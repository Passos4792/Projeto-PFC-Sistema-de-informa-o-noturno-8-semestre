// Minimiza ou expande o menu sem recarregar a página.
const botaoMenu = document.getElementById("alternar-menu");

if (botaoMenu) {
    botaoMenu.addEventListener("click", () => {
        const minimizado = document.body.classList.toggle("menu-minimizado");
        botaoMenu.textContent = minimizado ? "›" : "‹";
        botaoMenu.setAttribute("aria-label", minimizado ? "Expandir menu" : "Minimizar menu");
    });
}
