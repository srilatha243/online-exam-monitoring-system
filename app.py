"""
Online Exam Monitoring & Integrity Analytics Platform
Flask Backend Application

Handles candidate authentication, session management, face monitoring,
browser activity logging, and integrity scoring via SQLite.
"""

import base64
import json
import os
import sqlite3
import uuid
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

# ==============================
# App Configuration
# ==============================

app = Flask(__name__)
app.secret_key = "online_exam_secret_key"

DATABASE = "database.db"

# Path to OpenCV Haar Cascade classifier for face detection
CASCADE_PATH = os.path.join(
    "data", "haarcascades", "haarcascade_frontalface_default.xml"
)

# Upload folder for candidate photos
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==============================
# Database Initialization
# ==============================


def create_database():
    """Create all required database tables if they do not exist."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Candidates table: stores registration info
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT,
        email TEXT UNIQUE,
        mobile TEXT,
        password TEXT,
        photo TEXT
    )
    """
    )

    # Incident logs: records face absence, focus loss, tab switches
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS incident_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        event_type TEXT,
        description TEXT,
        timestamp TEXT,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )
    """
    )

    # Integrity reports: stores computed scores and AI report text
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS integrity_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        integrity_score REAL,
        risk_label TEXT,
        report_text TEXT,
        generated_at TEXT,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )
    """
    )

    conn.commit()
    conn.close()


# Initialize DB on startup
create_database()


# ==============================
# Helper: Compute Integrity Score
# ==============================


