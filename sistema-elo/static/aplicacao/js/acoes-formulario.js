(() => {
    const dialogo = document.getElementById('elo-dialogo-confirmacao');
    let botaoPendente = null;

    document.addEventListener('click', (evento) => {
        const botao = evento.target.closest('button[data-confirmar]');
        if (!botao || !botao.form) return;

        evento.preventDefault();
        if (!dialogo || typeof dialogo.showModal !== 'function') {
            if (window.confirm(botao.dataset.confirmar)) botao.form.requestSubmit(botao);
            return;
        }
        if (dialogo.open) return;

        botaoPendente = botao;
        dialogo.querySelector('#elo-dialogo-titulo').textContent = botao.dataset.tituloConfirmacao || 'Confirmar ação';
        dialogo.querySelector('#elo-dialogo-mensagem').textContent = botao.dataset.confirmar;
        dialogo.querySelector('[data-confirmar-dialogo]').textContent = botao.dataset.rotuloConfirmacao || 'Confirmar';
        dialogo.showModal();
        dialogo.querySelector('[data-fechar-dialogo]').focus();
    });

    if (dialogo) {
        dialogo.querySelector('[data-fechar-dialogo]').addEventListener('click', () => dialogo.close());
        dialogo.querySelector('[data-confirmar-dialogo]').addEventListener('click', () => {
            const botao = botaoPendente;
            botaoPendente = null;
            dialogo.close();
            if (botao?.isConnected && botao.form) botao.form.requestSubmit(botao);
        });
        dialogo.addEventListener('close', () => {
            if (botaoPendente) botaoPendente.focus();
            botaoPendente = null;
        });
        dialogo.addEventListener('click', (evento) => {
            if (evento.target === dialogo) dialogo.close();
        });
    }
})();

document.addEventListener('change', (evento) => {
    const campo = evento.target.closest('[data-envio-automatico]');
    if (campo?.form) campo.form.submit();
});
