"""Executa os testes do ELO e salva a evidência da execução da equipe."""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def executar(comando, raiz, ambiente, log):
    processo = subprocess.Popen(
        comando, cwd=raiz, env=ambiente,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', bufsize=1,
    )
    linhas = []
    with log.open('a', encoding='utf-8') as arquivo:
        arquivo.write('\n$ ' + shlex.join(comando) + '\n')
        for linha in processo.stdout:
            print(linha, end='', flush=True)
            arquivo.write(linha)
            linhas.append(linha)
    return processo.wait(), ''.join(linhas)


def principal():
    parser = argparse.ArgumentParser(description='Testes automatizados do ELO.')
    parser.add_argument('--mysql', action='store_true',
                        help='Cria e remove test_elo_atualizado no MySQL configurado no .env.')
    parser.add_argument('modulos', nargs='*', default=['testes'])
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parent
    pasta = raiz / 'relatorios_testes'
    pasta.mkdir(exist_ok=True)
    ambiente = os.environ.copy()
    ambiente['DJANGO_SETTINGS_MODULE'] = 'testes.configuracao'
    ambiente['ELO_TEST_MYSQL'] = '1' if args.mysql else '0'
    ambiente['PYTHONIOENCODING'] = 'utf-8'
    data = datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec='seconds')
    base = [sys.executable, '-m', 'coverage']
    teste = base + ['run', 'manage.py', 'test', *args.modulos,
                    '--settings=testes.configuracao', '--verbosity=2']
    log = pasta / 'execucao_completa.txt'
    log.write_text('ELO - execução de testes\nInício (America/Sao_Paulo): ' + data + '\n',
                   encoding='utf-8')
    try:
        import coverage  # noqa: F401
    except ImportError:
        print('Instale as dependências: python -m pip install -r requirements.txt')
        (pasta / 'resultado_execucao.txt').write_text(
            'Início: ' + data + '\nExecução não iniciada: coverage não está instalado.\n',
            encoding='utf-8')
        return 1

    testes_codigo, testes_saida = executar(teste, raiz, ambiente, log)
    contagem = re.search(r'Ran (\d+) tests? in [^\n]+', testes_saida)
    if contagem:
        report_codigo, report_saida = executar(base + ['report'], raiz, ambiente, log)
        html_codigo, _ = executar(base + ['html'], raiz, ambiente, log)
        xml_codigo, _ = executar(base + ['xml'], raiz, ambiente, log)
    else:
        report_codigo = html_codigo = xml_codigo = 1
        report_saida = 'Cobertura não calculada: os testes não chegaram a executar.'

    fim = datetime.now(timezone(timedelta(hours=-3))).isoformat(timespec='seconds')
    marcador = re.search(r'(?m)^(OK(?: \(skipped=\d+\))?|FAILED \([^\n]+\))\s*$', testes_saida)
    total = re.search(r'(?m)^TOTAL\s+[^\n]+$', report_saida)
    aprovado = all(codigo == 0 for codigo in (testes_codigo, report_codigo, html_codigo, xml_codigo))
    resumo = [
        'ELO - resultado automático da execução',
        'Início (America/Sao_Paulo): ' + data,
        'Fim (America/Sao_Paulo): ' + fim,
        'Comando: ' + shlex.join(teste),
        'Banco de testes: ' + ('MySQL isolado' if args.mysql else 'SQLite em memória'),
        'Testes executados: ' + (contagem.group(1) if contagem else 'não determinado'),
        'Resultado do Django: ' + (marcador.group(1) if marcador else 'não determinado'),
        'Código de retorno dos testes: ' + str(testes_codigo),
        'Cobertura: ' + (total.group(0) if total else 'não determinada'),
        'Códigos (relatório, HTML, XML): ' + ', '.join(map(str, (report_codigo, html_codigo, xml_codigo))),
        'Situação geral: ' + ('APROVADA' if aprovado else 'NÃO APROVADA'),
        'Evidência completa: relatorios_testes/execucao_completa.txt',
    ]
    (pasta / 'resultado_execucao.txt').write_text('\n'.join(resumo) + '\n', encoding='utf-8')
    data_br = datetime.fromisoformat(data).strftime('%d/%m/%Y')
    if aprovado and contagem and total:
        trecho = (
            f'Em {data_br}, a equipe executou a suíte automatizada do ELO no ambiente '
            f'de testes com {("MySQL isolado" if args.mysql else "SQLite em memória")}, pelo comando python executar_testes.py{(" --mysql" if args.mysql else "")}. '
            f'A execução compreendeu {contagem.group(1)} testes e terminou com resultado OK, '
            f'sem falhas ou erros. O relatório do coverage registrou cobertura total de '
            f'{total.group(0).split()[-1]}. A execução utilizou as configurações '
            f'testes.configuracao, isolamento dos arquivos temporários e simulação da integração '
            f'externa com o Google Agenda. As evidências foram geradas em '
            f'relatorios_testes/resultado_execucao.txt, execucao_completa.txt, html/index.html e coverage.xml. '
            f'Esses resultados correspondem à execução da equipe sobre esta versão do código.'
        )
    else:
        trecho = (
            f'Em {data_br}, a equipe iniciou a suíte automatizada do ELO pelo comando '
            f'python executar_testes.py, mas a execução não foi aprovada. '
            f'Resultado observado: {marcador.group(1) if marcador else "execução não concluída"}. '
            f'O total executado foi {contagem.group(1) if contagem else "não determinado"} testes. '
            f'O log integral foi preservado em relatorios_testes/execucao_completa.txt. '
            f'Este resultado não deve ser descrito como suíte aprovada.'
        )
    (pasta / 'trecho_secao_3_8_apos_testes.txt').write_text(trecho + '\n', encoding='utf-8')
    print('\n'.join(resumo))
    return 0 if aprovado else 1


if __name__ == '__main__':
    sys.exit(principal())
