import re
import io
import pandas as pd
import pdfplumber
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Expressão regular para capturar os lançamentos de cada linha do extrato
ROW_PATTERN = re.compile(
    r'^(\d{2}/\d{4})\s+'                  # 1: Comp. Apuração (ex: 08/2026)
    r'(\d{2}/\d{2}/\d{4})\s+'            # 2: Vencimento (ex: 18/09/2026)
    r'(.+?)\s+'                          # 3: Nome Trabalhador
    r'([A-Z0-9]+)\s+'                    # 4: Matrícula (ex: EC004S002817)
    r'(\d{3}\.\d{3}\.\d{3}-\d{2})\s+'    # 5: CPF (ex: 055.647.302-75)
    r'(\S+)\s+'                          # 6: Número do Contrato
    r'(\d+)\s+'                          # 7: Instituição Financeira (ex: 935)
    r'([\d\.,]+)$'                       # 8: Valor Consignado na Guia (ex: 100,43)
)

HEADER_COLUMNS_DETALHADO = [
    'Comp. Apuração',
    'Vencimento',
    'Nome Trabalhador',
    'Matrícula',
    'CPF',
    'Número do Contrato',
    'Instituição Financeira',
    'Valor Consignado na Guia'
]

HEADER_COLUMNS_CONSOLIDADO = [
    'Nome Trabalhador',
    'CPF',
    'Valor Consignado na Guia'
]


def extrair_metadados_guia(texto_pagina: str) -> dict:
    """Extrai informações cadastrais do cabeçalho da guia do extrato."""
    meta = {
        'empregador': '',
        'nome_empregador': '',
        'qtd_trabalhadores': '',
        'origem': '',
        'vencimento_guia': '',
        'total_guia': ''
    }
    if not texto_pagina:
        return meta

    m_emp = re.search(r'Empregador:\s*([\d\.\-\/]+)', texto_pagina)
    if m_emp:
        meta['empregador'] = m_emp.group(1).strip()

    m_nome = re.search(r'Nome Empregador:\s*([^Q\n\r]+?)(?=\s+Qtd\.|\n|$)', texto_pagina)
    if m_nome:
        meta['nome_empregador'] = m_nome.group(1).strip()

    m_qtd = re.search(r'Qtd\.\s*Trabalhadores\s*Consignado:\s*(\d+)', texto_pagina)
    if m_qtd:
        meta['qtd_trabalhadores'] = m_qtd.group(1).strip()

    m_venc = re.search(r'Vencimento da Guia:\s*(\d{2}/\d{2}/\d{4})', texto_pagina)
    if m_venc:
        meta['vencimento_guia'] = m_venc.group(1).strip()

    m_tot = re.search(r'Total da Guia[^:]*:\s*([\d\.,]+)', texto_pagina)
    if m_tot:
        meta['total_guia'] = m_tot.group(1).strip()

    return meta


def validar_padrao_pdf(arquivo_ou_stream) -> tuple[bool, str, dict]:
    """
    Realiza leitura prévia do PDF e valida se segue estritamente o padrão
    esperado do extrato de consignado de colaboradores.
    
    Retorna: (sucesso: bool, mensagem_erro_ou_ok: str, metadados: dict)
    """
    try:
        with pdfplumber.open(arquivo_ou_stream) as pdf:
            if not pdf.pages:
                return False, "O arquivo PDF enviado está vazio.", {}

            primeira_pagina = pdf.pages[0]
            texto_p1 = primeira_pagina.extract_text() or ""

            # 1. Validação de títulos e cabeçalhos característicos
            tem_titulo = (
                "Detalhe da Guia a Ser Emitida" in texto_p1 or 
                "Relação de Trabalhadores" in texto_p1
            )
            if not tem_titulo:
                return (
                    False,
                    "O cabeçalho do documento não corresponde ao Extrato de Consignado oficial ('Detalhe da Guia a Ser Emitida' / 'Relação de Trabalhadores').",
                    {}
                )

            # 2. Validação das colunas obrigatórias
            colunas_obrigatorias = ["Comp. Apuração", "Nome Trabalhador", "Matrícula", "CPF", "Valor Consignado"]
            ausentes = [col for col in colunas_obrigatorias if col not in texto_p1]
            if ausentes:
                return (
                    False,
                    f"Colunas obrigatórias não encontradas no documento: {', '.join(ausentes)}.",
                    {}
                )

            # 3. Validação de formato das linhas de lançamento
            linhas = [l.strip() for l in texto_p1.split('\n') if l.strip()]
            tem_linha_valida = any(ROW_PATTERN.match(l) for l in linhas)
            if not tem_linha_valida:
                return (
                    False,
                    "Não foi possível identificar lançamentos de consignado no formato padrão esperado na primeira página.",
                    {}
                )

            metadados = extrair_metadados_guia(texto_p1)
            metadados['total_paginas'] = len(pdf.pages)
            return True, "Arquivo validado com sucesso.", metadados

    except Exception as e:
        return False, f"Falha ao ler o arquivo PDF: {str(e)}", {}


