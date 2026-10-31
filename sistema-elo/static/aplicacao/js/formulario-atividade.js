

(() => {
    const formulario = document.querySelector('[data-formulario-atividade]');
    const aluno = formulario?.querySelector('[data-aluno]');
    const meta = formulario?.querySelector('[data-meta]');
    if (!aluno || !meta) return;
    let revisao = 0;
    aluno.addEventListener('change', async () => {
        const atual = ++revisao;
        meta.replaceChildren(new Option('Sem meta específica', ''));
        meta.disabled = false;
        if (!aluno.value) return;
        meta.disabled = true;
        try {
            const resposta = await fetch(formulario.dataset.metasUrl.replace('/0/', '/' + aluno.value + '/'), {credentials: 'same-origin'});
            if (!resposta.ok) throw new Error('Não foi possível consultar as metas.');
            const dados = await resposta.json();
            if (atual !== revisao) return;
            dados.forEach(item => meta.add(new Option(item.titulo, item.id)));
        } catch (erro) {
            if (atual === revisao) meta.add(new Option('Não foi possível carregar. Recarregue a página.', '', true, true));
        } finally {
            if (atual === revisao) meta.disabled = false;
        }
    });
})();
