"""
Online Exam Monitoring & Integrity Analytics Platform
Streamlit Dashboard for Invigilators

Provides:
- Cohort-level analytics (event distributions, heatmaps, K-Means clustering)
- Individual candidate detail with integrity scoring and AI report generation
- Demo data generation using Faker
- CSV and JSON export
"""

import json
import os
import random
import sqlite3
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend (required for Streamlit on Windows)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from faker import Faker
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from werkzeug.security import generate_password_hash

# ==============================
# Page Configuration
# ==============================

st.set_page_config(
    page_title="Exam Integrity Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================
# Constants
# ==============================

DATABASE = "database.db"

# Integrity score deduction weights per event type
EVENT_WEIGHTS = {
    "Face Absence": 15,
    "Tab Switch": 10,
    "Focus Loss": 5,
}

# ==============================
# Database Helpers
# ==============================


def get_connection():
    """Return a new SQLite connection with row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    """Ensure all required tables exist before querying."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT, email TEXT UNIQUE,
            mobile TEXT, password TEXT, photo TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER, event_type TEXT,
            description TEXT, timestamp TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS integrity_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER, integrity_score REAL,
            risk_label TEXT, report_text TEXT, generated_at TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )
    """
    )
    conn.commit()
    conn.close()


ensure_tables()


def load_candidates():
    """Load all candidates from the database as a DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM candidates", conn)
    conn.close()
    return df


def load_logs():
    """Load all incident logs from the database as a DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM incident_logs", conn)
    conn.close()
    return df


def load_candidate_logs(candidate_id):
    """Load incident logs for a specific candidate."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM incident_logs WHERE candidate_id=?", conn, params=(candidate_id,)
    )
    conn.close()
    return df


# ==============================
# Integrity Scoring Engine
# ==============================


def compute_integrity_score(candidate_id, logs_df=None):
    """
    Compute integrity score for a candidate.

    Start at 100, subtract points per event:
      - Face Absence: -15
      - Tab Switch:   -10
      - Focus Loss:   -5

    Returns (score: float, risk_label: str)
    """
    if logs_df is None:
        logs_df = load_candidate_logs(candidate_id)

    score = 100.0
    for _, row in logs_df.iterrows():
        score -= EVENT_WEIGHTS.get(row["event_type"], 0)
    score = max(0.0, score)

    if score >= 75:
        risk_label = "Low"
    elif score >= 50:
        risk_label = "Medium"
    else:
        risk_label = "High"

    return round(score, 2), risk_label


# ==============================
# AI Integrity Report Generator
# ==============================


