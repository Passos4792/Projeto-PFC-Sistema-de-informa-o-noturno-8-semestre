(() => {
    const form = document.querySelector('[data-busca-automatica]');
    if (!form) return;
    const input = form.elements.busca;
    const results = document.querySelector('[data-resultados-lista]');
    const count = document.querySelector('[data-contagem-lista]');
    const error = form.querySelector('[data-erro-busca]');
    let timer;
    let controller;
    let revision = 0;

    async function search(current) {
        controller = new AbortController();
        const url = new URL(window.location.href);
        url.searchParams.delete('pagina');
        const term = input.value.trim();
        const filterSearch = document.querySelector('[data-busca-filtros]');
        if (filterSearch) filterSearch.value = term;
        if (term) url.searchParams.set('busca', term);
        else url.searchParams.delete('busca');
        results.setAttribute('aria-busy', 'true');
        error.hidden = true;
        try {
            const response = await fetch(url, {signal: controller.signal});
            if (current !== revision) return;
            if (response.redirected) { window.location.assign(response.url); return; }
            if (!response.ok) throw new Error('Falha na busca');
            const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
            if (current !== revision) return;
            const nextResults = doc.querySelector('[data-resultados-lista]');
            const nextCount = doc.querySelector('[data-contagem-lista]');
            if (!nextResults || !nextCount) throw new Error('Resposta inválida');
            results.replaceChildren(...nextResults.childNodes);
            count.textContent = nextCount.textContent;
            history.replaceState(null, '', url);
        } catch (err) {
            if (current === revision && err.name !== 'AbortError') error.hidden = false;
        } finally {
            if (current === revision) results.removeAttribute('aria-busy');
        }
    }
    function schedule(delay) {
        clearTimeout(timer);
        controller?.abort();
        const current = ++revision;
        timer = setTimeout(() => search(current), delay);
    }
    input.addEventListener('input', () => schedule(250));
    form.addEventListener('submit', event => { event.preventDefault(); schedule(0); });
})();
