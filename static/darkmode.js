const DARKNESS = {
    "html": "dark"
}

function toggleDarkness() {
    if (localStorage.getItem("dark")) {
        console.log("MODE = DARK");
        lightMode();
    } else {
        console.log("MODE != DARK");
        darkMode();
    }
}

function lightMode() {
    for (const [key, value] of Object.entries(DARKNESS)) {
        document.querySelectorAll(key).forEach((e) => e.classList.remove(value));
    }
    try {
        localStorage.removeItem("dark");
    } catch (e) {
        alert("Could not save preference!");
    }
}

function darkMode() {
    for (const [key, value] of Object.entries(DARKNESS)) {
        document.querySelectorAll(key).forEach((e) => e.classList.add(value));
    }
    try {
        localStorage.setItem("dark", true);
    } catch (e) {
        alert("Could not save preference!");
    }
}

function initDarkMode() {
    if (localStorage.getItem("dark")) {
        darkMode();
        console.log("DarkModeSetup");
    }
}

console.log(localStorage.getItem("dark"));