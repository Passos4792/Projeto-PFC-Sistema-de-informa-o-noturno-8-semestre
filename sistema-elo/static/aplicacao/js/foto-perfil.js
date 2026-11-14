document.addEventListener('DOMContentLoaded', function () {
    const campo = document.getElementById('id_foto_perfil');
    const nome = document.getElementById('foto-nome-arquivo');
    if (!campo || !nome) return;
    campo.addEventListener('change', function () {
        const arquivo = campo.files && campo.files[0];
        nome.textContent = arquivo ? arquivo.name : 'Nenhum arquivo selecionado';
        nome.title = arquivo ? arquivo.name : '';
    });
});
