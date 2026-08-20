// ==============================
// Show / Hide Password
// ==============================

const password = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");

if (togglePassword && password) {

    togglePassword.addEventListener("click", () => {

        if (password.type === "password") {

            password.type = "text";

            togglePassword.innerHTML =
                '<i class="fas fa-eye-slash"></i>';

        } else {

            password.type = "password";

            togglePassword.innerHTML =
                '<i class="fas fa-eye"></i>';

        }

    });

}


// ==============================
// Login Loader Animation
// ==============================

const loginForm = document.getElementById("loginForm");
const loader = document.getElementById("loader");

if (loginForm) {

    loginForm.addEventListener("submit", function () {

        loader.style.display = "flex";

    });

}


// ==============================
// Button Hover Animation
// ==============================

const buttons = document.querySelectorAll("button, .register-btn");

buttons.forEach(button => {

    button.addEventListener("mouseenter", () => {

        button.style.transform = "scale(1.04)";

    });

    button.addEventListener("mouseleave", () => {

        button.style.transform = "scale(1)";

    });

});


// ==============================
// Floating Card Animation
// ==============================

const card = document.querySelector(".login-container");

if (card) {

    let direction = 1;

    setInterval(() => {

        card.style.transform =
            `translateY(${direction * 5}px)`;

        direction *= -1;

    }, 2500);

};


// ==============================
// Welcome Message
// ==============================

window.onload = function () {

    console.log("Online Exam Monitoring System Loaded Successfully");

}

// ==========================
// Animated Cursor
// ==========================

const cursor = document.querySelector(".cursor");
const cursor2 = document.querySelector(".cursor2");

document.addEventListener("mousemove", (e) => {

    cursor.style.left = e.clientX + "px";
    cursor.style.top = e.clientY + "px";

    cursor2.style.left = e.clientX + "px";
    cursor2.style.top = e.clientY + "px";

});

document.querySelectorAll("button,a,input").forEach(item=>{

    item.addEventListener("mouseenter",()=>{

        cursor.style.transform="translate(-50%,-50%) scale(1.8)";
        cursor2.style.transform="translate(-50%,-50%) scale(1.5)";

    });

    item.addEventListener("mouseleave",()=>{

        cursor.style.transform="translate(-50%,-50%) scale(1)";
        cursor2.style.transform="translate(-50%,-50%) scale(1)";

    });

});
