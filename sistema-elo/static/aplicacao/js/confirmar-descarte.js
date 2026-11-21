/* Proteção de formulários em edição: não altera nenhuma regra de negócio. */
(() => {
    'use strict';

    const formularios = Array.from(document.querySelectorAll('form[data-proteger-rascunho]'));
    if (!formularios.length) return;

    // Os campos de senha nunca são copiados. O estado inicial só é comparado no navegador.
    function estadoDo(formulario) {
        return Array.from(formulario.elements).filter(campo => campo.name && !campo.disabled &&
            !['submit', 'button', 'reset', 'image', 'password'].includes(campo.type) &&
            campo.name !== 'csrfmiddlewaretoken').map(campo => {
            let valor;
            if (campo.type === 'file') {
                valor = Array.from(campo.files || []).map(arquivo => [arquivo.name, arquivo.size, arquivo.lastModified]);
            } else if (campo.type === 'checkbox' || campo.type === 'radio') {
                valor = [campo.checked, campo.value];
            } else if (campo.tagName === 'SELECT' && campo.multiple) {
                valor = Array.from(campo.selectedOptions, opcao => opcao.value);
            } else {
                valor = campo.value;
            }
            return [campo.name, valor];
        });
    }

    const estadosIniciais = new Map(formularios.map(formulario => [formulario, JSON.stringify(estadoDo(formulario))]));
    let formularioEnviado = false;
    let saidaConfirmada = false;
    const modificado = () => !formularioEnviado && !saidaConfirmada && formularios.some(
        formulario => JSON.stringify(estadoDo(formulario)) !== estadosIniciais.get(formulario) ||
            Array.from(formulario.querySelectorAll('input[type="password"]')).some(campo => campo.value.length > 0)
    );

    formularios.forEach(formulario => {
        formulario.addEventListener('submit', () => { formularioEnviado = true; });
    });

    const dialogo = document.createElement('dialog');
    dialogo.className = 'elo-dialogo-descarte';
    dialogo.setAttribute('aria-labelledby', 'elo-descartar-titulo');
    dialogo.setAttribute('aria-describedby', 'elo-descartar-texto');
    dialogo.innerHTML = `
        <div class="elo-dialogo-descarte__corpo">
            <h2 id="elo-descartar-titulo">Descartar registro?</h2>
            <p id="elo-descartar-texto">Você tem alterações não salvas. Se sair agora, elas serão perdidas.</p>
            <div class="elo-dialogo-descarte__acoes">
                <button type="button" class="botao-secundario" data-permanecer>Não, permanecer</button>
                <button type="button" class="botao-principal" data-descartar>Sim, descartar</button>
            </div>
        </div>`;
    document.body.appendChild(dialogo);
    let destinoPendente = null;
    const permanecer = dialogo.querySelector('[data-permanecer]');
    const descartar = dialogo.querySelector('[data-descartar]');
    permanecer.addEventListener('click', () => dialogo.close());
    dialogo.addEventListener('close', () => { destinoPendente = null; });
    dialogo.addEventListener('click', evento => {
        if (evento.target === dialogo) dialogo.close();
    });
    descartar.addEventListener('click', () => {
        if (!destinoPendente) return;
        const destino = destinoPendente;
        saidaConfirmada = true;
        dialogo.close();
        window.location.assign(destino);
    });

    // Navegação por links (inclusive Voltar/Cancelar, menu e logotipo) usa o diálogo do ELO.
    document.addEventListener('click', evento => {
        if (evento.defaultPrevented || evento.button !== 0 || evento.ctrlKey || evento.metaKey ||
            evento.shiftKey || evento.altKey) return;
        const link = evento.target.closest('a[href]');
        if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
        const destino = link.href;
        if (!destino || destino.startsWith('javascript:') || destino.startsWith('mailto:') ||
            destino.startsWith('tel:') || destino.startsWith('#')) return;
        const url = new URL(destino, window.location.href);
        if (url.origin !== window.location.origin ||
            (url.pathname === window.location.pathname && url.search === window.location.search)) return;
        if (!modificado()) return;
        evento.preventDefault();
        destinoPendente = url.href;
        if (typeof dialogo.showModal === 'function') {
            dialogo.showModal();
            permanecer.focus();
        } else if (window.confirm('Descartar registro? As alterações não salvas serão perdidas.')) {
            saidaConfirmada = true;
            window.location.assign(destinoPendente);
        }
    }, true);

    // Ao fechar a guia, atualizar a página ou usar o botão voltar do navegador,
    // o texto da confirmação é controlado pelo próprio navegador.
    window.addEventListener('beforeunload', evento => {
        if (!modificado()) return;
        evento.preventDefault();
        evento.returnValue = '';
    });
})();
