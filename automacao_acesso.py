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
        if callable(observation):
            obs_str = str(observation(p))
        else:
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


def run_envio_credenciais_acesso(output_dir=None):
    """
    Executa a automação de Envio de Credenciais no DIMEP Acesso II via Playwright.
    Navega até SendingCommand.aspx, clica na aba 'Lista', marca o comando de credenciais e todos os equipamentos, e envia.
    Emite logs passo a passo via gerador (yield).
    """
    login = os.environ.get("ACESSO_LOGIN") or os.environ.get("LOGIN", "mixestec")
    senha = os.environ.get("ACESSO_SENHA") or os.environ.get("SENHA", "Dimep@123")
    base_url = os.environ.get("ACESSO_URL", "https://ponteriotocantins.dimep-ams.com.br").rstrip('/')
    headless_str = os.environ.get("ACESSO_HEADLESS") or os.environ.get("HEADLESS", "True")
    
    headless = headless_str.lower() in ("true", "1", "yes")

    base_project_dir = os.path.dirname(os.path.abspath(__file__))
    if not output_dir:
        output_dir = os.path.join(base_project_dir, 'static', 'documents')
    os.makedirs(output_dir, exist_ok=True)

    yield "🔄 Inicializando navegador Playwright para Envio de Credenciais no Acesso II...\n"
    yield f"🌐 URL Alvo: {base_url}\n"

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
        
        # 2. Navegação para a página Envio de Comando
        sending_url = f"{base_url}/SendingCommand/SendingCommand.aspx"
        yield f"🔄 Navegando para a página de Envio de Comando ({sending_url})...\n"
        page.goto(sending_url, wait_until='domcontentloaded', timeout=60000)
        
        # Validação de acesso
        if "SendingCommand.aspx" not in page.url:
            yield f"❌ Erro: Falha ao acessar página de Envio de Comando. URL atual: {page.url}\n"
            screenshot_err = os.path.join(output_dir, f"acesso_sending_auth_err_{int(time.time())}.png")
            page.screenshot(path=screenshot_err)
            yield f"⚠️ Screenshot salva em: {screenshot_err}\n"
            return

        # 3. Clicar na aba Lista (<a href="#subtabs3"> Lista</a>)
        yield "🔄 Clicando na aba 'Lista'...\n"
        tab_selector = 'a[href="#subtabs3"]'
        page.wait_for_selector(tab_selector, timeout=30000)
        page.click(tab_selector)
        time.sleep(1.5)

        # 4. Marcar checkbox do comando (ctl00_ctl00_MainContentMainMaster_MainContent_lstViewListCommands_ctrl2_chkCommand)
        chk_cmd_selector = "#ctl00_ctl00_MainContentMainMaster_MainContent_lstViewListCommands_ctrl2_chkCommand"
        yield "🔄 Marcando o comando na lista...\n"
        page.wait_for_selector(chk_cmd_selector, timeout=30000)
        if not page.is_checked(chk_cmd_selector):
            page.click(chk_cmd_selector)
        time.sleep(1.5)

        # 4.1 Clicar no botão 'Ok' da tela/modal de confirmação de credenciais
        btn_ok_selector = "#MainContentMainMaster_MainContent_CredentialTotal_btnOk"
        yield "🔄 Aguardando tela de confirmação e clicando em 'Ok'...\n"
        
        target_page = page
        if len(context.pages) > 1:
            target_page = context.pages[-1]
            yield f"ℹ️ Detectada nova aba/janela ({target_page.url})...\n"

        try:
            target_page.wait_for_selector(btn_ok_selector, state="visible", timeout=15000)
            target_page.click(btn_ok_selector)
            time.sleep(1.5)
            yield "✅ Clique em 'Ok' realizado com sucesso.\n"
        except Exception as e_ok:
            ok_clicked = False
            for p_item in context.pages:
                try:
                    btn = p_item.query_selector(btn_ok_selector) or p_item.query_selector("input[value='Ok']")
                    if btn:
                        btn.click()
                        ok_clicked = True
                        yield "✅ Clique em 'Ok' realizado (via fallback).\n"
                        break
                except Exception:
                    pass
            if not ok_clicked:
                yield "⚠️ Botão 'Ok' não localizado ou tela já confirmada. Prosseguindo com o fluxo...\n"

        # 5. Marcar checkbox de todos os equipamentos (MainContentMainMaster_MainContent_chkAllEquipments)
        chk_equip_selector = "#MainContentMainMaster_MainContent_chkAllEquipments"
        yield "🔄 Marcando todos os equipamentos...\n"
        page.wait_for_selector(chk_equip_selector, timeout=30000)
        if not page.is_checked(chk_equip_selector):
            page.click(chk_equip_selector)
        time.sleep(1.5)

        # 6. Clicar no botão Enviar (MainContentMainMaster_MainContent_btnSend)
        btn_send_selector = "#MainContentMainMaster_MainContent_btnSend"
        yield "🔄 Clicando no botão Enviar...\n"
        page.wait_for_selector(btn_send_selector, timeout=30000)
        page.click(btn_send_selector)
        page.wait_for_load_state("domcontentloaded", timeout=60000)
        time.sleep(2.0)

        yield "✅ Comando de Envio de Credenciais Acesso II enviado com sucesso!\n"
        yield "\n🏁 Automação no Acesso II concluída com sucesso!\n"

    except Exception as e:
        yield f"❌ Erro durante a automação de Envio de Credenciais no Acesso II: {str(e)}\n"
        try:
            if browser and 'page' in locals() and page:
                screenshot_err = os.path.join(output_dir, f"acesso_sending_exec_err_{int(time.time())}.png")
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
