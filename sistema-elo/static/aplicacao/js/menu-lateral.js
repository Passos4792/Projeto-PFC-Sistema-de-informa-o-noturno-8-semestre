//configuracao e eventos da tela
// Minimiza ou expande o menu sem recarregar a página.
const botaoMenu = document.getElementById("alternar-menu");

if (botaoMenu) {
    const atualizarMenu = () => {
        const minimizado = document.body.classList.contains("menu-minimizado");
        botaoMenu.textContent = minimizado ? "›" : "‹";
        botaoMenu.setAttribute("aria-label", minimizado ? "Expandir menu" : "Minimizar menu");
        botaoMenu.setAttribute("aria-expanded", String(!minimizado));
    };
    if (window.matchMedia("(max-width: 800px)").matches) {
        document.body.classList.add("menu-minimizado");
    }
    atualizarMenu();
    botaoMenu.addEventListener("click", () => {
        document.body.classList.toggle("menu-minimizado");
        atualizarMenu();
    });
}
//-------------------------------------------------------------------------------------
