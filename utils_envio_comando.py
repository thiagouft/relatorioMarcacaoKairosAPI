import requests
import json
import io
import datetime

from config import Config

def fetch_cracha(cracha):
    url = "https://www.dimepkairos.com.br/RestServiceApi/People/SearchPerson"
    payload = {"Cracha": cracha, "CarregarBiometrias": "true"}
    
    try:
        response = requests.post(url, json=payload, headers=Config.KAIROS_HEADERS)
        if response.status_code == 200:
            data = response.json()
            if data.get("Sucesso") and data.get("Obj"):
                # Handle JSON string inside Obj if necessary
                obj_data = data["Obj"]
                if isinstance(obj_data, str):
                    try:
                        obj_data = json.loads(obj_data)
                    except json.JSONDecodeError:
                        return {"cracha": cracha, "sucesso": False, "mensagem": "Erro ao interpretar dados da API (JSON inválido)."}
                
                if isinstance(obj_data, list) and len(obj_data) > 0:
                    person = obj_data[0]
                    matricula = person.get("Matricula")
                    nome = person.get("Nome")
                    data_demissao = person.get("DataDemissao")
                    templates = person.get("Template") or person.get("Templates") or []
                    
                    if not templates or len(templates) == 0:
                        return {
                            "cracha": cracha,
                            "sucesso": True,
                            "semTemplates": True,
                            "mensagem": "Não possui Biometria",
                            "nome": nome,
                            "id": person.get("Id")
                        }
                    
                    if data_demissao and data_demissao != "01/01/1753 00:00:00":
                        data_demissao_curta = data_demissao.split(" ")[0]
                        return {
                            "cracha": cracha,
                            "sucesso": False,
                            "mensagem": "Funcionário Desligado",
                            "dataDesligamento": data_demissao_curta,
                            "nome": nome,
                            "id": person.get("Id")
                        }
                    
                    return {"cracha": cracha, "matricula": matricula, "nome": nome, "sucesso": True, "id": person.get("Id")}
        
        mensagem_erro = data.get("Mensagem") if 'data' in locals() and data else "Erro desconhecido"
        return {"cracha": cracha, "sucesso": False, "mensagem": mensagem_erro}
        
    except Exception as e:
        return {"cracha": cracha, "sucesso": False, "mensagem": str(e)}

def unassociate_clocks(cracha_list, relogio_list):
    url = "https://www.dimepkairos.com.br/RestServiceApi/Clock/UnassociateClocks"
    payload = {
        "PessoaCracha": cracha_list,
        "RelogioNumero": relogio_list
    }
    try:
        requests.post(url, json=payload, headers=Config.KAIROS_HEADERS)
    except Exception as e:
        print(f"Erro ao desassociar os crachás: {e}")

def associate_clocks(cracha_list, relogio_list):
    url = "https://www.dimepkairos.com.br/RestServiceApi/Clock/AssociateClocks"
    payload = {
        "PessoaCracha": cracha_list,
        "RelogioNumero": relogio_list,
        "EnviarListaCredenciais": True,
        "EnviarListaTemplate": True
    }
    try:
        response = requests.post(url, json=payload, headers=Config.KAIROS_HEADERS)
        if response.status_code == 200 and response.json().get("Sucesso"):
            return {"sucesso": True}
        else:
            return {"sucesso": False, "mensagem": response.json().get("Mensagem", "Erro na associação")}
    except Exception as e:
        return {"sucesso": False, "mensagem": str(e)}

def schedule_commands(cracha_list, config_options, relogio_list):
    url = "https://www.dimepkairos.com.br/RestServiceApi/Clock/ScheduleCommands"
    # Ensure config_options keys correspond exactly to Kairos API flags
    payload = {
        "PessoaCracha": cracha_list,
        "RelogioNumero": relogio_list
    }
    payload.update(config_options)
    
    try:
        response = requests.post(url, json=payload, headers=Config.KAIROS_HEADERS)
        if response.status_code == 200 and response.json().get("Sucesso"):
            return {"sucesso": True, "mensagem": "Comandos agendados com sucesso.", "detalhes": response.json()}
        return {"sucesso": False, "mensagem": response.json().get("Mensagem", "Falha no agendamento")}
    except Exception as e:
        return {"sucesso": False, "mensagem": str(e)}

def fetch_clocks():
    url = "https://www.dimepkairos.com.br/RestServiceApi/Clock/SearchClocks"
    payload = {"TodosRelogios": "true"}
    try:
        response = requests.post(url, json=payload, headers=Config.KAIROS_HEADERS)
        if response.status_code == 200 and response.json().get("Sucesso"):
            return response.json().get("Obj", [])
        return []
    except Exception as e:
        print(f"Erro ao buscar relógios: {e}")
        return []

def dismiss_employee(employee, data_desligamento):
    url = "https://www.dimepkairos.com.br/RestServiceApi/Dismiss/MarkDismiss"
    payload = {
        "PESSOAID": employee.get("id"),
        "MOTIVO": "11-Rescisão sem justa causa por iniciativa do empregador",
        "DATA": data_desligamento
    }
    try:
        response = requests.post(url, json=payload, headers=Config.KAIROS_HEADERS)
        if response.status_code == 200 and response.json().get("Sucesso"):
            return {"sucesso": True, "employee": employee}
        else:
            mensagem = response.json().get("Mensagem", "Erro no desligamento")
            return {"sucesso": False, "employee": employee, "mensagem": mensagem}
    except Exception as e:
        return {"sucesso": False, "employee": employee, "mensagem": str(e)}

def generate_pdf_report(filename, title, content_lines):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    import io
    
    buffer = io.IOBytes() if hasattr(io, 'IOBytes') else io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        spaceAfter=2,
        alignment=TA_LEFT
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=2,
        alignment=TA_LEFT
    )
    
    if title:
        title_lines = title.split('\n')
        for t_line in title_lines:
            if t_line.strip():
                elements.append(Paragraph(t_line, title_style))
        elements.append(Spacer(1, 8))
        
    for line in content_lines:
        elements.append(Paragraph(line, normal_style))
        
    doc.build(elements)
    buffer.seek(0)
    
    with open(filename, 'wb') as f:
        f.write(buffer.getvalue())

def generate_cabecalho_arquivo(relogio_list, comandos):
    agora = datetime.datetime.now()
    data_hora = agora.strftime("%d/%m/%Y %H:%M:%S")
    
    # Simple lookup for clocks
    todos_relogios = fetch_clocks()
    relogios_selecionados = [r for r in todos_relogios if r.get('RelogioNumero') in relogio_list]
    
    descricao_relogios = "\n".join([f"Código: {r.get('RelogioNumero')} - Descrição: {r.get('RelogioNome')}" for r in relogios_selecionados])
    descricao_comandos = "\n".join([f"- {comando}" for comando in comandos.keys() if comandos[comando]])
    
    return f"Data de Processamento: {data_hora}\nRelógios Selecionados:\n{descricao_relogios}\n\nComandos Selecionados:\n{descricao_comandos}\n\n"

