from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


AZUL = colors.HexColor('#294664')
AZUL_MEDIO = colors.HexColor('#4776AD')
TEXTO = colors.HexColor('#43566E')
CINZA = colors.HexColor('#E3EBF3')


def _paragrafo_seguro(valor):
    texto = str(valor if valor is not None else '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not texto:
        texto = 'Não informado'
    return escape(texto).replace('\n', '<br/>')


def _rodape(canvas, documento):
    canvas.saveState()
    largura, _ = A4
    canvas.setStrokeColor(CINZA)
    canvas.line(18 * mm, 18 * mm, largura - 18 * mm, 18 * mm)
    canvas.setFillColor(TEXTO)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(18 * mm, 13 * mm, 'ELO - Registro pedagógico')
    canvas.drawRightString(largura - 18 * mm, 13 * mm, f'Página {documento.page}')
    canvas.restoreState()


def gerar_pdf_registro(item, linhas, *, documento):
    titulo = item.get_tipo_display() if documento else item.titulo
    metadados = [
        ('Estudante', item.aluno.nome_completo),
        ('Professor(a)', item.professor.nome_completo),
        ('Situação', item.get_situacao_display()),
    ]
    if documento:
        metadados.append(('Ano letivo', str(item.ano_letivo)))
        if item.bimestre:
            metadados.append(('Bimestre', f'{item.bimestre}º bimestre'))
    else:
        metadados.append(('Data de referência', item.data_referencia.strftime('%d/%m/%Y')))

    estilos = {
        'marca': ParagraphStyle('MarcaELO', fontName='Helvetica-Bold', fontSize=16,
                                leading=21, textColor=AZUL_MEDIO, spaceAfter=9),
        'titulo': ParagraphStyle('TituloELO', fontName='Helvetica-Bold', fontSize=16,
                                 leading=21, textColor=AZUL, spaceAfter=12,
                                 splitLongWords=True),
        'rotulo': ParagraphStyle('RotuloELO', fontName='Helvetica-Bold', fontSize=9.4,
                                 leading=13, textColor=AZUL),
        'metadado': ParagraphStyle('MetadadoELO', fontName='Helvetica', fontSize=9.4,
                                   leading=13, textColor=TEXTO),
        'secao': ParagraphStyle('SecaoELO', fontName='Helvetica-Bold', fontSize=11.5,
                                leading=16, textColor=AZUL, spaceAfter=6,
                                splitLongWords=True),
        'conteudo': ParagraphStyle('ConteudoELO', fontName='Helvetica', fontSize=10,
                                   leading=16, textColor=TEXTO, spaceAfter=11,
                                   splitLongWords=True),
        'observacao': ParagraphStyle('ObservacaoELO', fontName='Helvetica', fontSize=8.2,
                                     leading=12, textColor=TEXTO),
    }
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm,
                            leftMargin=20 * mm, topMargin=21 * mm,
                            bottomMargin=26 * mm, title=str(titulo), author='ELO')
    elementos = [
        Paragraph('ELO', estilos['marca']),
        Paragraph(_paragrafo_seguro(titulo), estilos['titulo']),
    ]
    linhas_metadados = [
        [Paragraph(_paragrafo_seguro(rotulo), estilos['rotulo']),
         Paragraph(_paragrafo_seguro(valor), estilos['metadado'])]
        for rotulo, valor in metadados
    ]
    tabela = Table(linhas_metadados, colWidths=[38 * mm, 128 * mm], hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F8FB')),
        ('BOX', (0, 0), (-1, -1), 0.5, CINZA),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.extend([tabela, Spacer(1, 13 * mm)])

    for rotulo, valor in linhas:
        secao = Paragraph(_paragrafo_seguro(rotulo), estilos['secao'])
        conteudo = Paragraph(_paragrafo_seguro(valor), estilos['conteudo'])
        if len(str(valor or '')) < 450:
            elementos.append(KeepTogether([secao, conteudo]))
        else:
            elementos.extend([secao, conteudo])
        elementos.append(HRFlowable(width='100%', thickness=0.5, color=CINZA, spaceAfter=12))
    elementos.extend([
        Spacer(1, 5 * mm),
        Paragraph('Registro pedagógico do ELO. Este arquivo não é uma assinatura '
                  'eletrônica oficial e não substitui a validação exigida pela escola.',
                  estilos['observacao']),
    ])
    pdf.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()


def gerar_pdf_prontuario_aluno(aluno, documentos, relatorios):
    from django.utils import timezone
    from reportlab.platypus import PageBreak
    from aplicacao.forms.documentos import CAMPOS_DOCUMENTOS

    estilos = {
        'marca': ParagraphStyle('CapaMarcaELO', fontName='Helvetica-Bold', fontSize=19,
                                leading=24, textColor=AZUL_MEDIO, spaceAfter=14),
        'titulo': ParagraphStyle('CapaTituloELO', fontName='Helvetica-Bold', fontSize=17,
                                 leading=23, textColor=AZUL, spaceAfter=14),
        'secao': ParagraphStyle('ProntuarioSecaoELO', fontName='Helvetica-Bold', fontSize=13,
                                leading=19, textColor=AZUL, spaceAfter=9, splitLongWords=True),
        'rotulo': ParagraphStyle('ProntuarioRotuloELO', fontName='Helvetica-Bold', fontSize=10,
                                 leading=14, textColor=AZUL, spaceBefore=12, spaceAfter=4,
                                 splitLongWords=True),
        'texto': ParagraphStyle('ProntuarioTextoELO', fontName='Helvetica', fontSize=10,
                                leading=16, textColor=TEXTO, spaceAfter=7, splitLongWords=True),
        'nota': ParagraphStyle('ProntuarioNotaELO', fontName='Helvetica', fontSize=8.5,
                               leading=13, textColor=TEXTO, spaceAfter=10),
    }
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=22*mm, bottomMargin=26*mm,
                            title=f'Histórico pedagógico - {aluno.nome_completo}', author='ELO')
    pagina = [
        Paragraph('ELO', estilos['marca']),
        Paragraph('Histórico pedagógico do aluno', estilos['titulo']),
        Paragraph(f'<b>Aluno:</b> {_paragrafo_seguro(aluno.nome_completo)}', estilos['texto']),
        Paragraph(f'<b>Situação:</b> Inativo', estilos['texto']),
        Paragraph(f'<b>Inativado em:</b> {timezone.localtime(aluno.inativado_em):%d/%m/%Y}', estilos['texto']),
        Paragraph(f'<b>Disponível até:</b> {aluno.documentos_disponiveis_ate:%d/%m/%Y}', estilos['texto']),
        Paragraph(f'<b>Documentos:</b> {len(documentos)}', estilos['texto']),
        Paragraph(f'<b>Relatórios:</b> {len(relatorios)}', estilos['texto']),
        Spacer(1, 7*mm),
        Paragraph('Este arquivo reúne os registros cadastrados no ELO no momento da exportação, '
                  'inclusive rascunhos e itens internos. Contém informações restritas de uma criança '
                  'ou adolescente e deve ser compartilhado somente com pessoas autorizadas.', estilos['nota']),
        Paragraph('O arquivo é gerado sob demanda. Não constitui assinatura eletrônica oficial nem '
                  'substitui a validação pela instituição de ensino.', estilos['nota']),
    ]
    if not documentos and not relatorios:
        pagina.append(Paragraph('Não existem documentos ou relatórios pedagógicos cadastrados '
                                'para este aluno até a data da exportação.', estilos['texto']))

    def linha(rotulo, valor):
        pagina.append(Paragraph(_paragrafo_seguro(rotulo), estilos['rotulo']))
        pagina.append(Paragraph(_paragrafo_seguro(valor), estilos['texto']))

    for indice, doc in enumerate(documentos, 1):
        pagina.append(PageBreak())
        pagina.append(Paragraph(f'Documento {indice} de {len(documentos)}', estilos['nota']))
        pagina.append(Paragraph(_paragrafo_seguro(doc.get_tipo_display()), estilos['secao']))
        linha('Professor(a)', doc.professor.nome_completo)
        linha('Ano letivo', doc.ano_letivo)
        if doc.bimestre:
            linha('Bimestre', f'{doc.bimestre}º bimestre')
        linha('Situação do documento', doc.get_situacao_display())
        linha('Criado em', timezone.localtime(doc.criado_em).strftime('%d/%m/%Y %H:%M'))
        linha('Última atualização', timezone.localtime(doc.atualizado_em).strftime('%d/%m/%Y %H:%M'))
        campos = doc.campos if isinstance(doc.campos, dict) else {}
        chaves = set()
        for chave, rotulo in CAMPOS_DOCUMENTOS.get(doc.tipo, []):
            chaves.add(chave)
            linha(rotulo, campos.get(chave, ''))
        for chave, valor in campos.items():
            if chave not in chaves:
                linha(str(chave).replace('_', ' ').capitalize(), valor)

    for indice, rel in enumerate(relatorios, 1):
        pagina.append(PageBreak())
        pagina.append(Paragraph(f'Relatório {indice} de {len(relatorios)}', estilos['nota']))
        pagina.append(Paragraph(_paragrafo_seguro(rel.titulo), estilos['secao']))
        linha('Professor(a)', rel.professor.nome_completo)
        linha('Período', rel.periodo)
        linha('Data de referência', rel.data_referencia.strftime('%d/%m/%Y'))
        linha('Situação do relatório', rel.get_situacao_display())
        linha('Criado em', timezone.localtime(rel.criado_em).strftime('%d/%m/%Y %H:%M'))
        linha('Última atualização', timezone.localtime(rel.atualizado_em).strftime('%d/%m/%Y %H:%M'))
        linha('Relato pedagógico', rel.relato)

    pdf.build(pagina, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