def generate_integrity_report(candidate_name, score, risk_label, logs_df):
    """
    Generate a structured AI integrity report.

    Attempts to use LangChain with an OpenAI/Gemini LLM if configured.
    Falls back to a rule-based structured report generator if no API key is set.
    """
    # Count event types
    event_counts = (
        logs_df["event_type"].value_counts().to_dict() if not logs_df.empty else {}
    )
    face_absences = event_counts.get("Face Absence", 0)
    tab_switches = event_counts.get("Tab Switch", 0)
    focus_losses = event_counts.get("Focus Loss", 0)
    total_events = face_absences + tab_switches + focus_losses

    # Try LangChain LLM if available
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from langchain.chains import LLMChain
            from langchain.prompts import PromptTemplate
            from langchain_community.llms import OpenAI

            prompt_template = PromptTemplate(
                input_variables=[
                    "name",
                    "score",
                    "risk_label",
                    "face_absences",
                    "tab_switches",
                    "focus_losses",
                ],
                template="""
You are an AI exam integrity analyst. Generate a concise professional integrity report.

Candidate: {name}
Integrity Score: {score}/100
Risk Level: {risk_label}
Face Absences: {face_absences}
Tab Switches: {tab_switches}
Focus Losses: {focus_losses}

Provide:
1. Executive Summary
2. Key Findings
3. Recommendation

Keep report under 200 words. Be professional and non-accusatory.
""",
            )
            llm = OpenAI(temperature=0.3, openai_api_key=openai_key)
            chain = LLMChain(llm=llm, prompt=prompt_template)
            report = chain.run(
                name=candidate_name,
                score=score,
                risk_label=risk_label,
                face_absences=face_absences,
                tab_switches=tab_switches,
                focus_losses=focus_losses,
            )
            return report.strip()
        except Exception as e:
            st.warning(f"LLM unavailable ({e}). Using structured report.")

    # ---- Fallback: Rule-Based Structured Report ----
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if risk_label == "Low":
        summary = (
            f"{candidate_name} demonstrated strong examination integrity throughout the session. "
            f"The integrity score of {score}/100 reflects minimal suspicious activity."
        )
        recommendation = (
            "No further review is required. The candidate maintained consistent attention and "
            "browser focus during the examination period."
        )
    elif risk_label == "Medium":
        summary = (
            f"{candidate_name} exhibited moderate levels of suspicious activity during the session. "
            f"The integrity score of {score}/100 indicates areas that may warrant attention."
        )
        recommendation = (
            "A secondary manual review of the examination session is recommended. "
            "The invigilator should cross-reference the event timeline with other evidence."
        )
    else:
        summary = (
            f"{candidate_name} exhibited significant suspicious activity during the session. "
            f"The integrity score of {score}/100 is below acceptable thresholds and indicates "
            f"a high probability of examination misconduct."
        )
        recommendation = (
            "An immediate review of the candidate's session is strongly recommended. "
            "Evidence should be compiled and forwarded to the examination committee for evaluation."
        )

    report = f"""
INTEGRITY REPORT — GENERATED {timestamp}
{'='*55}

CANDIDATE:       {candidate_name}
INTEGRITY SCORE: {score}/100
RISK LEVEL:      {risk_label}

EXECUTIVE SUMMARY
{'-'*55}
{summary}

KEY FINDINGS
{'-'*55}
• Face Absences Detected:  {face_absences} event(s) — deducted {face_absences * 15} points
• Tab Switches Detected:   {tab_switches} event(s) — deducted {tab_switches * 10} points
• Focus Loss Events:       {focus_losses} event(s) — deducted {focus_losses * 5} points
• Total Suspicious Events: {total_events}

RECOMMENDATION
{'-'*55}
{recommendation}

{'='*55}
This report was generated automatically by the Exam Integrity AI System.
It is intended as an informational tool only and does not constitute
a final disciplinary decision.
""".strip()

    return report


# ==============================
# Faker Demo Data Generator
# ==============================


