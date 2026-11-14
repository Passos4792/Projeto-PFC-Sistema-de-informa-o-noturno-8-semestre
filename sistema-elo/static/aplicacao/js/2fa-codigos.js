'use strict';
const botaoImprimir = document.getElementById('elo-imprimir-codigos');
if (botaoImprimir) {
    botaoImprimir.addEventListener('click', () => window.print());
}
