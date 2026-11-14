(() => {
    const nivel = document.querySelector('[data-nivel-acesso]');
    if (!nivel || !nivel.form) return;
    const formulario = nivel.form;

    function atualizar() {
        const escolhido = nivel.value;
        formulario.querySelectorAll('[data-somente-nivel]').forEach(campo => {
            const visivel = campo.dataset.somenteNivel === escolhido;
            campo.closest('.grupo-campo').hidden = !visivel;
            campo.disabled = !visivel;
        });
        formulario.querySelectorAll('[data-obrigatorio-nivel]').forEach(campo => {
            const obrigatorio = campo.dataset.obrigatorioNivel === escolhido;
            campo.required = obrigatorio;
            const rotulo = campo.closest('.grupo-campo').querySelector('label');
            const marca = rotulo.querySelector('.obrigatorio');
            if (obrigatorio && !marca) {
                const nova = document.createElement('span');
                nova.className = 'obrigatorio';
                nova.setAttribute('aria-hidden', 'true');
                nova.textContent = ' *';
                rotulo.append(nova);
            } else if (!obrigatorio && marca) {
                marca.remove();
            }
        });
    }

    nivel.addEventListener('change', atualizar);
    atualizar();
})();