def generate_demo_data(num_candidates=15):
    """
    Populate the database with realistic demo candidates and incident logs.
    Uses Faker to generate names, emails, and mobile numbers.
    """
    fake = Faker()
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    event_types = ["Face Absence", "Tab Switch", "Focus Loss"]
    descriptions = {
        "Face Absence": "No face detected in webcam frame",
        "Tab Switch": "Candidate switched tabs or minimised browser",
        "Focus Loss": "Candidate left the exam window",
    }

    generated = 0
    for _ in range(num_candidates):
        name = fake.name()
        email = fake.unique.email()
        mobile = fake.numerify("##########")
        password = generate_password_hash("password123")

        try:
            cursor.execute(
                "INSERT INTO candidates (fullname, email, mobile, password, photo) VALUES (?,?,?,?,?)",
                (name, email, mobile, password, ""),
            )
            conn.commit()
            candidate_id = cursor.lastrowid

            # Randomly generate 0–20 incident logs over a 2-hour window
            num_events = random.randint(0, 20)
            base_time = datetime.now() - timedelta(hours=2)
            for _ in range(num_events):
                event_type = random.choice(event_types)
                event_time = base_time + timedelta(seconds=random.randint(0, 7200))
                cursor.execute(
                    """
                    INSERT INTO incident_logs (candidate_id, event_type, description, timestamp)
                    VALUES (?,?,?,?)
                    """,
                    (
                        candidate_id,
                        event_type,
                        descriptions[event_type],
                        event_time.strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
            conn.commit()
            generated += 1
        except sqlite3.IntegrityError:
            continue  # Skip duplicate emails

    conn.close()
    return generated


# ==============================
# Sidebar Navigation
# ==============================

st.sidebar.image(
    "https://img.icons8.com/color/96/000000/shield--v2.png",
    width=80,
)
st.sidebar.title("🛡️ Exam Integrity")
st.sidebar.markdown("**Online Exam Monitoring Platform**")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["📊 Cohort Analytics", "👤 Candidate Detail"],
    index=0,
)
st.sidebar.divider()

# Demo data generator
st.sidebar.subheader("Demo Data")
num_demo = st.sidebar.slider("Number of candidates", 5, 30, 15)
if st.sidebar.button("🧪 Generate Demo Data"):
    count = generate_demo_data(num_demo)
    st.sidebar.success(f"Generated {count} demo candidates!")
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("Flask Backend: `http://localhost:5000`")
st.sidebar.markdown("Streamlit: `http://localhost:8501`")

# ==============================
# Load Data
# ==============================

candidates_df = load_candidates()
logs_df = load_logs()

# ==============================
# PAGE 1: Cohort Analytics
# ==============================

if page == "📊 Cohort Analytics":

    st.title("📊 Cohort Integrity Analytics")
    st.markdown("Platform-wide statistics for all registered candidates.")
    st.divider()

    if candidates_df.empty:
        st.info(
            "No candidates found. Click **Generate Demo Data** in the sidebar to populate the database."
        )
    else:
        # ---- KPI Metrics ----
        total_candidates = len(candidates_df)
        total_logs = len(logs_df)

        # Compute scores for all candidates
        all_scores = []
        all_risk = []
        for cid in candidates_df["id"].tolist():
            cand_logs = logs_df[logs_df["candidate_id"] == cid]
            score, risk = compute_integrity_score(cid, cand_logs)
            all_scores.append(score)
            all_risk.append(risk)

        avg_score = round(np.mean(all_scores), 2) if all_scores else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("👥 Total Candidates", total_candidates)
        col2.metric("📋 Total Incident Logs", total_logs)
        col3.metric("📈 Avg Integrity Score", f"{avg_score}/100")
        col4.metric(
            "⚠️ High Risk",
            all_risk.count("High"),
        )

        st.divider()

        # ---- Integrity Score Distribution ----
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Integrity Score Distribution")
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.set_facecolor("#0d1117")
            fig.patch.set_facecolor("#0d1117")
            ax.hist(
                all_scores, bins=10, color="#00c6ff", edgecolor="#0072ff", alpha=0.85
            )
            ax.set_xlabel("Integrity Score", color="white")
            ax.set_ylabel("Candidate Count", color="white")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#333")
            st.pyplot(fig)
            plt.close(fig)

        with col_right:
            st.subheader("Risk Label Distribution")
            risk_counts = pd.Series(all_risk).value_counts()
            fig2, ax2 = plt.subplots(figsize=(5, 4))
            fig2.patch.set_facecolor("#0d1117")
            colors = {"Low": "#00ff88", "Medium": "#ffbb33", "High": "#ff4444"}
            pie_colors = [colors.get(r, "#aaa") for r in risk_counts.index]
            ax2.pie(
                risk_counts.values,
                labels=risk_counts.index,
                colors=pie_colors,
                autopct="%1.1f%%",
                textprops={"color": "white"},
            )
            ax2.set_facecolor("#0d1117")
            st.pyplot(fig2)
            plt.close(fig2)

        st.divider()

        # ---- Event Distribution ----
        if not logs_df.empty:
            st.subheader("Suspicious Event Distribution")
            event_counts = logs_df["event_type"].value_counts()
            fig3, ax3 = plt.subplots(figsize=(8, 3))
            ax3.set_facecolor("#0d1117")
            fig3.patch.set_facecolor("#0d1117")
            event_counts.plot(
                kind="bar",
                ax=ax3,
                color=["#00c6ff", "#ffbb33", "#ff4444"],
                edgecolor="#333",
            )
            ax3.set_xlabel("Event Type", color="white")
            ax3.set_ylabel("Count", color="white")
            ax3.tick_params(colors="white", axis="both")
            plt.xticks(rotation=0)
            for spine in ax3.spines.values():
                spine.set_edgecolor("#333")
            st.pyplot(fig3)
            plt.close(fig3)

        st.divider()

        # ---- Heatmap: Events by Hour vs Candidate ----
        st.subheader("🔥 Suspicious Events Heatmap (Hour × Candidate)")
        if not logs_df.empty and "timestamp" in logs_df.columns:
            try:
                logs_df["timestamp"] = pd.to_datetime(
                    logs_df["timestamp"], errors="coerce"
                )
                logs_df["hour"] = logs_df["timestamp"].dt.hour

                # Map candidate_id to short names
                cid_to_name = dict(
                    zip(
                        candidates_df["id"],
                        candidates_df["fullname"].str.split().str[0],
                    )
                )
                logs_df["candidate_label"] = logs_df["candidate_id"].map(cid_to_name)

                pivot = (
                    logs_df.groupby(["hour", "candidate_label"])
                    .size()
                    .unstack(fill_value=0)
                )

                fig4, ax4 = plt.subplots(figsize=(12, max(4, len(pivot.columns) * 0.5)))
                fig4.patch.set_facecolor("#0d1117")
                sns.heatmap(
                    pivot.T,
                    ax=ax4,
                    cmap="YlOrRd",
                    linewidths=0.3,
                    linecolor="#333",
                    annot=True,
                    fmt="d",
                    cbar_kws={"label": "Event Count"},
                )
                ax4.set_xlabel("Hour of Day", color="white")
                ax4.set_ylabel("Candidate", color="white")
                ax4.tick_params(colors="white")
                ax4.set_title("Suspicious Events by Hour", color="white")
                st.pyplot(fig4)
                plt.close(fig4)
            except Exception as e:
                st.warning(f"Could not render heatmap: {e}")

        st.divider()

        # ---- K-Means Clustering ----
        st.subheader("🤖 K-Means Risk Clustering")
        st.caption(
            "Candidates are clustered into 3 groups (Low/Medium/High Risk) "
            "based on Face Absence, Tab Switch, and Focus Loss counts."
        )

        if not logs_df.empty and len(candidates_df) >= 3:
            # Build feature matrix
            feature_rows = []
            for cid in candidates_df["id"].tolist():
                cand_logs = logs_df[logs_df["candidate_id"] == cid]
                face_abs = len(cand_logs[cand_logs["event_type"] == "Face Absence"])
                tab_sw = len(cand_logs[cand_logs["event_type"] == "Tab Switch"])
                focus_l = len(cand_logs[cand_logs["event_type"] == "Focus Loss"])
                feature_rows.append(
                    {
                        "candidate_id": cid,
                        "face_absence": face_abs,
                        "tab_switch": tab_sw,
                        "focus_loss": focus_l,
                    }
                )

            features_df = pd.DataFrame(feature_rows)
            X = features_df[["face_absence", "tab_switch", "focus_loss"]].values

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            n_clusters = min(3, len(candidates_df))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            features_df["cluster"] = kmeans.fit_predict(X_scaled)

            # Map cluster labels to risk labels by centroid severity
            centroids = kmeans.cluster_centers_
            centroid_severity = centroids.sum(axis=1)
            cluster_order = np.argsort(centroid_severity)
            cluster_labels = {}
            label_names = ["Low Risk", "Medium Risk", "High Risk"]
            for rank, cluster_id in enumerate(cluster_order):
                cluster_labels[cluster_id] = label_names[min(rank, 2)]
            features_df["risk_cluster"] = features_df["cluster"].map(cluster_labels)

            # Merge with candidate names
            features_df = features_df.merge(
                candidates_df[["id", "fullname"]], left_on="candidate_id", right_on="id"
            )

            cluster_colors = {
                "Low Risk": "#00ff88",
                "Medium Risk": "#ffbb33",
                "High Risk": "#ff4444",
            }

            fig5, ax5 = plt.subplots(figsize=(8, 5))
            fig5.patch.set_facecolor("#0d1117")
            ax5.set_facecolor("#0d1117")
            for risk_grp, grp in features_df.groupby("risk_cluster"):
                ax5.scatter(
                    grp["tab_switch"],
                    grp["face_absence"],
                    label=risk_grp,
                    color=cluster_colors.get(risk_grp, "#aaa"),
                    s=100,
                    alpha=0.85,
                )
            ax5.set_xlabel("Tab Switches", color="white")
            ax5.set_ylabel("Face Absences", color="white")
            ax5.tick_params(colors="white")
            ax5.legend(facecolor="#1a1a2e", labelcolor="white")
            ax5.set_title("Candidate Risk Clusters", color="white")
            for spine in ax5.spines.values():
                spine.set_edgecolor("#333")
            st.pyplot(fig5)
            plt.close(fig5)

            # Show cluster summary table
            st.subheader("Cluster Summary")
            cluster_summary = (
                features_df.groupby("risk_cluster")[
                    ["face_absence", "tab_switch", "focus_loss"]
                ]
                .mean()
                .round(2)
            )
            st.dataframe(cluster_summary, use_container_width=True)

            st.divider()

            # Detailed candidate table with scores
            st.subheader("All Candidates — Integrity Overview")
            rows = []
            for _, row in features_df.iterrows():
                cand_logs = logs_df[logs_df["candidate_id"] == row["candidate_id"]]
                score, risk = compute_integrity_score(row["candidate_id"], cand_logs)
                rows.append(
                    {
                        "Name": row["fullname"],
                        "Email": candidates_df.loc[
                            candidates_df["id"] == row["candidate_id"], "email"
                        ].values[0],
                        "Score": score,
                        "Risk": risk,
                        "Cluster": row["risk_cluster"],
                        "Face Abs.": row["face_absence"],
                        "Tab Sw.": row["tab_switch"],
                        "Focus L.": row["focus_loss"],
                    }
                )
            summary_df = pd.DataFrame(rows).sort_values("Score")
            st.dataframe(summary_df, use_container_width=True)

            # Export CSV
            csv_data = summary_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Export CSV",
                data=csv_data,
                file_name="cohort_integrity_report.csv",
                mime="text/csv",
            )
        else:
            st.info(
                "Not enough data for clustering. Generate demo data with at least 3 candidates."
            )

