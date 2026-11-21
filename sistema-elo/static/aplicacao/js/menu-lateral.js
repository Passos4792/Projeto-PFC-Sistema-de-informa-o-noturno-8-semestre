const botaoMenu = document.getElementById("alternar-menu");

if (botaoMenu) {
    const atualizarMenu = () => {
        const minimizado = document.body.classList.contains("menu-minimizado");
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

// O link do título abre o cadastro. Apenas o botão de seta abre/fecha os perfis.
const botaoCadastros = document.querySelector('.menu-cadastros .alternar-cadastros');
const submenuCadastros = document.getElementById('submenu-cadastros');
if (botaoCadastros && submenuCadastros) {
    botaoCadastros.addEventListener('click', () => {
        const aberto = botaoCadastros.getAttribute('aria-expanded') === 'true';
        submenuCadastros.hidden = aberto;
        botaoCadastros.setAttribute('aria-expanded', String(!aberto));
        botaoCadastros.setAttribute('aria-label', aberto ? 'Mostrar tipos de usuário' : 'Ocultar tipos de usuário');
    });
}
