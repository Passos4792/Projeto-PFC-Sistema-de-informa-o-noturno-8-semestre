document.querySelectorAll('select[data-filtro-dashboard]').forEach((campo) => {
    campo.addEventListener('change', () => campo.form?.requestSubmit());
});