# ==============================
# PAGE 2: Candidate Detail
# ==============================

elif page == "👤 Candidate Detail":

    st.title("👤 Candidate Integrity Detail")
    st.divider()

    if candidates_df.empty:
        st.info("No candidates found. Click **Generate Demo Data** in the sidebar.")
    else:
        # Candidate selector
        candidate_options = {
            row["fullname"] + f" ({row['email']})": row["id"]
            for _, row in candidates_df.iterrows()
        }
        selected_label = st.selectbox(
            "Select Candidate", list(candidate_options.keys())
        )
        candidate_id = candidate_options[selected_label]

        candidate = candidates_df[candidates_df["id"] == candidate_id].iloc[0]
        cand_logs = load_candidate_logs(candidate_id)
        score, risk_label = compute_integrity_score(candidate_id, cand_logs)

        st.divider()

        # ---- Candidate Profile ----
        col_profile, col_score = st.columns([1, 2])

        with col_profile:
            st.subheader("Profile")
            photo_path = candidate.get("photo", "")
            if photo_path and os.path.exists(photo_path):
                st.image(photo_path, width=150)
            else:
                st.image("https://i.pravatar.cc/150", width=150, caption="No photo")
            st.markdown(f"**Name:** {candidate['fullname']}")
            st.markdown(f"**Email:** {candidate['email']}")
            st.markdown(f"**Mobile:** {candidate['mobile']}")

        with col_score:
            st.subheader("Integrity Score")
            risk_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(
                risk_label, "⚪"
            )
            st.metric(
                label=f"{risk_color} Risk Level: {risk_label}",
                value=f"{score}/100",
            )

            # Score progress bar
            bar_color = {"Low": "#00ff88", "Medium": "#ffbb33", "High": "#ff4444"}.get(
                risk_label, "#aaa"
            )
            st.progress(int(score))

            # Event breakdown
            if not cand_logs.empty:
                event_counts = cand_logs["event_type"].value_counts()
                st.subheader("Event Breakdown")
                for evt, cnt in event_counts.items():
                    deduction = EVENT_WEIGHTS.get(evt, 0) * cnt
                    st.markdown(f"- **{evt}**: {cnt} event(s) → -{deduction} pts")

        st.divider()

        # ---- Incident Logs Table ----
        st.subheader("📋 Incident Logs")
        if cand_logs.empty:
            st.success("✅ No suspicious events logged for this candidate.")
        else:
            st.dataframe(
                cand_logs[["event_type", "description", "timestamp"]].reset_index(
                    drop=True
                ),
                use_container_width=True,
            )

        st.divider()

        # ---- AI Integrity Report ----
        st.subheader("🤖 AI Integrity Report")
        if st.button("Generate Report"):
            with st.spinner("Generating integrity report..."):
                report_text = generate_integrity_report(
                    candidate["fullname"], score, risk_label, cand_logs
                )
            st.text_area("Integrity Report", value=report_text, height=300)

            # Save report to DB
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO integrity_reports
                (candidate_id, integrity_score, risk_label, report_text, generated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    score,
                    risk_label,
                    report_text,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
            conn.close()
            st.success("Report saved to database.")

            # JSON Export
            export_data = {
                "candidate": {
                    "id": int(candidate_id),
                    "name": candidate["fullname"],
                    "email": candidate["email"],
                },
                "integrity_score": score,
                "risk_label": risk_label,
                "report": report_text,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "incident_logs": (
                    cand_logs.to_dict(orient="records") if not cand_logs.empty else []
                ),
            }
            st.download_button(
                label="⬇️ Export JSON Report",
                data=json.dumps(export_data, indent=2),
                file_name=f"integrity_report_{candidate_id}.json",
                mime="application/json",
            )
