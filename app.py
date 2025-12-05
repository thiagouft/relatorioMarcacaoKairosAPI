from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
import requests
import pandas as pd
import io
import datetime
from functools import wraps
from config import Config
from db_setup import User, Log, Base

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
            return redirect(url_for('dashboard'))
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
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db_session()
        user = db.query(User).filter_by(username=username).first()
        db.close()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            log_action('Login realizado com sucesso')
            return redirect(url_for('dashboard'))
        else:
            flash('Login ou senha inválidos', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_action('Logout realizado')
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', is_admin=session.get('is_admin'))

# --- User Management (Admin Only) ---

@app.route('/admin/create_user', methods=['POST'])
@admin_required
def create_user():
    username = request.form['username']
    password = request.form['password']
    is_admin = 'is_admin' in request.form
    
    db = get_db_session()
    if db.query(User).filter_by(username=username).first():
        flash('Login já existe.', 'danger')
        db.close()
        return redirect(url_for('dashboard'))
    
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password, is_admin=is_admin)
    db.add(new_user)
    db.commit()
    db.close()
    
    log_action(f'Criou login: {username}')
    flash(f'Login {username} criado com sucesso.', 'success')
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
        return redirect(url_for('dashboard'))
    
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

# --- Kairos API & Reports ---

@app.route('/api/appointments', methods=['POST'])
@login_required
def get_appointments():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Datas de início e fim são obrigatórias'}), 400
        
    # Validation: Max 30 days
    d1 = datetime.datetime.strptime(start_date, "%d-%m-%Y")
    d2 = datetime.datetime.strptime(end_date, "%d-%m-%Y")
    if abs((d2 - d1).days) > 30:
         return jsonify({'error': 'O intervalo máximo é de 30 dias'}), 400

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
            
        # Process records for display
        processed_data = []
        for r in all_records:
            processed_data.append({
                "Matricula": r.get('Matricula'),
                "RelogioID": r.get('RelogioID'),
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

@app.route('/api/export', methods=['POST'])
@login_required
def export_excel():
    data = request.json
    records = data.get('records')
    
    if not records:
        return jsonify({'error': 'Sem dados para exportar'}), 400
        
    df = pd.DataFrame(records)
    
    # Select and rename columns if needed, or just dump everything
    # Based on requirement: "Matricula", "RelogioID", "NumeroSerieRep", "DataFormatada", "HoraFormatada"
    columns_order = ["Matricula", "RelogioID", "NumeroSerieRep", "DataFormatada", "HoraFormatada"]
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

if __name__ == '__main__':
    app.run(debug=True)
