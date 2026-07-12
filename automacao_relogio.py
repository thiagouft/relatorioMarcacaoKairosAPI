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
        yield "🔐 Dados de login enviados.\n"

        # Wait for navigation after form submission
        page.wait_for_load_state('domcontentloaded')
        yield "✅ Login realizado com sucesso.\n"

        if tipo == 'datahora':
            yield "📅 Iniciando atualização de data e hora para os relógios selecionados...\n"
            for i in relogio_ids:
                target_url = f"https://www.dimepkairos.com.br/Dimep/Relogios/AgendarOperacaoRelogio/{i}?operacao=3"
                yield f"\n🔄 Enviando comando de data e hora para o relógio {i}...\n"
                try:
                    page.goto(target_url, wait_until='domcontentloaded')
                    # Wait for validation summary success or timeout
                    page.wait_for_selector('.validation-summary-ok', timeout=10000)
                    yield f"✅ Comando enviado com sucesso para o relógio {i}.\n"
                    time.sleep(0.5)
                except Exception as inner_err:
                    yield f"❌ Erro ao enviar comando para o relógio {i}: {str(inner_err)}\n"
            
            yield "\n🏁 Automação de Data e Hora concluída!\n"

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
