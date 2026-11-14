(() => {
    'use strict';

    const MAX_OPCOES_VISIVEIS = 120;
    const instancias = new WeakMap();
    let aberta = null;
    let contador = 0;

    const normalizar = (texto) => String(texto ?? '')
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();

    function rotuloDo(select) {
        const rotulo = select.labels?.[0]?.textContent?.replace(/\*/g, '').trim();
        return rotulo || select.getAttribute('aria-label') || select.name || 'opção';
    }

    function fechar({ devolverFoco = false } = {}) {
        if (!aberta) return;
        const instancia = aberta;
        aberta = null;
        instancia.painel.hidden = true;
        instancia.gatilho.setAttribute('aria-expanded', 'false');
        instancia.busca.setAttribute('aria-expanded', 'false');
        instancia.busca.removeAttribute('aria-activedescendant');
        if (devolverFoco && instancia.gatilho.isConnected && !instancia.gatilho.disabled) {
            instancia.gatilho.focus();
        }
    }

    function atualizarPosicao(instancia) {
        if (aberta !== instancia) return;
        const rect = instancia.gatilho.getBoundingClientRect();


        if (rect.bottom < 0 || rect.top > window.innerHeight || rect.width < 1) {
            fechar();
            return;
        }
        const margem = 8;
        const largura = Math.min(Math.max(rect.width, 230), window.innerWidth - margem * 2);
        const esquerda = Math.min(Math.max(rect.left, margem), window.innerWidth - largura - margem);
        const abaixo = window.innerHeight - rect.bottom - margem;
        const acima = rect.top - margem;
        const paraCima = abaixo < 210 && acima > abaixo;
        const altura = Math.max(110, Math.min(335, (paraCima ? acima : abaixo) - 6));
        Object.assign(instancia.painel.style, {
            left: `${esquerda}px`,
            width: `${largura}px`,
            maxHeight: `${altura}px`,
            top: paraCima ? `${Math.max(margem, rect.top - altura - 4)}px` : `${rect.bottom + 4}px`,
        });
    }

    function opcoesDo(select) {
        return [...select.options].map((option, indice) => {
            const grupo = option.parentElement?.tagName === 'OPTGROUP'
                ? option.parentElement.label : '';
            return {
                indice, texto: option.textContent.trim(), valor: option.value,
                busca: normalizar(`${grupo} ${option.textContent}`),
                grupo, desabilitada: option.disabled || !!option.closest('optgroup[disabled]'),
            };
        });
    }

    function sincronizar(instancia) {
        const { select, gatilho } = instancia;
        if (!select.isConnected) {
            if (aberta === instancia) fechar();
            instancia.painel.remove();
            return;
        }
        const opcao = select.selectedOptions[0];
        instancia.valor.textContent = opcao?.textContent.trim() || 'Selecione uma opção';
        gatilho.disabled = select.matches(':disabled');
        gatilho.setAttribute('aria-required', String(select.required));
        if (select.getAttribute('aria-invalid') === 'true') {
            gatilho.setAttribute('aria-invalid', 'true');
        } else {
            gatilho.removeAttribute('aria-invalid');
        }
        if (select.matches(':disabled') && aberta === instancia) fechar();
        if (aberta === instancia) {
            renderizar(instancia);
            atualizarPosicao(instancia);
        }
    }

    function destacar(instancia, indice) {
        const elementos = [...instancia.lista.querySelectorAll('[role="option"]')];
        if (!elementos.length) return;
        instancia.ativo = Math.min(Math.max(0, indice), elementos.length - 1);
        elementos.forEach((elemento, posicao) => {
            const atual = posicao === instancia.ativo;
            elemento.classList.toggle('elo-selecao-ativa', atual);
            if (atual) {
                instancia.busca.setAttribute('aria-activedescendant', elemento.id);
                elemento.scrollIntoView({block: 'nearest'});
            }
        });
    }

    function escolher(instancia, indice) {
        const opcao = instancia.select.options[indice];
        if (!opcao || opcao.disabled || opcao.closest('optgroup[disabled]')) return;
        const anterior = instancia.select.value;
        instancia.select.selectedIndex = indice;
        sincronizar(instancia);
        fechar({devolverFoco: true});
        if (anterior !== instancia.select.value) {


            instancia.select.dispatchEvent(new Event('input', {bubbles: true}));
            instancia.select.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }

    function renderizar(instancia) {
        if (aberta !== instancia) return;
        const termo = normalizar(instancia.busca.value);
        const palavras = termo.split(' ').filter(Boolean);
        const filtradas = opcoesDo(instancia.select).filter(item =>
            palavras.every(palavra => item.busca.includes(palavra))
        );
        const exibidas = filtradas.slice(0, MAX_OPCOES_VISIVEIS);
        const fragmento = document.createDocumentFragment();
        const identificador = instancia.identificador;
        exibidas.forEach((item, posicao) => {
            const opcao = document.createElement('div');
            opcao.className = 'elo-selecao-opcao';
            opcao.setAttribute('role', 'option');
            opcao.id = `${identificador}-opcao-${posicao}`;
            opcao.setAttribute('aria-selected', String(instancia.select.selectedIndex === item.indice));
            if (item.desabilitada) opcao.setAttribute('aria-disabled', 'true');
            opcao.textContent = item.grupo ? `${item.grupo} — ${item.texto}` : item.texto;
            opcao.addEventListener('pointermove', () => {
                if (!item.desabilitada && instancia.ativo !== posicao) destacar(instancia, posicao);
            });
            opcao.addEventListener('click', () => {
                if (!item.desabilitada) escolher(instancia, item.indice);
            });
            fragmento.appendChild(opcao);
        });
        instancia.lista.replaceChildren(fragmento);
        instancia.visiveis = exibidas;
        if (!filtradas.length) {
            const vazio = document.createElement('p');
            vazio.className = 'elo-selecao-vazio';
            vazio.textContent = 'Nenhuma opção encontrada';
            instancia.lista.appendChild(vazio);
        }
        instancia.contagem.textContent = filtradas.length > MAX_OPCOES_VISIVEIS
            ? `${MAX_OPCOES_VISIVEIS} de ${filtradas.length} opções. Digite para refinar a busca.`
            : `${filtradas.length} ${filtradas.length === 1 ? 'opção encontrada' : 'opções encontradas'}`;
        const selecionada = exibidas.findIndex(item => item.indice === instancia.select.selectedIndex && !item.desabilitada);
        const primeira = exibidas.findIndex(item => !item.desabilitada);
        instancia.ativo = -1;
        instancia.busca.removeAttribute('aria-activedescendant');
        if (selecionada !== -1 || primeira !== -1) {
            destacar(instancia, selecionada === -1 ? primeira : selecionada);
        }
    }

    function abrir(instancia, textoInicial = '') {
        if (!instancia.select.isConnected || instancia.select.matches(':disabled')) return;
        if (aberta) fechar();
        aberta = instancia;
        instancia.painel.hidden = false;
        instancia.gatilho.setAttribute('aria-expanded', 'true');
        instancia.busca.setAttribute('aria-expanded', 'true');
        instancia.busca.value = textoInicial;
        renderizar(instancia);
        atualizarPosicao(instancia);
        instancia.busca.focus();
    }

    function preparar(select) {
        if (instancias.has(select) || select.multiple || select.size > 1 || select.matches('[data-sem-busca]')) return;
        if (!select.closest('body')) return;
        const identificador = `elo-selecao-${++contador}`;
        const rotulo = rotuloDo(select);
        const caixa = document.createElement('span');
        caixa.className = 'elo-selecao';
        const gatilho = document.createElement('button');
        gatilho.type = 'button';
        gatilho.className = 'elo-selecao-gatilho';
        gatilho.setAttribute('role', 'combobox');
        gatilho.setAttribute('aria-haspopup', 'listbox');
        gatilho.setAttribute('aria-expanded', 'false');
        gatilho.setAttribute('aria-controls', `${identificador}-lista`);
        gatilho.setAttribute('aria-label', `Selecionar ${rotulo}`);
        const valor = document.createElement('span');
        valor.className = 'elo-selecao-valor';
        const seta = document.createElement('span');
        seta.className = 'elo-selecao-seta';
        seta.setAttribute('aria-hidden', 'true');
        seta.textContent = '⌄';
        gatilho.append(valor, seta);

        select.parentNode.insertBefore(caixa, select);
        caixa.append(select, gatilho);
        select.classList.add('elo-selecao-original');
        select.tabIndex = -1;
        select.setAttribute('aria-hidden', 'true');

        const painel = document.createElement('div');
        painel.className = 'elo-selecao-painel';
        painel.hidden = true;
        const busca = document.createElement('input');
        busca.type = 'search';
        busca.className = 'elo-selecao-busca';
        busca.placeholder = 'Digite para pesquisar...';
        busca.autocomplete = 'off';
        busca.setAttribute('role', 'searchbox');
        busca.setAttribute('aria-label', `Pesquisar ${rotulo}`);
        busca.setAttribute('aria-controls', `${identificador}-lista`);
        busca.setAttribute('aria-expanded', 'false');
        const lista = document.createElement('div');
        lista.className = 'elo-selecao-lista';
        lista.id = `${identificador}-lista`;
        lista.setAttribute('role', 'listbox');
        lista.setAttribute('aria-label', `Opções de ${rotulo}`);
        const contagem = document.createElement('p');
        contagem.className = 'elo-selecao-contagem';
        contagem.setAttribute('aria-live', 'polite');
        painel.append(busca, lista, contagem);
        document.body.appendChild(painel);
        const instancia = {select, caixa, gatilho, valor, painel, busca, lista, contagem, identificador, ativo: -1, visiveis: []};
        instancias.set(select, instancia);
        sincronizar(instancia);

        gatilho.addEventListener('click', () => {
            if (aberta === instancia) fechar({devolverFoco: true});
            else abrir(instancia);
        });
        gatilho.addEventListener('keydown', evento => {
            if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(evento.key)) {
                evento.preventDefault();
                abrir(instancia);
            } else if (evento.key.length === 1 && !evento.ctrlKey && !evento.metaKey && !evento.altKey) {
                evento.preventDefault();
                abrir(instancia, evento.key);
            }
        });
        busca.addEventListener('input', () => renderizar(instancia));
        busca.addEventListener('keydown', evento => {
            if (evento.key === 'Escape') {
                evento.preventDefault();
                fechar({devolverFoco: true});
            } else if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
                evento.preventDefault();
                const passo = evento.key === 'ArrowDown' ? 1 : -1;
                const proximos = instancia.visiveis
                    .map((item, indice) => !item.desabilitada ? indice : -1).filter(indice => indice !== -1);
                if (proximos.length) {
                    const atual = proximos.indexOf(instancia.ativo);
                    const proximo = proximos[(atual + passo + proximos.length) % proximos.length];
                    destacar(instancia, proximo);
                }
            } else if (evento.key === 'Enter') {
                evento.preventDefault();
                const item = instancia.visiveis[instancia.ativo];
                if (item && !item.desabilitada) escolher(instancia, item.indice);
            } else if (evento.key === 'Tab') {
                fechar();
            }
        });
        select.addEventListener('change', () => sincronizar(instancia));
        select.addEventListener('invalid', evento => {

            evento.preventDefault();
            gatilho.setAttribute('aria-invalid', 'true');
            gatilho.focus();
        });
        instancia.rotulos = [];
        [...(select.labels || [])].forEach(label => {
            const aoClicar = evento => {
                if (evento.target.closest('a, button, input')) return;
                evento.preventDefault();
                abrir(instancia);
            };
            label.addEventListener('click', aoClicar);
            instancia.rotulos.push([label, aoClicar]);
        });
    }

    function examinar(raiz) {
        if (!(raiz instanceof Element)) return;
        if (raiz.matches('select')) preparar(raiz);
        raiz.querySelectorAll?.('select').forEach(preparar);
    }

    document.querySelectorAll('select').forEach(preparar);


    const observador = new MutationObserver(mutacoes => {
        const atualizar = new Set();
        for (const mutacao of mutacoes) {
            if (mutacao.type === 'attributes') {
                if (mutacao.target.matches('select')) atualizar.add(mutacao.target);
                continue;
            }
            const select = mutacao.target.closest?.('select');
            if (select) atualizar.add(select);
            mutacao.addedNodes.forEach(no => {
                if (no.nodeType === 1) examinar(no);
            });
            mutacao.removedNodes.forEach(no => {
                if (no.nodeType !== 1 || no.isConnected) return;
                const removidos = no.matches?.('select') ? [no] : [...no.querySelectorAll('select')];
                removidos.forEach(campo => {
                    if (campo.isConnected) return;
                    const instancia = instancias.get(campo);
                    if (!instancia) return;
                    if (aberta === instancia) fechar();
                    instancia.painel.remove();
                    instancia.caixa.remove();
                    instancia.rotulos?.forEach(([rotulo, callback]) => rotulo.removeEventListener('click', callback));
                    instancias.delete(campo);
                });
            });
        }
        atualizar.forEach(select => {
            if (!instancias.has(select)) preparar(select);
            else sincronizar(instancias.get(select));
        });
    });
    observador.observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['disabled', 'required', 'aria-invalid']});

    document.addEventListener('reset', evento => {

        const formulario = evento.target;
        if (!formulario.matches?.('form')) return;
        window.setTimeout(() => {
            formulario.querySelectorAll('select').forEach(campo => {
                const instancia = instancias.get(campo);
                if (instancia) sincronizar(instancia);
            });
        }, 0);
    }, true);

    document.addEventListener('pointerdown', evento => {
        if (!aberta) return;
        if (!aberta.painel.contains(evento.target) && !aberta.gatilho.contains(evento.target)) fechar();
    }, true);
    document.addEventListener('focusin', evento => {
        if (aberta && !aberta.painel.contains(evento.target) && !aberta.gatilho.contains(evento.target)) fechar();
    });
    window.addEventListener('resize', () => { if (aberta) atualizarPosicao(aberta); });
    window.addEventListener('scroll', () => { if (aberta) atualizarPosicao(aberta); }, true);


    window.ELOSelectSearch = {
        refresh(select) {
            const instancia = instancias.get(select);
            if (instancia) sincronizar(instancia);
        },
    };
})();
