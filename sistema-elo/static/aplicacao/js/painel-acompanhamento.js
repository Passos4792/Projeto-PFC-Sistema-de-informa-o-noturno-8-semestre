

(() => {
    const painel = document.querySelector('[data-painel]');
    if (!painel) return;
    const formulario = painel.querySelector('[data-filtros-painel]');
    let grafico, controle, revisao = 0, atraso;
    function desenhar(dados) {
        grafico?.destroy();
        const secao = painel.dataset.secao;
        const canvas = painel.querySelector('[data-grafico]');
        if (!canvas) return;

        const selecionarAluno = ['frequencias', 'conteudos', 'metas'].includes(secao) && !formulario.elements.aluno.value;
        if (selecionarAluno) {
            canvas.hidden = true;
            painel.querySelector('[data-grafico-vazio]').hidden = true;
            return;
        }
        if (!window.Chart) return;
        let linhas, conjuntos;
        if (secao === 'metas') {
            linhas = dados.periodos.map(item => item.nome);
            conjuntos = [{label: 'Metas', data: dados.periodos.map(item => item.total), backgroundColor: '#b4b9df'},
                {label: 'Alcançadas', data: dados.periodos.map(item => item.alcancadas), backgroundColor: '#548e80'}];
        } else if (secao === 'frequencias') {
            linhas = dados.frequencias.map(item => item.aluno);
            conjuntos = [{label: 'Atual (%)', data: dados.frequencias.map(item => item.atual), backgroundColor: '#777db0'},
                {label: 'Mínima (%)', data: dados.frequencias.map(item => item.minima), backgroundColor: '#ebc56f'}];
        } else {
            linhas = dados.conteudos.map(item => item.nome);
            conjuntos = [{label: 'Atividades', data: dados.conteudos.map(item => item.total), backgroundColor: '#b4b9df'},
                {label: 'Realizadas', data: dados.conteudos.map(item => item.realizadas), backgroundColor: '#548e80'}];
        }
        canvas.hidden = !linhas.length;
        painel.querySelector('[data-grafico-vazio]').hidden = !!linhas.length;
        if (!linhas.length) return;
        grafico = new Chart(canvas, {
            type: 'bar', data: {labels: linhas, datasets: conjuntos},
            options: {responsive: true, maintainAspectRatio: false,
                animation: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? false : undefined,
                plugins: {legend: {position: 'bottom'}},
                scales: {y: {beginAtZero: true, max: secao === 'frequencias' ? 100 : undefined, ticks: {precision: 0}}}},
        });
    }
    async function atualizar(substituir) {
        const dadosLocais = ['frequencias', 'conteudos', 'metas'].includes(painel.dataset.secao);

        if (dadosLocais && !substituir) {
            const dadosIniciais = painel.querySelector('#dados-painel-iniciais');
            if (dadosIniciais) desenhar(JSON.parse(dadosIniciais.textContent));
            return;
        }
        controle?.abort();
        controle = new AbortController();
        const atual = ++revisao;
        const url = new URL(window.location.href);
        url.search = new URLSearchParams(new FormData(formulario)).toString();
        const api = new URL(painel.dataset.api, window.location.origin);
        api.search = url.search;
        api.searchParams.set('secao', painel.dataset.secao);
        try {
            const opcoes = {credentials: 'same-origin', signal: controle.signal};
            const respostas = await Promise.all([dadosLocais ? Promise.resolve(null) : fetch(api, opcoes), substituir ? fetch(url, opcoes) : Promise.resolve(null)]);
            if (!dadosLocais && !respostas[0].ok) throw new Error('Confira os filtros ou entre novamente para atualizar os dados.');
            let dados = dadosLocais ? null : await respostas[0].json();
            if (substituir) {
                if (respostas[1].redirected) {window.location.assign(respostas[1].url); return;}
                if (!respostas[1].ok) throw new Error('Não foi possível atualizar o painel.');
                const documento = new DOMParser().parseFromString(await respostas[1].text(), 'text/html');
                const resultados = documento.querySelector('[data-painel-resultados]');
                if (!resultados) throw new Error('Recarregue a página para continuar.');
                if (dadosLocais) dados = JSON.parse(resultados.querySelector('#dados-painel-iniciais').textContent);
                if (atual !== revisao) return;
                grafico?.destroy();
                painel.querySelector('[data-painel-resultados]')?.replaceWith(resultados);
                window.history.replaceState(null, '', url);
            }
            if (atual === revisao) desenhar(dados);
        } catch (erro) {
            if (erro.name === 'AbortError' || atual !== revisao) return;
            const aviso = painel.querySelector('[data-atualizacao]');
            if (aviso) aviso.textContent = erro.message;
        }
    }
    formulario.addEventListener('submit', evento => {evento.preventDefault(); clearTimeout(atraso); atualizar(true);});
    formulario.addEventListener('change', () => {clearTimeout(atraso); atualizar(true);});
    formulario.querySelector('[name=busca]')?.addEventListener('input', () => {clearTimeout(atraso); atraso = setTimeout(() => atualizar(true), 300);});
    atualizar(false);
})();
