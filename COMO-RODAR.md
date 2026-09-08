# Como rodar o ELO

## 1. Instale os programas

- Python 3.12 ou superior
- MySQL Server 8
- MySQL Workbench
- VS Code

## 2. Crie o banco

No MySQL Workbench, execute:

```text
banco-de-dados-projeto/Criar Banco.sql
```

Se você já utilizou uma versão anterior do ELO, recrie o banco vazio antes de rodar as migrations desta versão.

## 3. Configure o `.env`

Na pasta `ELO-Django-simplificado`, faça uma cópia de `.env.example` com o nome `.env`.

Depois, coloque a senha do seu MySQL em:

```text
DB_PASSWORD=sua_senha_mysql
```

## 4. Crie o ambiente virtual

Abra o terminal na pasta principal e execute:

```powershell
python -m venv .venv
```

No PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se estiver usando o Prompt de Comando:

```text
.venv\Scripts\activate.bat
```

## 5. Instale as bibliotecas

```powershell
python -m pip install -r requirements.txt
```

## 6. Crie as tabelas

```powershell
cd sistema-elo
python manage.py migrate
```

## 7. Inicie o sistema

```powershell
python manage.py runserver
```

Abra:

```text
http://127.0.0.1:8000/
```

## Páginas principais

- `/professores/`
- `/alunos/`
- `/responsaveis/`
- `/vinculos/`
- `/metas/`
- `/atividades/`
- `/conteudos/`
- `/frequencias/`

A autenticação ainda não foi implementada.
