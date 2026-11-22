"""Confere integridade estática do ELO sem iniciar Django ou acessar o banco."""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
import subprocess
import sys


RAIZ = Path(__file__).resolve().parent
NOVAS = {
    'atividade-cancelar': 'ROTAS_AEE',
    'solicitacao-senha-negar': 'ROTAS_SOLICITACOES_SENHA',
    'privacidade-exportar-menor': 'ROTAS_CONTA',
    'privacidade-excluir-menor': 'ROTAS_CONTA',
}


def nomes_de_rotas(codigo):
    encontrados = {}
    for chamada in ast.walk(codigo):
        if not isinstance(chamada, ast.Call):
            continue
        if not isinstance(chamada.func, ast.Name) or chamada.func.id != 'path':
            continue
        identificador = next((k.value.value for k in chamada.keywords
                              if k.arg == 'name' and isinstance(k.value, ast.Constant)), None)
        if identificador and chamada.args and isinstance(chamada.args[0], ast.Constant):
            encontrados[identificador] = chamada.args[0].value
    return encontrados


def conjuntos_de_acesso(codigo):
    grupos = {}
    for atribuicao in codigo.body:
        if not isinstance(atribuicao, ast.Assign) or len(atribuicao.targets) != 1:
            continue
        alvo = atribuicao.targets[0]
        if not isinstance(alvo, ast.Name) or not alvo.id.startswith('ROTAS_'):
            continue
        valor = atribuicao.value
        if isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name) and valor.func.id == 'frozenset':
            grupos[alvo.id] = set(ast.literal_eval(valor.args[0]))
        elif (isinstance(valor, ast.BinOp) and isinstance(valor.op, ast.BitOr)
              and isinstance(valor.left, ast.Name) and isinstance(valor.right, ast.Set)):
            grupos[alvo.id] = grupos[valor.left.id] | set(ast.literal_eval(valor.right))
    return grupos


def entradas_da_matriz(codigo):
    for funcao in ast.walk(codigo):
        if not isinstance(funcao, ast.FunctionDef) or funcao.name != 'argumentos':
            continue
        for no in funcao.body:
            if isinstance(no, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'alvo'
                                                   for t in no.targets) and isinstance(no.value, ast.Dict):
                return {k.value for k in no.value.keys if isinstance(k, ast.Constant)}
    return set()


def principal():
    avisos = []
    resultados = []
    arquivos = sorted(RAIZ.rglob('*.py'))
    codigos = {}
    for arquivo in arquivos:
        try:
            codigos[arquivo] = ast.parse(arquivo.read_text(encoding='utf-8'), filename=str(arquivo))
        except (SyntaxError, UnicodeError) as erro:
            avisos.append(f'Python inválido em {arquivo.relative_to(RAIZ)}: {erro}')
    resultados.append(f'Python: {len(codigos)}/{len(arquivos)} arquivos analisados sem erro de sintaxe.')

    rotas = nomes_de_rotas(codigos[RAIZ / 'aplicacao/urls.py'])
    grupos = conjuntos_de_acesso(codigos[RAIZ / 'aplicacao/servicos/acesso.py'])
    classificadas = set().union(*grupos.values())
    classificadas.update({'inicio', 'logout', 'trocar-senha', 'aceitar-termos', 'aluno-inicio', 'aguardando-autorizacao', 'autorizar-acesso-menor'})
    nao_classificadas = sorted(n for n in rotas if n not in classificadas and not n.startswith('api-'))
    if nao_classificadas:
        avisos.append('Rotas não classificadas: ' + ', '.join(nao_classificadas))
    resultados.append(f'Permissões: {len(rotas)} rotas nomeadas; {len(nao_classificadas)} sem classificação.')

    matriz = entradas_da_matriz(codigos[RAIZ / 'testes/seguranca/test_matriz_de_acesso.py'])
    for nome, grupo in NOVAS.items():
        if nome not in rotas:
            avisos.append('Rota nova ausente: ' + nome)
        if nome not in grupos.get(grupo, ()):
            avisos.append('Rota sem permissão esperada: ' + nome + ' em ' + grupo)
        if nome not in matriz:
            avisos.append('Rota ausente da matriz com identificadores: ' + nome)
    resultados.append('Quatro rotas novas: URL, perfil e matriz de acesso conferidos.')

    sem_pk = sorted(nome for nome, caminho in rotas.items()
                    if '<int:pk>' in caminho and nome not in matriz)
    if sem_pk:
        avisos.append('A matriz não define identificador para: ' + ', '.join(sem_pk))
    resultados.append(f'Matriz de acesso: {len(sem_pk)} rotas com pk sem identificador.')

    templates = sorted((RAIZ / 'templates').rglob('*.html'))
    ilegais = re.compile(r'on(?:click|change|submit)\s*=|<script\s*>', re.IGNORECASE)
    for arquivo in templates:
        texto = arquivo.read_text(encoding='utf-8')
        if ilegais.search(texto):
            avisos.append('HTML com script embutido: ' + str(arquivo.relative_to(RAIZ)))
    resultados.append(f'Templates: {len(templates)} arquivos HTML sem padrões de script embutido proibidos.')

    javascript = sorted((RAIZ / 'static').rglob('*.js'))
    node = shutil.which('node')
    if node:
        for arquivo in javascript:
            processo = subprocess.run([node, '--check', str(arquivo)], capture_output=True, text=True)
            if processo.returncode:
                avisos.append('Erro de sintaxe JS: ' + str(arquivo.relative_to(RAIZ)) + '\n' + processo.stderr)
        resultados.append(f'JavaScript: {len(javascript)} arquivos verificados pelo Node.js.')
    else:
        resultados.append(f'JavaScript: {len(javascript)} arquivos encontrados; Node.js indisponível para validar sintaxe.')

    teste_count = sum(isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and no.name.startswith('test_')
                      for arquivo, codigo in codigos.items() if 'testes' in arquivo.relative_to(RAIZ).parts
                      for no in ast.walk(codigo))
    resultados.append(f'Testes Django: {teste_count} métodos definidos; não executados por este verificador.')

    data = datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec='seconds')
    relatorio = ['ELO | Verificação estática | ' + data, *resultados,
                 'Ocorrências: ' + str(len(avisos)), *(f'- {aviso}' for aviso in avisos),
                 'Importante: esta validação não substitui python executar_testes.py.']
    texto = '\n'.join(relatorio) + '\n'
    print(texto)
    pasta = RAIZ / 'relatorios_testes'
    pasta.mkdir(exist_ok=True)
    (pasta / 'checagem_estatica.txt').write_text(texto, encoding='utf-8')
    return 0 if not avisos else 1


if __name__ == '__main__':
    sys.exit(principal())
