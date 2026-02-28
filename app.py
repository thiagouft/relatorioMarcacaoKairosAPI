from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
import requests
import pandas as pd
import io
import datetime
import json
from functools import wraps
from config import Config
from db_setup import User, Log, Base
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os
import werkzeug.utils

# Import utility functions for comando
from utils_envio_comando import (
    fetch_cracha,
    unassociate_clocks,
    associate_clocks,
    schedule_commands,
    fetch_clocks,
    dismiss_employee,
    generate_pdf_report,
    generate_cabecalho_arquivo
)
app = Flask(__name__)
app.config.from_object(Config)

# Database Setup
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Session = sessionmaker(bind=engine)

def get_db_session():
    return Session()

# Login Decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Acesso negado. Requer privilégios de administrador.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def log_action(action):
    db = get_db_session()
    try:
        user_id = session.get('user_id')
        username = session.get('username')
        new_log = Log(user_id=user_id, username=username, action=action)
        db.add(new_log)
        db.commit()
    except Exception as e:
        print(f"Error logging action: {e}")
    finally:
        db.close()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db_session()
        user = db.query(User).filter_by(email=email).first()
        db.close()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username # Keep for legacy or display
            session['full_name'] = user.full_name
            session['is_admin'] = user.is_admin
            session['must_change_password'] = user.must_change_password
            
            log_action('Login realizado com sucesso')
            
            if user.must_change_password:
                return redirect(url_for('change_password'))
                
            return redirect(url_for('home'))
        else:
            flash('Email ou senha inválidos', 'danger')
            
    return render_template('login.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('As senhas não conferem.', 'danger')
            return render_template('change_password.html')
            
        db = get_db_session()
        user = db.query(User).get(session['user_id'])
        
        if user:
            user.password_hash = generate_password_hash(new_password)
            user.must_change_password = False
            db.commit()
            
            session['must_change_password'] = False
            flash('Senha alterada com sucesso.', 'success')
            db.close()
            return redirect(url_for('home'))
        
        db.close()
        
    return render_template('change_password.html')

@app.before_request
def check_password_change_required():
    if 'user_id' in session and session.get('must_change_password'):
        if request.endpoint not in ['change_password', 'logout', 'static']:
            return redirect(url_for('change_password'))

@app.route('/logout')
def logout():
    log_action('Logout realizado')
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
@login_required
def home():
    locations = sorted(CLOCK_GROUPS.keys())
    return render_template('home.html', is_admin=session.get('is_admin'), locations=locations)

# --- User Management (Admin Only) ---

@app.route('/admin/create_user', methods=['POST'])
@admin_required
def create_user():
    email = request.form['email']
    full_name = request.form['full_name']
    username = request.form['username']
    password = request.form['password']
    is_admin = 'is_admin' in request.form
    
    db = get_db_session()
    
    # Check if email exists
    if db.query(User).filter_by(email=email).first():
        flash('Email já cadastrado.', 'danger')
        db.close()
        return redirect(url_for('admin_users'))

    # Check if username exists
    if db.query(User).filter_by(username=username).first():
        flash('User Name (Login) já cadastrado.', 'danger')
        db.close()
        return redirect(url_for('admin_users'))
    
    hashed_password = generate_password_hash(password)
    new_user = User(
        username=username, 
        email=email,
        full_name=full_name,
        password_hash=hashed_password, 
        is_admin=is_admin,
        must_change_password=True
    )
    db.add(new_user)
    db.commit()
    db.close()
    
    log_action(f'Criou usuário: {email}')
    flash(f'Usuário {full_name} ({email}) criado com sucesso.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/reset_password', methods=['POST'])
@admin_required
def reset_password():
    username = request.form['username']
    new_password = request.form['new_password']
    
    db = get_db_session()
    user = db.query(User).filter_by(username=username).first()
    
    if not user:
        flash('Login não encontrado.', 'danger')
        db.close()
        return redirect(url_for('home'))
    
    user.password_hash = generate_password_hash(new_password)
    db.commit()
    db.close()
    
    log_action(f'Resetou senha do login: {username}')
    flash(f'Senha de {username} alterada com sucesso.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db_session()
    users = db.query(User).all()
    db.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/locais_ponto')
@admin_required
def admin_locais_ponto():
    return render_template('admin_locais_ponto.html')

@app.route('/admin/envio_comando')
@admin_required
def envio_comando():
    return render_template('envio_comando.html')

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    db = get_db_session()
    user = db.query(User).get(user_id)
    
    if not user:
        flash('Login não encontrado.', 'danger')
        db.close()
        return redirect(url_for('admin_users'))
        
    if user.username == 'admin':
        flash('Não é possível excluir o login admin principal.', 'danger')
        db.close()
        return redirect(url_for('admin_users'))
        
    username = user.username
    db.delete(user)
    db.commit()
    db.close()
    
    log_action(f'Excluiu login: {username}')
    flash(f'Login {username} excluído com sucesso.', 'success')
    return redirect(url_for('admin_users'))

# --- Helper Functions ---

def fetch_all_employees_map():
    """
    Fetches all employees from Kairos API and returns a dictionary {Matricula: {'Nome': ..., 'Cracha': ...}}.
    Iterates through all pages.
    """
    employees_map = {}
    page = 1
    total_pages = 1
    
    try:
        while page <= total_pages:
            payload = {
                "Pagina": page
            }
            
            response = requests.post(
                app.config['KAIROS_SEARCH_PEOPLE_URL'],
                json=payload,
                headers=app.config['KAIROS_HEADERS']
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('Sucesso'):
                    total_pages = data.get('TotalPagina', 1)
                    if 'Obj' in data:
                        for person in data['Obj']:
                            mat = person.get('Matricula')
                            nome = person.get('Nome')
                            cracha = person.get('Cracha')
                            if mat:
                                employees_map[str(mat)] = {'Nome': nome, 'Cracha': cracha}
            
            page += 1
            
    except Exception as e:
        print(f"Error fetching all employees: {e}")
        
    return employees_map

# --- Clock Groups Mapping ---
CLOCK_GROUPS = {
  "P10": [1, 11, 23,29],
  "COCA": [3, 14, 31],
  "CANTEIRO III": [7, 18, 22, 24, 25],
  "PIPE MARABA": [5, 9, 20],
  "OFICINA II": [8],
  "PIPE SAO FELIX": [2, 4, 10, 28],
  "TREINAMENTO": [16],
  "RH": [13],
  "P12": [6, 12],
  "PIPE FERROV.": [19, 21, 32],
  "TENDA MOTORISTAS III": [26],
  "NAUTICA": [30],
  "PI SAO FELIX": [35,36],
  "DOMINGO": [17, 27],
}

def get_location_by_clock_id(clock_id):
    if clock_id is None:
        return ""
    try:
        cid = int(clock_id)
        for location, ids in CLOCK_GROUPS.items():
            if cid in ids:
                return location
    except (ValueError, TypeError):
        pass
    return ""

# --- Kairos API & Reports ---

@app.route('/api/appointments', methods=['POST'])
@login_required
def get_appointments():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    selected_location = data.get('local') # Get location filter

    if not start_date or not end_date:
        return jsonify({'error': 'Datas de início e fim são obrigatórias'}), 400
        
    # Validation
    try:
        # Prevent unconverted data remains by trimming the year part if it's too long
        sd_parts = start_date.split('-')
        if len(sd_parts) == 3 and len(sd_parts[2]) > 4:
             sd_parts[2] = sd_parts[2][:4]
             start_date = "-".join(sd_parts)

        ed_parts = end_date.split('-')
        if len(ed_parts) == 3 and len(ed_parts[2]) > 4:
             ed_parts[2] = ed_parts[2][:4]
             end_date = "-".join(ed_parts)

        d1 = datetime.datetime.strptime(start_date, "%d-%m-%Y")
        d2 = datetime.datetime.strptime(end_date, "%d-%m-%Y")
        days_diff = abs((d2 - d1).days)
    except ValueError as e:
        return jsonify({'error': f'Formato de data inválido. Use o calendário.'}), 400

    req_matricula = data.get('matricula')
    if req_matricula and req_matricula.strip():
        if days_diff > 60:
             return jsonify({'error': 'Para consulta individual, o intervalo máximo é de 60 dias'}), 400
    else:
        if days_diff > 5:
             return jsonify({'error': 'Para consulta geral, o intervalo máximo é de 5 dias'}), 400

    all_records = []
    page = 1
    total_pages = 1
    
    try:
        while page <= total_pages:
            payload = {
                "DataInicio": start_date,
                "DataFim": end_date,
                "CalculoNaoAtualizado": "true",
                "Pagina": page,
                "ResponseType": "AS400V1"
            }
            
            matricula = data.get('matricula')
            if matricula and matricula.strip():
                try:
                    payload["CrachasPessoa"] = [int(matricula)]
                except ValueError:
                    return jsonify({'error': 'Matrícula deve ser um número'}), 400
            else:
                payload["IdsPessoa"] = [0]
            
            response = requests.post(
                app.config['KAIROS_API_URL'],
                json=payload,
                headers=app.config['KAIROS_HEADERS']
            )
            
            if response.status_code != 200:
                return jsonify({'error': 'Erro ao consultar API Kairos'}), 500
                
            resp_json = response.json()
            
            if not resp_json.get('Sucesso'):
                 return jsonify({'error': resp_json.get('Mensagem', 'Erro desconhecido na API')}), 500
            
            if 'Obj' in resp_json:
                all_records.extend(resp_json['Obj'])
            
            total_pages = resp_json.get('TotalPagina', 1)
            page += 1
            
        # --- Fetch Employee Names & Cracha ---
        employees_info = {}
        
        # If searching by specific matricula, fetch just that one
        if matricula and matricula.strip():
             try:
                people_payload = {"Cracha": int(matricula)}
                p_response = requests.post(
                    app.config['KAIROS_SEARCH_PEOPLE_URL'],
                    json=people_payload,
                    headers=app.config['KAIROS_HEADERS']
                )
                if p_response.status_code == 200:
                    p_data = p_response.json()
                    if p_data.get('Sucesso') and p_data.get('Obj'):
                        person_obj = p_data['Obj'][0]
                        found_name = person_obj.get('Nome', '')
                        found_cracha = person_obj.get('Cracha', '')
                        
                        # Apply this name to all records found, handling potential matricula format mismatches
                        for r in all_records:
                            r_mat = str(r.get('Matricula'))
                            employees_info[r_mat] = {'Nome': found_name, 'Cracha': found_cracha}
             except Exception as e:
                print(f"Error fetching name for matricula {matricula}: {e}")
        else:
            # Bulk fetch all employees
            employees_info = fetch_all_employees_map()
                
        # Process records for display
        processed_data = []
        for r in all_records:
            mat = r.get('Matricula')
            str_mat = str(mat)
            
            emp_data = employees_info.get(str_mat, {})
            nome = emp_data.get('Nome', '')
            display_matricula = emp_data.get('Cracha', mat)
            
            relogio_id = r.get('RelogioID')
            local = get_location_by_clock_id(relogio_id)

            # Apply location filter
            if selected_location and selected_location.strip() and selected_location != 'Todos':
                if local != selected_location:
                    continue

            processed_data.append({
                "Matricula": display_matricula,
                "Nome": nome,
                "Local": local,
                "RelogioID": relogio_id,
                "NumeroSerieRep": r.get('NumeroSerieRep'),
                "Dia": r.get('Dia'),
                "Mes": r.get('Mes'),
                "Ano": r.get('Ano'),
                "Hora": r.get('Hora'),
                "Minuto": r.get('Minuto'),
                "DataFormatada": f"{r.get('Dia'):02d}/{r.get('Mes'):02d}/{r.get('Ano')}",
                "HoraFormatada": f"{r.get('Hora'):02d}:{r.get('Minuto'):02d}"
            })
            
        # Sort by Date and Time
        processed_data.sort(key=lambda x: (x['Ano'], x['Mes'], x['Dia'], x['Hora'], x['Minuto']))
            
        log_action(f'Consultou apontamentos de {start_date} a {end_date}')
        return jsonify({'data': processed_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/locais_ponto', methods=['POST'])
@admin_required
def api_admin_locais_ponto():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    matriculas = data.get('matriculas', [])

    if not start_date or not end_date or not matriculas:
        return jsonify({'error': 'Datas e lista de matrículas são obrigatórias'}), 400
        
    try:
        sd_parts = start_date.split('-')
        if len(sd_parts) == 3 and len(sd_parts[2]) > 4:
             sd_parts[2] = sd_parts[2][:4]
             start_date = "-".join(sd_parts)

        ed_parts = end_date.split('-')
        if len(ed_parts) == 3 and len(ed_parts[2]) > 4:
             ed_parts[2] = ed_parts[2][:4]
             end_date = "-".join(ed_parts)

        datetime.datetime.strptime(start_date, "%d-%m-%Y")
        datetime.datetime.strptime(end_date, "%d-%m-%Y")
    except ValueError:
        return jsonify({'error': 'Formato de data inválido'}), 400

    grupo_crachas = {grupo: set() for grupo in CLOCK_GROUPS}
    crachas_sem_dados = []
    crachas_inexistentes = []

    try:
        for cracha in matriculas:
            payload = {
                "CrachasPessoa": [cracha],
                "DataInicio": start_date,
                "DataFim": end_date,
                "CalculoNaoAtualizado": "true",
                "ResponseType": "AS400V1"
            }
            
            response = requests.post(
                app.config['KAIROS_API_URL'],
                json=payload,
                headers=app.config['KAIROS_HEADERS']
            )
            
            if response.status_code == 200:
                resp_json = response.json()
                sucesso = resp_json.get("Sucesso")
                obj_list = resp_json.get("Obj")
                
                if sucesso and isinstance(obj_list, list) and len(obj_list) > 0:
                    relogio_ids = set()
                    for item in obj_list:
                        relogio_id = item.get("RelogioID")
                        if relogio_id is not None:
                            relogio_ids.add(relogio_id)
                            
                    for grupo, ids_grupo in CLOCK_GROUPS.items():
                        if any(relogio_id in ids_grupo for relogio_id in relogio_ids):
                            grupo_crachas[grupo].add(cracha)
                            
                elif sucesso and isinstance(obj_list, list) and len(obj_list) == 0:
                    crachas_sem_dados.append(cracha)
                elif not sucesso and obj_list is None:
                    crachas_inexistentes.append(cracha)
            else:
                print(f"Erro ao consultar api/admin/locais_ponto crachá {cracha}: {response.status_code}")
                # We log it but continue processing the rest
                
        # Convert sets to sorted lists for JSON serialization
        grupo_crachas_serializable = {
            k: sorted(list(v)) for k, v in grupo_crachas.items() if v
        }
        
        log_action(f'Consultou Locais de Ponto para {len(matriculas)} matrículas ({start_date} a {end_date})')
        
        return jsonify({
            'data': {
                'grupo_crachas': grupo_crachas_serializable,
                'crachas_sem_dados': sorted(crachas_sem_dados),
                'crachas_inexistentes': sorted(crachas_inexistentes)
            }
        })
        
    except Exception as e:
         print(f"Error in api_admin_locais_ponto: {e}")
         return jsonify({'error': str(e)}), 500

# --- Envio de Comandos API ---

@app.route('/api/envio_comando/relogios', methods=['GET'])
@admin_required
def api_envio_comando_relogios():
    relogios = fetch_clocks()
    return jsonify(relogios)

@app.route('/api/envio_comando/processar', methods=['POST'])
@admin_required
def api_envio_comando_processar():
    try:
        comandos_str = request.form.get('comandos', '{}')
        relogios_str = request.form.get('relogios', '[]')
        matriculas_str = request.form.get('matriculas', '')
        
        config_options = json.loads(comandos_str)
        relogio_list = json.loads(relogios_str)
        
        pesquisa_falha = []
        crachas_sucesso = []
        falha_file_name = None
        funcionarios = []
        
        if matriculas_str:
            matriculas_list = json.loads(matriculas_str)
            funcionarios = [int(m) for m in matriculas_list if str(m).isdigit()]
        elif 'arquivo' in request.files:
            file = request.files['arquivo']
            if file.filename != '':
                content = file.read().decode('utf-8')
                linhas = content.split('\n')
                for linha in linhas:
                    linha = linha.strip()
                    if linha and linha.isdigit():
                        funcionarios.append(int(linha))
        
        if not funcionarios:
            return jsonify({'sucesso': False, 'mensagem': 'Nenhum funcionário fornecido.'})
            
        for cracha in funcionarios:
            result = fetch_cracha(cracha)
            if not result.get('sucesso'):
                pesquisa_falha.append(result)
            else:
                crachas_sucesso.append(result)
                if result.get('semTemplates'):
                    pesquisa_falha.append({
                        'cracha': result.get('cracha'),
                        'nome': result.get('nome'),
                        'sucesso': False,
                        'mensagem': result.get('mensagem', 'Não possui Biometria'),
                        'dataDesligamento': result.get('dataDesligamento')
                    })
        
        result_response = {
            'sucesso': False,
            'mensagem': 'Nenhum crachá válido encontrado para processamento.',
            'falhas': pesquisa_falha
        }
        
        if pesquisa_falha:
            log_file_name = 'falha_consulta.txt'
            normalized = []
            for p in pesquisa_falha:
                normalized.append({
                    'cracha': p.get('cracha'),
                    'nome': p.get('nome'),
                    'sucesso': p.get('sucesso', False),
                    'mensagem': p.get('mensagem', ''),
                    'dataDesligamento': p.get('dataDesligamento')
                })
            with open(os.path.join(app.root_path, 'static', log_file_name), 'w', encoding='utf-8') as f:
                json.dump(normalized, f, indent=2, ensure_ascii=False)
            falha_file_name = log_file_name

        if crachas_sucesso:
            cracha_list = [c.get('cracha') for c in crachas_sucesso]
            schedule_result = schedule_commands(cracha_list, config_options, relogio_list)
            
            if schedule_result.get('sucesso'):
                cabecalho = generate_cabecalho_arquivo(relogio_list, config_options)
                sucesso_file_name = 'sucesso_inclusao.pdf'
                sucesso_content = [f"Crachá: {c.get('cracha')}, Nome: {c.get('nome')}" for c in crachas_sucesso]
                generate_pdf_report(os.path.join(app.root_path, 'static', sucesso_file_name), cabecalho, sucesso_content)
                
                schedule_result['sucessoFileName'] = sucesso_file_name
            
            result_response = schedule_result
            result_response['falhas'] = pesquisa_falha
            if falha_file_name:
                 result_response['falhaFileName'] = falha_file_name
                 
        log_action(f"Processado comandos para {len(funcionarios)} funcionarios")
        return jsonify(result_response)

    except Exception as e:
        print(f"Erro no processamento: {e}")
        return jsonify({'sucesso': False, 'mensagem': f'Erro ao processar: {str(e)}'}), 500

@app.route('/api/envio_comando/associar', methods=['POST'])
@admin_required
def api_envio_comando_associar():
    try:
        relogios_str = request.form.get('relogios', '[]')
        matriculas_str = request.form.get('matriculas', '')
        
        relogio_list = json.loads(relogios_str)
        if not relogio_list:
            return jsonify({'sucesso': False, 'mensagem': "Campo 'relogios' é obrigatório."}), 400
            
        comandos_list = {
            'EnviarListaCredenciais': True,
            'EnviarListaTemplate': True
        }
        
        pesquisa_falha = []
        crachas_sucesso = []
        associacao_falha = []
        falha_file_name = None
        funcionarios = []
        
        if matriculas_str:
            matriculas_list = json.loads(matriculas_str)
            funcionarios = [int(m) for m in matriculas_list if str(m).isdigit()]
        elif 'arquivo' in request.files:
            file = request.files['arquivo']
            if file.filename != '':
                content = file.read().decode('utf-8')
                linhas = content.split('\n')
                for linha in linhas:
                    linha = linha.strip()
                    if linha and linha.isdigit():
                        funcionarios.append(int(linha))
                        
        for cracha in funcionarios:
            result = fetch_cracha(cracha)
            if not result.get('sucesso'):
                pesquisa_falha.append(result)
            else:
                crachas_sucesso.append(result)
                if result.get('semTemplates'):
                    pesquisa_falha.append({
                        'cracha': result.get('cracha'),
                        'nome': result.get('nome'),
                        'sucesso': False,
                        'mensagem': result.get('mensagem', 'Não possui Biometria'),
                        'dataDesligamento': result.get('dataDesligamento')
                    })
                    
        if not crachas_sucesso:
            return jsonify({'sucesso': False, 'mensagem': "Nenhum crachá válido encontrado para processamento."})
            
        cracha_list = [c.get('cracha') for c in crachas_sucesso]
        
        unassociate_clocks(cracha_list, relogio_list)
        associacao_sucesso = associate_clocks(cracha_list, relogio_list)
        
        if not associacao_sucesso.get('sucesso'):
            associacao_falha.append({'mensagem': associacao_sucesso.get('mensagem')})
            
        if pesquisa_falha:
            log_file_name = 'falha_consulta.txt'
            normalized = []
            for p in pesquisa_falha:
                normalized.append({
                    'cracha': p.get('cracha'),
                    'nome': p.get('nome'),
                    'sucesso': p.get('sucesso', False),
                    'mensagem': p.get('mensagem', ''),
                    'dataDesligamento': p.get('dataDesligamento')
                })
            with open(os.path.join(app.root_path, 'static', log_file_name), 'w', encoding='utf-8') as f:
                json.dump(normalized, f, indent=2, ensure_ascii=False)
            falha_file_name = log_file_name
            
        if crachas_sucesso:
            cabecalho = generate_cabecalho_arquivo(relogio_list, comandos_list)
            sucesso_content = [f"Crachá: {c.get('cracha')}, Nome: {c.get('nome')}" for c in crachas_sucesso]
            sucesso_file_name = 'sucesso_associacao.pdf'
            generate_pdf_report(os.path.join(app.root_path, 'static', sucesso_file_name), cabecalho, sucesso_content)
        
        if associacao_falha:
             with open(os.path.join(app.root_path, 'static', 'falhas_associacao.json'), 'w', encoding='utf-8') as f:
                json.dump(associacao_falha, f, indent=2, ensure_ascii=False)
                
        response_payload = {
            'sucesso': True,
            'mensagem': 'Processamento concluído.',
            'detalhes': {
                'crachasProcessados': len(cracha_list),
                'falhasPesquisa': len(pesquisa_falha),
                'falhasAssociacao': len(associacao_falha)
            },
            'sucessoFileName': 'sucesso_associacao.pdf'
        }
        
        if falha_file_name:
            response_payload['falhaFileName'] = falha_file_name
            
        log_action(f"Associados relógios para {len(cracha_list)} funcionários")
        return jsonify(response_payload)
        
    except Exception as e:
        print(f"Erro ao processar crachás: {e}")
        return jsonify({'sucesso': False, 'mensagem': f'Erro ao processar: {str(e)}'}), 500

@app.route('/api/envio_comando/desligar', methods=['POST'])
@admin_required
def api_envio_comando_desligar():
    try:
        if 'arquivo' not in request.files:
            return jsonify({'sucesso': False, 'mensagem': 'Nenhum arquivo enviado.'}), 400
            
        file = request.files['arquivo']
        if file.filename == '':
             return jsonify({'sucesso': False, 'mensagem': 'Arquivo inválido.'}), 400
             
        content = file.read().decode('utf-8')
        linhas = [linha.strip() for linha in content.split('\n') if linha.strip()]
        
        cracha_list = []
        for linha in linhas:
            if len(linha) >= 19:
                cracha = linha[0:11]
                dia = linha[11:13]
                mes = linha[13:15]
                ano = linha[15:19]
                data_desligamento = f"{ano}/{mes}/{dia}"
                cracha_list.append({"Cracha": cracha, "DataDesligamento": data_desligamento})
                
        crachas_sucesso = []
        crachas_falha = []
        
        for item in cracha_list:
            cracha = item["Cracha"]
            data_desligamento = item["DataDesligamento"]
            
            result = fetch_cracha(cracha)
            if result.get('sucesso'):
                if result.get('semTemplates'):
                    crachas_falha.append({
                        "cracha": result.get('cracha'),
                        "nome": result.get('nome'),
                        "mensagem": result.get('mensagem', 'Não possui Biometria')
                    })
                
                dismiss_result = dismiss_employee(result, data_desligamento)
                if dismiss_result.get('sucesso'):
                    data_formatada = "/".join(data_desligamento.split("/")[::-1])
                    crachas_sucesso.append({
                        "cracha": result.get("cracha"),
                        "nome": result.get("nome"),
                        "dataDesligamento": data_formatada
                    })
                else:
                    crachas_falha.append({
                        "cracha": result.get("cracha"),
                        "nome": result.get("nome"),
                        "mensagem": dismiss_result.get("mensagem")
                    })
            else:
                 crachas_falha.append({
                     "cracha": cracha,
                     "nome": "Desconhecido",
                     "mensagem": result.get("mensagem")
                 })
                 
        sucesso_file_name = None
        falha_file_name = None
        
        if crachas_sucesso:
            sucesso_file_name = 'sucesso_desligamento.pdf'
            sucesso_content = [f"Crachá: {c.get('cracha')}, Nome: {c.get('nome')}, Data de Desligamento: {c.get('dataDesligamento')}" for c in crachas_sucesso]
            generate_pdf_report(os.path.join(app.root_path, 'static', sucesso_file_name), "Funcionários Desligados\n\n", sucesso_content)
            
        if crachas_falha:
            falha_file_name = 'falha_desligamento.json'
            with open(os.path.join(app.root_path, 'static', falha_file_name), 'w', encoding='utf-8') as f:
                json.dump(crachas_falha, f, indent=2, ensure_ascii=False)
                
        log_action(f"Processado desligamento de {len(cracha_list)} funcionários")
        return jsonify({
            'sucesso': True,
            'mensagem': 'Processamento de desligamento concluído.',
            'processados': len(cracha_list),
            'sucessoFileName': sucesso_file_name,
            'falhaFileName': falha_file_name
        })
        
    except Exception as e:
        print(f"Erro ao processar desligamento: {e}")
        return jsonify({'sucesso': False, 'mensagem': f'Erro ao processar: {str(e)}'}), 500

@app.route('/api/export', methods=['POST'])
@login_required
def export_excel():
    data = request.json
    records = data.get('records')
    
    if not records:
        return jsonify({'error': 'Sem dados para exportar'}), 400
        
    df = pd.DataFrame(records)
    
    # Select and rename columns if needed, or just dump everything
    # Select and rename columns if needed, or just dump everything
    # Based on requirement: "Matricula", "Nome", "Local", "RelogioID", "NumeroSerieRep", "DataFormatada", "HoraFormatada"
    columns_order = ["Matricula", "Nome", "Local", "RelogioID", "NumeroSerieRep", "DataFormatada", "HoraFormatada"]
    # Filter columns that actually exist in the data
    existing_cols = [col for col in columns_order if col in df.columns]
    df = df[existing_cols]
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
        
    output.seek(0)
    
    log_action('Exportou relatório para Excel')
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='relatorio_ponto.xlsx'
    )

@app.route('/api/export-pdf', methods=['POST'])
@login_required
def export_pdf():
    try:
        data = request.json
        records = data.get('records')
        
        if not records:
            return jsonify({'error': 'Sem dados para exportar'}), 400

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph("Relatório de Ponto", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Table Data
        # Header matches Excel export requirement: "Matricula", "Nome", "Local", "RelogioID", "NumeroSerieRep", "DataFormatada", "HoraFormatada"
        headers = ["Matrícula", "Nome", "Local", "Relógio", "N. Série", "Data", "Hora"]
        table_data = [headers]

        for r in records:
            row = [
                str(r.get('Matricula', '')),
                str(r.get('Nome', '')),
                str(r.get('Local', '')),
                str(r.get('RelogioID', '')),
                str(r.get('NumeroSerieRep', '')),
                str(r.get('DataFormatada', '')),
                str(r.get('HoraFormatada', ''))
            ]
            table_data.append(row)

        # Create Table
        t = Table(table_data)
        
        # Style
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ])
        t.setStyle(style)
        
        elements.append(t)
        doc.build(elements)
        
        buffer.seek(0)
        
        log_action('Exportou relatório para PDF')
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='relatorio_ponto.pdf'
        )

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return jsonify({'error': 'Erro ao gerar PDF'}), 500

if __name__ == '__main__':
    app.run(debug=True)
