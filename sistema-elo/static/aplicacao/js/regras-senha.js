(() => {
    const SIMILARIDADE_MAXIMA = 0.7;
    const TEXTOS = {ok: ' — atendido', falta: ' — ainda falta', neutro: ''};
    let listaComuns = null;
    let carregandoComuns = null;


    function carregarComuns(url) {
        if (!carregandoComuns) {
            carregandoComuns = fetch(url, {credentials: 'same-origin'})
                .then(resposta => resposta.ok ? resposta.text() : Promise.reject(new Error('lista indisponível')))
                .then(texto => { listaComuns = new Set(texto.split('\n').filter(Boolean)); })
                .catch(() => { listaComuns = null; });
        }
        return carregandoComuns;
    }


    function semelhanca(a, b) {
        if (!a.length && !b.length) return 1;
        const disponiveis = new Map();
        for (const letra of b) disponiveis.set(letra, (disponiveis.get(letra) || 0) + 1);
        let iguais = 0;
        for (const letra of a) {
            const restantes = disponiveis.get(letra) || 0;
            if (restantes > 0) { iguais += 1; disponiveis.set(letra, restantes - 1); }
        }
        return 2 * iguais / (a.length + b.length);
    }

    function parecidaComDados(senha, dados) {
        const minuscula = senha.toLowerCase();
        return dados.some(valor => {
            const texto = valor.toLowerCase();
            const partes = texto.split(/[^\p{L}\p{N}_]+/u).concat(texto);
            return partes.some(parte => {
                if (!parte) return false;
                const muitoCurta = minuscula.length >= 10 * parte.length &&
                    parte.length < SIMILARIDADE_MAXIMA / 2 * minuscula.length;
                return !muitoCurta && semelhanca(minuscula, parte) >= SIMILARIDADE_MAXIMA;
            });
        });
    }

    document.querySelectorAll('[data-regras-senha]').forEach(bloco => {
        const senha = document.getElementById(bloco.dataset.campoSenha);
        if (!senha) return;
        const confirmacao = document.getElementById(bloco.dataset.campoConfirmacao);
        const minimo = Number(bloco.dataset.tamanhoMinimo) || 8;
        const camposPessoais = (bloco.dataset.camposPessoais || '').split(' ')
            .map(id => document.getElementById(id)).filter(Boolean);
        const dadosFixos = ['pessoalUsuario', 'pessoalNome', 'pessoalSobrenome', 'pessoalEmail']
            .map(chave => bloco.dataset[chave]).filter(Boolean);

        function marcar(regra, estado) {
            const item = bloco.querySelector(`[data-regra="${regra}"]`);
            if (!item) return;
            item.dataset.estado = estado;
            item.querySelector('[data-estado-texto]').textContent = TEXTOS[estado];
        }

        function conferir() {
            const valor = senha.value;
            const vazio = !valor;
            const dados = dadosFixos.concat(camposPessoais.map(campo => campo.value.trim()).filter(Boolean));
            marcar('tamanho', vazio ? 'neutro' : valor.length >= minimo ? 'ok' : 'falta');
            marcar('numerica', vazio ? 'neutro' : /^\d+$/.test(valor) ? 'falta' : 'ok');
            marcar('pessoal', vazio ? 'neutro' : parecidaComDados(valor, dados) ? 'falta' : 'ok');
            if (vazio || !listaComuns) marcar('comum', 'neutro');
            else marcar('comum', listaComuns.has(valor.toLowerCase().trim()) ? 'falta' : 'ok');
            if (confirmacao) {
                marcar('confirmacao', !confirmacao.value || vazio ? 'neutro'
                    : confirmacao.value === valor ? 'ok' : 'falta');
            }
            if (!vazio && !listaComuns && bloco.dataset.listaComuns) {
                carregarComuns(bloco.dataset.listaComuns).then(() => { if (listaComuns) conferir(); });
            }
        }

        [senha, confirmacao, ...camposPessoais].forEach(campo => campo?.addEventListener('input', conferir));
        conferir();
    });
})();