def compute_integrity_score(candidate_id):
    """
    Compute the integrity score for a candidate.

    Scoring Rules (deductions from 100):
      - Face Absence:  -15 points each
      - Tab Switch:    -10 points each
      - Focus Loss:    -5  points each

    Returns score (float), risk_label (str: Low/Medium/High)
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT event_type FROM incident_logs WHERE candidate_id=?", (candidate_id,)
    )
    events = cursor.fetchall()
    conn.close()

    score = 100.0
    for (event_type,) in events:
        if event_type == "Face Absence":
            score -= 15
        elif event_type == "Tab Switch":
            score -= 10
        elif event_type == "Focus Loss":
            score -= 5

    score = max(0.0, score)

    # Determine risk label
    if score >= 75:
        risk_label = "Low"
    elif score >= 50:
        risk_label = "Medium"
    else:
        risk_label = "High"

    return round(score, 2), risk_label


# ==============================
# Home Page (Login)
# ==============================


@app.route("/")
def home():
    """Render the login/home page."""
    return render_template("index.html")


# ==============================
# Register
# ==============================


@app.route("/register", methods=["GET", "POST"])
def register():
    """Handle candidate registration with optional webcam photo capture."""
    if request.method == "POST":
        fullname = request.form.get("fullname")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        photo = request.form.get("photo")

        hashed_password = generate_password_hash(password)
        photo_path = ""

        # Decode and save base64 photo if provided
        if photo:
            try:
                header, encoded = photo.split(",", 1)
                image_data = base64.b64decode(encoded)
                filename = f"{uuid.uuid4().hex}.png"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                with open(filepath, "wb") as image_file:
                    image_file.write(image_data)
                photo_path = filepath
            except Exception as e:
                print("Photo Error:", e)

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO candidates (fullname, email, mobile, password, photo)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fullname, email, mobile, hashed_password, photo_path),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Email Already Exists"
        conn.close()
        return redirect("/")

    return render_template("register.html")


# ==============================
# Login
# ==============================


@app.route("/login", methods=["POST"])
def login():
    """Authenticate candidate credentials and start a session."""
    email = request.form.get("email")
    password = request.form.get("password")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates WHERE email=?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[4], password):
        session["user"] = {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "mobile": user[3],
            "photo": user[5],
        }
        return redirect("/dashboard")

    return """
    <h2 style='font-family:Arial;text-align:center;color:red;margin-top:100px;'>
    Invalid Email or Password
    </h2>
    <center><a href="/">Go Back</a></center>
    """


# ==============================
# Candidate Dashboard
# ==============================


@app.route("/dashboard")
def dashboard():
    """Render the candidate monitoring dashboard (requires login)."""
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session["user"])


# ==============================
# Logout
# ==============================


@app.route("/logout")
def logout():
    """Clear the session and redirect to the login page."""
    session.clear()
    return redirect("/")


# ==============================
# API: Face Presence Monitor
# ==============================


@app.route("/api/monitor", methods=["POST"])
def monitor():
    """
    Receive a base64-encoded webcam frame, run Haar Cascade face detection,
    and log a 'Face Absence' event if no face is detected.

    Expected JSON body:
        { "frame": "<base64-encoded PNG data URL>" }

    Returns JSON:
        { "face_detected": bool, "face_count": int }
    """
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data or "frame" not in data:
        return jsonify({"error": "No frame provided"}), 400

    candidate_id = session["user"]["id"]
    face_detected = False
    face_count = 0

    try:
        # Decode base64 image frame
        frame_data = data["frame"]
        if "," in frame_data:
            frame_data = frame_data.split(",", 1)[1]
        image_bytes = base64.b64decode(frame_data)
        np_array = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if frame is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Load Haar Cascade classifier
            face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            face_count = len(faces)
            face_detected = face_count > 0

            # Log face absence event if no face found
            if not face_detected:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO incident_logs (candidate_id, event_type, description, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        candidate_id,
                        "Face Absence",
                        "No face detected in webcam frame",
                        timestamp,
                    ),
                )
                conn.commit()
                conn.close()

    except Exception as e:
        print("Monitor Error:", e)
        return jsonify({"error": str(e)}), 500

    return jsonify({"face_detected": face_detected, "face_count": face_count})


# ==============================
# API: Browser Event Logger
# ==============================


@app.route("/api/log_event", methods=["POST"])
def log_event():
    """
    Log browser activity events such as focus loss or tab switching.

    Expected JSON body:
        {
            "event_type": "Focus Loss" | "Tab Switch",
            "description": "<optional details>"
        }

    Returns JSON:
        { "status": "logged" }
    """
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data or "event_type" not in data:
        return jsonify({"error": "Missing event_type"}), 400

    candidate_id = session["user"]["id"]
    event_type = data.get("event_type")
    description = data.get("description", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Only log recognized event types
    allowed_events = {"Focus Loss", "Tab Switch", "Face Absence"}
    if event_type not in allowed_events:
        return jsonify({"error": "Unknown event type"}), 400

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO incident_logs (candidate_id, event_type, description, timestamp)
        VALUES (?, ?, ?, ?)
        """,
        (candidate_id, event_type, description, timestamp),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "logged"})


# ==============================
# API: Get Integrity Score
# ==============================


@app.route("/api/integrity/<int:candidate_id>", methods=["GET"])
def get_integrity(candidate_id):
    """
    Compute and return the integrity score for a given candidate.

    Returns JSON:
        { "candidate_id": int, "score": float, "risk_label": str }
    """
    score, risk_label = compute_integrity_score(candidate_id)
    return jsonify(
        {"candidate_id": candidate_id, "score": score, "risk_label": risk_label}
    )


# ==============================
# API: Candidate Logs
# ==============================


@app.route("/api/logs/<int:candidate_id>", methods=["GET"])
def get_logs(candidate_id):
    """
    Return all incident logs for a given candidate as JSON.
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, event_type, description, timestamp FROM incident_logs WHERE candidate_id=?",
        (candidate_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    logs = [
        {"id": r[0], "event_type": r[1], "description": r[2], "timestamp": r[3]}
        for r in rows
    ]
    return jsonify(logs)


# ==============================
# Run Flask
# ==============================

if __name__ == "__main__":
    app.run(debug=True, port=5000)
