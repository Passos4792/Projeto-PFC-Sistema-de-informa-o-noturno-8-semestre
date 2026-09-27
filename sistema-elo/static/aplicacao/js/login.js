//configuracao e eventos da tela
document.querySelector('.botao-olho').addEventListener('click', function() {
    const campo = document.getElementById('senha');
    const mostrar = campo.type === 'password';
    campo.type = mostrar ? 'text' : 'password';
    this.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
    this.setAttribute('aria-pressed', String(mostrar));
});
//-------------------------------------------------------------------------------------
