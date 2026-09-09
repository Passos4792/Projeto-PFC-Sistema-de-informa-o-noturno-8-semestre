# Projeto-PFC-Sistema-de-informa-o-noturno-8-semestre
Projeto final do curso de sistema de informação noturno realizado na Universidade Mogi das Cruzes no segundo semestre do ano de 2026.
Auxiliador de acompanhamento de crianças atípicas pela escola e responsáveis.

## Tecnologias utilizadas

- Python
- Django
- MySQL
- HTML
- CSS
- JavaScript

## Estrutura do projeto

- `sistema-elo/`: código principal do sistema
- `aplicacao/`: regras, cadastros e funcionalidades
- `configuracao/`: configurações do Django
- `templates/`: páginas HTML
- `static/`: CSS, JavaScript e imagens
- `banco-de-dados-projeto/`: script de criação do banco
- `requirements.txt`: bibliotecas necessárias
- `.env.example`: exemplo de configuração do banco

## Como executar

1. Criar o banco `elo_db` no MySQL.
2. Criar o arquivo `.env` com os dados do banco.
3. Instalar as dependências:

```bash
python -m pip install -r requirements.txt
