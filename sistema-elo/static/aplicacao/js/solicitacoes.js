

document.addEventListener('submit', async (evento) => {
    const formulario = evento.target.closest('[data-solicitar], [data-decisao]');
    if (!formulario) return;
    evento.preventDefault();
    if (formulario.dataset.enviando) return;
    const decisao = formulario.hasAttribute('data-decisao');
    const campos = new FormData(formulario);
    const dados = decisao
        ? {decisao: evento.submitter?.value, resposta: campos.get('resposta')}
        : {mensagem: campos.get('mensagem')};
    const retorno = formulario.querySelector('[data-retorno]');
    if (decisao && dados.decisao === 'RECUSADA' && !dados.resposta.trim()) {
        retorno.textContent = 'Escreva uma orientação para solicitar a revisão.';
        formulario.querySelector('textarea').focus();
        return;
    }
    formulario.dataset.enviando = '1';
    const botoes = formulario.querySelectorAll('button');
    botoes.forEach(botao => botao.disabled = true);
    retorno.textContent = 'Enviando…';
    try {
        const resposta = await fetch(formulario.action, {
            method: decisao ? 'PATCH' : 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': campos.get('csrfmiddlewaretoken')},
            body: JSON.stringify(dados),
        });
        const resultado = await resposta.json();
        if (!resposta.ok) throw new Error(resultado.erro || resultado.detail || Object.values(resultado).flat().join(' '));
        window.location.reload();
    } catch (erro) {
        retorno.textContent = erro.message || 'Não foi possível confirmar o envio. Atualize a página antes de tentar novamente.';
        delete formulario.dataset.enviando;
        botoes.forEach(botao => botao.disabled = false);
    }
});
