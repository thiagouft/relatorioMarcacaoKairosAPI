import os
import time
import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv, dotenv_values

load_dotenv()

def get_previous_date():
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    return yesterday.strftime('%d/%m/%Y')

def run_relogio_automation(tipo, data_personalizada=None, relogio_ids=None):
    # 1. Load credentials
    login = os.environ.get('KAIROS_LOGIN') or os.environ.get('LOGIN')
    password = os.environ.get('KAIROS_PASSWORD') or os.environ.get('SENHA')

    if not login or not password:
        # Fallback to ponteiro/.env
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ponteiro_env_path = os.path.join(base_dir, 'ponteiro', '.env')
        if os.path.exists(ponteiro_env_path):
            ponteiro_env = dotenv_values(ponteiro_env_path)
            login = login or ponteiro_env.get('LOGIN')
            password = password or ponteiro_env.get('SENHA')

    if not login or not password:
        yield "❌ Erro: Credenciais de login (LOGIN/SENHA) não encontradas no ambiente ou em ponteiro/.env.\n"
        return

    if not data_personalizada:
        data_personalizada = get_previous_date()

    if relogio_ids is None:
        # Default clock IDs: 1 to 32, plus 35 and 36
        relogio_ids = list(range(1, 33)) + [35, 36]
    else:
        # Map selectable clock IDs 33 -> 35 and 34 -> 36 for URL access
        relogio_ids = [35 if rid == 33 else 36 if rid == 34 else rid for rid in relogio_ids]

    yield "🔄 Iniciando automação com Playwright...\n"
    
    p = None
    browser = None
    try:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Login
        LOGIN_URL = 'https://www.dimepkairos.com.br'
        yield "🔄 Acessando página de login...\n"
        page.goto(LOGIN_URL, wait_until='domcontentloaded')
        yield "✅ Página de login carregada.\n"

        page.wait_for_selector('#LogOnModel_UserName')
        page.type('#LogOnModel_UserName', login, delay=50)
        time.sleep(0.3)
        page.type('#LogOnModel_Password', password, delay=50)

        page.wait_for_selector('#btnFormLogin')
        page.click('#btnFormLogin')
        yield "🔐 Dados de login enviados. Aguardando autenticação...\n"

        # Aguarda a página processar o login
        try:
            page.wait_for_function(
                """() => {
                    const url = window.location.href;
                    const hasErrors = document.querySelector('.validation-summary-errors, #divErrors');
                    const hasSessionModal = document.querySelector('.ui-dialog, .bootbox, [id*="Desconectar"]');
                    const isAwayFromLogin = !url.includes('/LogOn') && !url.endsWith('dimepkairos.com.br/') && !url.endsWith('dimepkairos.com.br');
                    return isAwayFromLogin || !!hasErrors || !!hasSessionModal;
                }""",
                timeout=20000
            )
        except Exception:
            pass

        # Verifica se apareceu modal de sessão concorrente (ex: outro usuário conectado)
        try:
            btn_confirm = page.locator('button:has-text("Sim"), input[value="Sim"], .ui-dialog-buttonset button:first-child, button:has-text("Continuar"), #btnDesconectar')
            if btn_confirm.count() > 0 and btn_confirm.first.is_visible():
                yield "⚠️ Alerta de sessão anterior detectado. Confirmando desconexão...\n"
                btn_confirm.first.click()
                time.sleep(1.0)
                page.wait_for_load_state('domcontentloaded', timeout=15000)
        except Exception:
            pass

        # Verifica se houve erro explícito no login
        try:
            err_el = page.locator('.validation-summary-errors, #divErrors')
            if err_el.count() > 0 and err_el.first.is_visible():
                err_text = err_el.first.inner_text().strip().replace('\n', ' ')
                if err_text:
                    yield f"❌ Falha de login no Kairos: {err_text}\n"
                    return
        except Exception:
            pass

        yield "✅ Login processado com sucesso.\n"

        if tipo == 'datahora':
            yield "📅 Iniciando atualização de data e hora para os relógios selecionados...\n"
            for i in relogio_ids:
                target_url = f"https://www.dimepkairos.com.br/Dimep/Relogios/AgendarOperacaoRelogio/{i}?operacao=3"
                yield f"\n🔄 Enviando comando de data e hora para o relógio {i}...\n"
                try:
                    page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Aguarda qualquer feedback da página: sucesso, erro, ou volta para login
                    feedback_selector = '.validation-summary-ok, .validation-summary-errors, #divErrors, .field-validation-error, #LogOnModel_UserName, .toast-message'
                    page.wait_for_selector(feedback_selector, timeout=25000)
                    
                    # 1. Verifica se houve sucesso
                    ok_el = page.locator('.validation-summary-ok')
                    if ok_el.count() > 0 and ok_el.first.is_visible():
                        msg = ok_el.first.inner_text().strip().replace('\n', ' ')
                        yield f"✅ Comando enviado com sucesso para o relógio {i}: {msg or 'Operação agendada.'}\n"
                    # 2. Verifica se houve erro ou aviso do Kairos
                    elif page.locator('.validation-summary-errors, #divErrors').count() > 0 and page.locator('.validation-summary-errors, #divErrors').first.is_visible():
                        err_msg = page.locator('.validation-summary-errors, #divErrors').first.inner_text().strip().replace('\n', ' ')
                        yield f"⚠️ Relógio {i} (Aviso do Kairos): {err_msg}\n"
                    # 3. Verifica se a sessão expirou e voltou para login
                    elif page.locator('#LogOnModel_UserName').count() > 0 and page.locator('#LogOnModel_UserName').first.is_visible():
                        yield f"❌ Relógio {i}: Sessão expirada/desconectada pelo Kairos (redirecionado para tela de login).\n"
                    else:
                        yield f"ℹ️ Relógio {i}: Resposta recebida da página do Kairos.\n"
                    
                    time.sleep(0.5)
                except Exception as inner_err:
                    # Tenta capturar screenshot para diagnóstico visual
                    ss_info = ""
                    try:
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        ss_dir = os.path.join(base_dir, 'static', 'screenshots')
                        os.makedirs(ss_dir, exist_ok=True)
                        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        ss_file = os.path.join(ss_dir, f"erro_relogio_{i}_{ts}.png")
                        page.screenshot(path=ss_file, full_page=True)
                        ss_info = f" [Captura salva em: static/screenshots/{os.path.basename(ss_file)}]"
                    except Exception:
                        pass
                    
                    # Obtém a URL atual para ajudar no diagnóstico
                    curr_url_info = ""
                    try:
                        curr_url_info = f" (URL atual: {page.url})"
                    except Exception:
                        pass

                    yield f"❌ Erro ao enviar comando para o relógio {i}: {str(inner_err)}{curr_url_info}{ss_info}\n"
            
            yield "\n🏁 Automação de Data e Hora concluída!\n"

        elif tipo == 'verificacao_conclusao':
            yield "🔍 Iniciando verificação de conclusão de comandos nos relógios...\n"
            for i in relogio_ids:
                advanced_url = f"https://www.dimepkairos.com.br/Dimep/Relogios/Advanced/{i}"
                yield f"\n🔄 Verificando status dos comandos para o relógio {i}...\n"
                try:
                    page.goto(advanced_url, wait_until='domcontentloaded')
                    time.sleep(1.0)
                    
                    status_dict = page.evaluate("""() => {
                        const rows = Array.from(document.querySelectorAll('tr'));
                        const results = {};
                        for (const row of rows) {
                            const cols = row.querySelectorAll('td');
                            if (cols.length >= 2) {
                                const desc = cols[0].textContent.trim();
                                const status = cols[1].textContent.trim();
                                if (desc.includes('Buscar status do relógio') || desc.includes('Atualizar data e hora')) {
                                    results[desc] = status;
                                }
                            }
                        }
                        return results;
                    }""")
                    
                    if not status_dict:
                        yield f"⚠️ Relógio {i}: Tabela de agendamentos não encontrada ou sem comandos de interesse.\n"
                    else:
                        for desc, status in status_dict.items():
                            yield f"  - [{desc}]: {status}\n"
                    
                except Exception as inner_err:
                    yield f"❌ Erro ao verificar relógio {i}: {str(inner_err)}\n"
                    continue
            yield "\n🏁 Automação de Verificação de Conclusão concluída!\n"

        else:
            # Pointer Repositioning
            yield f"📅 Iniciando reposição do ponteiro para a data: {data_personalizada}...\n"
            
            # 1. Reposição de Ponteiro for each clock
            for i in relogio_ids:
                advanced_url = f"https://www.dimepkairos.com.br/Dimep/Relogios/Advanced/{i}"
                yield f"\n🔄 Processando reposição do ponteiro para o relógio {i}...\n"
                try:
                    page.goto(advanced_url, wait_until='domcontentloaded')
                    time.sleep(0.5)
                    yield f"✅ Acessou o relógio {i}\n"

                    page.wait_for_selector('#TabReposicaoPonteiro')
                    page.click('#TabReposicaoPonteiro')
                    time.sleep(0.5)
                    yield "✅ Aba 'Reposição do Ponteiro' selecionada.\n"

                    page.wait_for_selector('label[for="radioAPartirDeData"]')
                    page.click('label[for="radioAPartirDeData"]')
                    time.sleep(0.3)

                    page.wait_for_selector('#textboxData')
                    page.evaluate(f"""() => {{
                        const dateInput = document.querySelector('#textboxData');
                        if (dateInput) {{
                            dateInput.value = '';
                            dateInput.value = '{data_personalizada}';
                        }}
                    }}""")
                    yield f"📅 Data '{data_personalizada}' inserida.\n"
                    time.sleep(0.3)

                    page.wait_for_selector('.questionReposicaoPonteiro')
                    page.click('.questionReposicaoPonteiro')
                    yield "🚀 Requisição enviada.\n"

                    # Confirmação (botão "Sim")
                    page.wait_for_selector('#bReposicaoPonteiro', state='visible', timeout=5000)
                    time.sleep(0.3)
                    page.click('#bReposicaoPonteiro')
                    yield "✔️ Confirmação da reposição executada.\n"

                except Exception as inner_err:
                    yield f"❌ Erro na reposição do ponteiro para o relógio {i}: {str(inner_err)}\n"
                    continue

            # 2. Importação (Marcações)
            for i in relogio_ids:
                advanced_url = f"https://www.dimepkairos.com.br/Dimep/Relogios/Advanced/{i}"
                yield f"\n🔄 Processando 2ª importação para o relógio {i}...\n"
                try:
                    page.goto(advanced_url, wait_until='domcontentloaded')
                    time.sleep(0.5)

                    page.wait_for_selector('#TabExportarDados', state='visible', timeout=5000)
                    page.evaluate("""() => {
                        const exportTab = document.querySelector('#TabExportarDados');
                        if (exportTab) exportTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }""")
                    time.sleep(0.5)

                    page.click('#TabExportarDados')
                    time.sleep(0.5)
                    yield "📁 Aba 'Comandos do Relógio' aberta.\n"

                    # Seleciona "Importar"
                    page.wait_for_selector('label[for="radioFunctionImportar"]')
                    page.click('label[for="radioFunctionImportar"]')
                    time.sleep(0.3)
                    yield "☑️ Opção 'Importar' selecionada novamente para 'Marcações'.\n"

                    # Marca "Marcações"
                    page.wait_for_selector('label[for="checkImportarMarcacoes"]')
                    page.click('label[for="checkImportarMarcacoes"]')
                    time.sleep(0.3)
                    yield "🔘 'Marcações' marcado.\n"

                    # Clica em "Importar"
                    page.wait_for_selector('.buttonImportar')
                    page.click('.buttonImportar')
                    time.sleep(1.0)
                    yield "📨 Importação de 'Marcações' concluída.\n"

                except Exception as inner_err:
                    yield f"❌ Erro na 2ª importação para o relógio {i}: {str(inner_err)}\n"
                    continue

            # 3. Importação (Status Completo e Status Imediato)
            for i in relogio_ids:
                advanced_url = f"https://www.dimepkairos.com.br/Dimep/Relogios/Advanced/{i}"
                yield f"\n🔄 Processando 3ª importação para o relógio {i}...\n"
                try:
                    page.goto(advanced_url, wait_until='domcontentloaded')
                    time.sleep(0.5)

                    page.wait_for_selector('#TabExportarDados', state='visible', timeout=5000)
                    page.evaluate("""() => {
                        const exportTab = document.querySelector('#TabExportarDados');
                        if (exportTab) exportTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }""")
                    time.sleep(0.5)

                    page.click('#TabExportarDados')
                    time.sleep(0.5)
                    yield "📁 Aba 'Comandos do Relógio' aberta.\n"

                    # Seleciona "Importar"
                    page.wait_for_selector('label[for="radioFunctionImportar"]')
                    page.click('label[for="radioFunctionImportar"]')
                    time.sleep(0.3)
                    yield "☑️ Opção 'Importar' selecionada novamente para 'Status Completo' e 'Status Imediato'.\n"

                    # Marca "Status Completo"
                    page.wait_for_selector('label[for="checkboxImportarStatusCompleto"]')
                    page.click('label[for="checkboxImportarStatusCompleto"]')
                    time.sleep(0.3)
                    yield "🔘 'Status Completo' marcado.\n"

                    # Marca "Status Imediato"
                    page.wait_for_selector('label[for="checkboxImportarStatusImediato"]')
                    page.click('label[for="checkboxImportarStatusImediato"]')
                    time.sleep(0.3)
                    yield "🔘 'Status Imediato' marcado.\n"

                    # Clica em "Importar"
                    page.wait_for_selector('.buttonImportar')
                    page.click('.buttonImportar')
                    time.sleep(1.0)
                    yield "📨 Importação de 'Status Completo' e 'Status Imediato' concluída novamente.\n"

                except Exception as inner_err:
                    yield f"❌ Erro na 3ª importação para o relógio {i}: {str(inner_err)}\n"
                    continue

            yield "\n🏁 Automação de Reposição de Ponteiro concluída!\n"

    except Exception as e:
        yield f"❌ Erro geral na automação: {str(e)}\n"
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
        print("🔒 Navegador encerrado.")