def extrair_extrato_pdf(arquivo_ou_stream) -> tuple[pd.DataFrame, dict]:
    """
    Extrai todos os registros do PDF e os metadados da guia.
    Retorna (DataFrame com as 8 colunas, dicionário de metadados).
    """
    registros = []
    metadados = {}

    with pdfplumber.open(arquivo_ou_stream) as pdf:
        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text() or ""
            
            # Captura metadados da primeira página
            if i == 0 and not metadados:
                metadados = extrair_metadados_guia(texto)
                metadados['total_paginas'] = len(pdf.pages)

            for linha in texto.split('\n'):
                linha = linha.strip()
                match = ROW_PATTERN.match(linha)
                if match:
                    valor_str = match.group(8).replace('.', '').replace(',', '.')
                    registros.append({
                        'Comp. Apuração': match.group(1),
                        'Vencimento': match.group(2),
                        'Nome Trabalhador': match.group(3).strip(),
                        'Matrícula': match.group(4),
                        'CPF': match.group(5),
                        'Número do Contrato': match.group(6),
                        'Instituição Financeira': str(match.group(7)),
                        'Valor Consignado na Guia': round(float(valor_str), 2)
                    })

    df = pd.DataFrame(registros, columns=HEADER_COLUMNS_DETALHADO)
    return df, metadados


