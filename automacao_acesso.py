import os
import sys
import time
import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

from config import fix_utf8_mojibake

CSV_HEADER = "Registration ID;Name;Org Structure  Function;Access Profile Code;PIS;Person Situation;Credential Number;Credential Start Date;Credential End Date;Technology;Credential User Face;Credential User REP;CPF;;;;;;;Observation;Inactive;;;CanReentry\n"

def generate_acesso_csv(pessoas, person_situation, observation, output_path=None):
    """
    Gera o arquivo CSV formatado para importação no DIMEP Acesso II.
    pessoas: lista de objetos ou dicionários contendo 'chapa' (ou 'matricula') e 'nome'.
    person_situation: 11 (Bloqueio) ou 10 (Desbloqueio)
    observation: 'Férias' (Bloqueio) ou "'" (Desbloqueio)
    output_path: caminho para salvar o arquivo. Se None, gera em static/documents/ com timestamp.
    """
    if not output_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        docs_dir = os.path.join(base_dir, 'static', 'documents')
        os.makedirs(docs_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(docs_dir, f"acesso_import_{timestamp}.csv")

    lines = [CSV_HEADER]
    for p in pessoas:
        chapa = getattr(p, 'chapa', None) if not isinstance(p, dict) else p.get('chapa')
        nome = getattr(p, 'nome', None) if not isinstance(p, dict) else p.get('nome')
        
        chapa_str = str(chapa).strip() if chapa is not None else ''
        nome_str = str(nome).strip() if nome is not None else ''
        sit_str = str(person_situation)
        obs_str = str(observation) if observation is not None else ''
        
        row = f"{chapa_str};{nome_str};CONSÓRCIO PONTE RIO TOCANTINS;1;;{sit_str};0;16/06/2025;16/06/2099;4;;;;;;;;;;{obs_str};TRUE;;;false\n"
        lines.append(row)

    # Gravação com encoding cp1252 (exigido pelo sistema DIMEP Acesso II para correta leitura do caractere Ó em CONSÓRCIO PONTE RIO TOCANTINS)
    with open(output_path, 'w', encoding='cp1252', errors='replace') as f:
        f.writelines(lines)

    return output_path



def run_acesso_import(csv_path, output_dir=None):
    """
    Executa a automação de importação no DIMEP Acesso II via Playwright.
    Emite logs passo a passo via gerador (yield).
    """
    login = os.environ.get("ACESSO_LOGIN") or os.environ.get("LOGIN", "mixestec")
    senha = os.environ.get("ACESSO_SENHA") or os.environ.get("SENHA", "Dimep@123")
    base_url = os.environ.get("ACESSO_URL", "https://ponteriotocantins.dimep-ams.com.br").rstrip('/')
    headless_str = os.environ.get("ACESSO_HEADLESS") or os.environ.get("HEADLESS", "True")
    
    headless = headless_str.lower() in ("true", "1", "yes")

    # Tempo limite em segundos para o processamento e download
    timeout_segundos = int(os.environ.get("ACESSO_TIMEOUT", "900"))
    timeout_ms = timeout_segundos * 1000

    if not os.path.exists(csv_path):
        yield f"❌ Erro: O arquivo CSV '{csv_path}' não foi encontrado.\n"
        return

    base_project_dir = os.path.dirname(os.path.abspath(__file__))
    if not output_dir:
        output_dir = os.path.join(base_project_dir, 'static', 'documents')
    os.makedirs(output_dir, exist_ok=True)

    yield "🔄 Inicializando navegador Playwright para o sistema Acesso II...\n"
    yield f"🌐 URL Alvo: {base_url}\n"
    yield f"📄 Arquivo CSV: {os.path.basename(csv_path)}\n"

    p = None
    browser = None
    try:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # 1. Acesso à página de Logon
        login_url = f"{base_url}/logon.aspx"
        yield f"🔄 Acessando página de login ({login_url})...\n"
        page.goto(login_url, wait_until='domcontentloaded', timeout=60000)
        
        page.wait_for_selector("#txtUsrLogin", timeout=30000)
        yield "🔐 Preenchendo credenciais de acesso...\n"
        page.fill("#txtUsrLogin", login)
        page.fill("#txtUserPassLogin", senha)
        
        yield "🔄 Clicando em Entrar...\n"
        page.click("#Submit1")
        page.wait_for_load_state("domcontentloaded", timeout=60000)
        yield "✅ Login efetuado com sucesso.\n"
        
        # 2. Navegação para tela de Importação de Pessoas
        import_url = f"{base_url}/ImportingPerson/ImportingPerson.aspx"
        yield f"🔄 Navegando para a página de importação ({import_url})...\n"
        page.goto(import_url, wait_until='domcontentloaded', timeout=60000)
        
        # Validação de acesso
        if "ImportingPerson.aspx" not in page.url:
            yield f"❌ Erro: Falha na autenticação ou permissão negada. URL atual: {page.url}\n"
            screenshot_err = os.path.join(output_dir, f"acesso_auth_err_{int(time.time())}.png")
            page.screenshot(path=screenshot_err)
            yield f"⚠️ Screenshot salva em: {screenshot_err}\n"
            return
        
        # 3. Upload do arquivo CSV
        file_input_selector = "#ctl00_ctl00_MainContentMainMaster_MainContent_FileUpload_ctl02"
        yield "🔄 Localizando campo de upload do arquivo...\n"
        page.wait_for_selector(file_input_selector, timeout=30000)
        
        yield f"📤 Enviando arquivo CSV '{os.path.basename(csv_path)}'...\n"
        page.set_input_files(file_input_selector, os.path.abspath(csv_path))
        time.sleep(1.0)
        
        # 4. Processamento e download do relatório
        process_btn_selector = "#MainContentMainMaster_MainContent_btnProcess"
        yield "🔄 Aguardando botão de processamento...\n"
        page.wait_for_selector(process_btn_selector, timeout=30000)
        
        yield f"⚙️ Disparando processamento (tempo limite de até {timeout_segundos}s)...\n"
        context.set_default_timeout(timeout_ms)
        
        with page.expect_download(timeout=timeout_ms) as download_info:
            page.click(process_btn_selector)
            
        download = download_info.value
        download_filename = download.suggested_filename or f"relatorio_processamento_{int(time.time())}.txt"
        saved_report_path = os.path.join(output_dir, download_filename)
        
        yield f"📥 Download do relatório de processamento detectado: {download_filename}\n"
        download.save_as(saved_report_path)
        yield f"✅ Relatório de execução baixado e salvo com sucesso em: {saved_report_path}\n"
        
        # Ler resumo do relatório baixado se for texto
        if os.path.exists(saved_report_path):
            try:
                conteudo = ""
                for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin1'):
                    try:
                        with open(saved_report_path, 'r', encoding=enc) as rf:
                            conteudo = rf.read()
                            if conteudo:
                                break
                    except (UnicodeDecodeError, Exception):
                        continue
                if conteudo:
                    conteudo_clean = fix_utf8_mojibake(conteudo)
                    yield f"\n📋 --- CONTEÚDO DO RELATÓRIO DO ACESSO II ---\n{conteudo_clean.strip()}\n-----------------------------------------\n"
            except Exception:
                pass


        yield "\n🏁 Automação no Acesso II concluída com sucesso!\n"

    except Exception as e:
        yield f"❌ Erro durante a automação no Acesso II: {str(e)}\n"
        try:
            if browser and 'page' in locals() and page:
                screenshot_err = os.path.join(output_dir, f"acesso_exec_err_{int(time.time())}.png")
                page.screenshot(path=screenshot_err)
                yield f"⚠️ Screenshot do erro salva em: {screenshot_err}\n"
        except Exception as se:
            yield f"⚠️ Não foi possível capturar screenshot: {str(se)}\n"
    finally:
        if browser:
            try:
                browser.close()
            except:
                pass
        if p:
            try:
                p.stop()
            except:
                pass
        yield "🔒 Navegador encerrado.\n"
