import argparse
import os
from pathlib import Path
import subprocess
import sys


def principal():
    parser = argparse.ArgumentParser(description='Testes automatizados do ELO.')
    parser.add_argument('--mysql', action='store_true',
                        help='Cria e remove test_elo_atualizado no MySQL configurado no .env.')
    parser.add_argument('modulos', nargs='*', default=['testes'])
    args = parser.parse_args()
    raiz = Path(__file__).resolve().parent
    (raiz / 'relatorios_testes').mkdir(exist_ok=True)
    ambiente = os.environ.copy()
    ambiente['DJANGO_SETTINGS_MODULE'] = 'testes.configuracao'
    ambiente['ELO_TEST_MYSQL'] = '1' if args.mysql else '0'
    ambiente['PYTHONIOENCODING'] = 'utf-8'
    try:
        import coverage
    except ImportError:
        print('Instale as dependências: python -m pip install -r requirements.txt')
        return 1
    comando = [sys.executable, '-m', 'coverage']
    testes = subprocess.run(comando + ['run', 'manage.py', 'test', *args.modulos,
        '--settings=testes.configuracao', '--verbosity=2'], cwd=raiz, env=ambiente)
    relatorio = subprocess.run(comando + ['report'], cwd=raiz, env=ambiente)
    html = subprocess.run(comando + ['html'], cwd=raiz, env=ambiente)
    xml = subprocess.run(comando + ['xml'], cwd=raiz, env=ambiente)
    return 1 if any(resultado.returncode for resultado in (testes, relatorio, html, xml)) else 0


if __name__ == '__main__':
    sys.exit(principal())