def consolidar_por_colaborador(df_detalhado: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa os dados detalhados por Nome Trabalhador e CPF,
    somando o Valor Consignado na Guia e ordenando alfabeticamente.
    """
    if df_detalhado.empty:
        return pd.DataFrame(columns=HEADER_COLUMNS_CONSOLIDADO)

    df_consolidado = (
        df_detalhado.groupby(['Nome Trabalhador', 'CPF'], as_index=False)['Valor Consignado na Guia']
        .sum()
    )
    df_consolidado['Valor Consignado na Guia'] = df_consolidado['Valor Consignado na Guia'].round(2)
    df_consolidado = df_consolidado.sort_values(by='Nome Trabalhador').reset_index(drop=True)
    return df_consolidado[HEADER_COLUMNS_CONSOLIDADO]


def gerar_excel_detalhado(df_detalhado: pd.DataFrame) -> io.BytesIO:
    """
    Gera o arquivo Excel 'consignado.xlsx' contendo todos os lançamentos
    individuais, formatação idêntica e linha de total com fórmula.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Consignado'

    # Estilos
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    
    total_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
    total_font = Font(name='Calibri', size=11, bold=True, color='000000')

    border_cell = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    border_total = Border(
        top=Side(style='thin', color='A6B9D0'),
        bottom=Side(style='double', color='1F4E79')
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    # 1. Cabeçalho
    ws.append(HEADER_COLUMNS_DETALHADO)
    for col_idx in range(1, len(HEADER_COLUMNS_DETALHADO) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center if col_idx != 3 else align_left
    ws.row_dimensions[1].height = 24

    # 2. Dados
    for row_data in df_detalhado.itertuples(index=False):
        ws.append([
            str(row_data[0]),
            str(row_data[1]),
            str(row_data[2]),
            str(row_data[3]),
            str(row_data[4]),
            str(row_data[5]),
            str(row_data[6]),
            float(row_data[7])
        ])
        r = ws.max_row
        ws.row_dimensions[r].height = 20

        ws.cell(row=r, column=1).alignment = align_center
        ws.cell(row=r, column=2).alignment = align_center
        ws.cell(row=r, column=3).alignment = align_left
        ws.cell(row=r, column=4).alignment = align_center
        ws.cell(row=r, column=5).alignment = align_center
        ws.cell(row=r, column=6).alignment = align_center
        ws.cell(row=r, column=7).alignment = align_center
        
        c_val = ws.cell(row=r, column=8)
        c_val.alignment = align_right
        c_val.number_format = '#,##0.00'

        for c in range(1, 9):
            ws.cell(row=r, column=c).border = border_cell

    # 3. Linha Total Consignado
    last_data_row = ws.max_row
    total_row = last_data_row + 1
    
    ws.cell(row=total_row, column=1, value='Total Consignado')
    ws.cell(row=total_row, column=8, value=f'=SUM(H2:H{last_data_row})')
    
    ws.row_dimensions[total_row].height = 22
    for c in range(1, 9):
        cell = ws.cell(row=total_row, column=c)
        cell.fill = total_fill
        cell.font = total_font
        cell.border = border_total
        if c == 1:
            cell.alignment = align_left
        elif c == 8:
            cell.alignment = align_right
            cell.number_format = '#,##0.00'

    # Larguras de coluna
    col_widths = {
        'A': 16.0,
        'B': 14.0,
        'C': 42.0,
        'D': 16.0,
        'E': 18.0,
        'F': 22.0,
        'G': 22.0,
        'H': 26.0
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def gerar_excel_consolidado(df_consolidado: pd.DataFrame) -> io.BytesIO:
    """
    Gera o arquivo Excel 'consignado_consolidado.xlsx' contendo o extrato
    agrupado por colaborador com a soma do valor consignado.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Consolidado por Trabalhador'

    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')

    total_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
    total_font = Font(name='Calibri', size=11, bold=True, color='000000')

    border_cell = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    border_total = Border(
        top=Side(style='thin', color='A6B9D0'),
        bottom=Side(style='double', color='1F4E79')
    )

    align_center = Alignment(horizontal='center', vertical='center')
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    # 1. Cabeçalho
    ws.append(HEADER_COLUMNS_CONSOLIDADO)
    for col_idx in range(1, len(HEADER_COLUMNS_CONSOLIDADO) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_left if col_idx == 1 else (align_center if col_idx == 2 else align_right)
    ws.row_dimensions[1].height = 24

    # 2. Dados
    for row_data in df_consolidado.itertuples(index=False):
        ws.append([
            str(row_data[0]),
            str(row_data[1]),
            float(row_data[2])
        ])
        r = ws.max_row
        ws.row_dimensions[r].height = 20

        ws.cell(row=r, column=1).alignment = align_left
        ws.cell(row=r, column=2).alignment = align_center
        c_val = ws.cell(row=r, column=3)
        c_val.alignment = align_right
        c_val.number_format = '#,##0.00'

        for c in range(1, 4):
            ws.cell(row=r, column=c).border = border_cell

    # 3. Linha Total Consignado
    last_data_row = ws.max_row
    total_row = last_data_row + 1

    ws.cell(row=total_row, column=1, value='Total Consignado')
    ws.cell(row=total_row, column=3, value=f'=SUM(C2:C{last_data_row})')

    ws.row_dimensions[total_row].height = 22
    for c in range(1, 4):
        cell = ws.cell(row=total_row, column=c)
        cell.fill = total_fill
        cell.font = total_font
        cell.border = border_total
        if c == 1:
            cell.alignment = align_left
        elif c == 3:
            cell.alignment = align_right
            cell.number_format = '#,##0.00'

    # Larguras de coluna
    col_widths = {
        'A': 44.0,
        'B': 18.0,
        'C': 28.0
    }
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

