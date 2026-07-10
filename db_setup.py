from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash
import datetime
from config import Config
import json

# 1. Create Database if not exists (using raw pyodbc because sqlalchemy needs an existing DB to connect usually, or master)
def create_database():
    import pyodbc
    conn_str = f"DRIVER={Config.DRIVER};SERVER={Config.SERVER};UID={Config.USERNAME};PWD={Config.PASSWORD};"
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT name FROM master.dbo.sysdatabases WHERE name = ?", Config.DATABASE)
        if not cursor.fetchone():
            print(f"Creating database {Config.DATABASE}...")
            cursor.execute(f"CREATE DATABASE {Config.DATABASE}")
        else:
            print(f"Database {Config.DATABASE} already exists.")
            
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")

# 2. Define Models
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False) # Keeping for internal ref or legacy, but login will be email
    email = Column(String(120), unique=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=True)
    menu_permissions = Column(String(500), default='{}')  # JSON string for menu permissions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True) # Nullable in case user is deleted or system action
    username = Column(String(50), nullable=True) # Store username for easier history
    action = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(500), nullable=False)

class Horario(Base):
    __tablename__ = 'horarios'
    codigo = Column(String(50), primary_key=True)
    descricao = Column(String(200), nullable=False)

class Secao(Base):
    __tablename__ = 'secoes'
    codigo = Column(String(50), primary_key=True)
    descricao = Column(String(200), nullable=False)

class Gerencia(Base):
    __tablename__ = 'gerencias'
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False)

class GerenciaSecao(Base):
    __tablename__ = 'gerencia_secoes'
    gerencia_id = Column(Integer, ForeignKey('gerencias.id'), primary_key=True)
    secao_codigo = Column(String(50), ForeignKey('secoes.codigo'), primary_key=True)

class Situacao(Base):
    __tablename__ = 'situacoes'
    id = Column(Integer, primary_key=True)
    descricao = Column(String(100), unique=True, nullable=False)

class Pessoa(Base):
    __tablename__ = 'pessoas'
    chapa = Column(String(50), primary_key=True)
    nome = Column(String(100), nullable=False)
    nome_funcao = Column(String(100), nullable=True)
    data_admissao = Column(DateTime, nullable=True)
    data_demissao = Column(DateTime, nullable=True)
    pis_pasep = Column(String(50), nullable=True)
    cpf = Column(String(50), nullable=True)
    data_nascimento = Column(DateTime, nullable=True)
    horario_codigo = Column(String(50), ForeignKey('horarios.codigo'), nullable=True)
    secao_codigo = Column(String(50), ForeignKey('secoes.codigo'), nullable=True)
    situacao_id = Column(Integer, ForeignKey('situacoes.id'), nullable=True)

HORARIOS = [{'codigo': '3001900001', 'descricao': 'Seg. à Qui. 07:00 às 17:00 / Sex 07:00 às 16:00 / Almoço rigido 12:00 às 13:00'}, {'codigo': '3001900025', 'descricao': 'Seg. à Sex. 07:00 as 13:00 - Estagiario'}, {'codigo': '3001900006', 'descricao': 'Seg. à Qui. 16:30 às 02:00 / Sex. 15:30 às 00:00 - / Almoço 19:30 às 20:30'}, {'codigo': '3001900010', 'descricao': 'Seg à Qui. 23:00 às 08:00/ Sex 23:00 às 07:00 / Janta 03:00 ás 04:00'}, {'codigo': '3001900026', 'descricao': 'HORARIO -  Seg. a Qui. 07:00 às 16:00 (APENAS COM AUTORIZAÇÃO QUE PODE SE USAR)'}, {'codigo': '3001900037', 'descricao': 'Seg. á Qui. 17:00 às 02:22 / Sex. 16:00 ás 00:37 / Janta 21:00 às 22:00'}, {'codigo': '3001900019', 'descricao': 'Seg à Qui. 05:00 às 15:00 / Sex 05:00 às 14:00 / Almoço 11:00 às 12:00'}, {'codigo': '3001900023', 'descricao': 'Seg. à Qui. 22:00 às 07:00 / Sex 22:00 ás 06:00 / Janta 23:30 ás 00:30'}, {'codigo': '3001900003', 'descricao': 'Seg. à Qui. 14:00 às 23:45 / Sex. 13:00 às 22:00 - / Almoço 18:00 às 19:00'}, {'codigo': '3001900020', 'descricao': 'Seg. á Qui. 17:30 às 02:46 / Sex. 16:30 ás 01:46 / Almoço 22:30: às 23:30'}, {'codigo': '3001900002', 'descricao': 'Seg. à Sex. 07:00 às 14:00 / Almoço rigido 12:00 às 13:00'}, {'codigo': '3001900017', 'descricao': 'Seg à Qui. 21:00 às 06:09 / Sex 21:00 às 05:09 / Jantar 22:30 ás 23:30'}, {'codigo': '3001900009', 'descricao': 'Seg. à Sex. 13:00 às 17:00 - Jovem Aprendiz'}, {'codigo': '3001900008', 'descricao': 'Seg. à Sex. 07:00 às 11:00 - Jovem Aprendiz'}, {'codigo': '3001900005', 'descricao': 'Seg à Qui. 21:00 às 06:09 / Sex 21:00 às 05:09 / Janta 10:30 ás 11:30'}, {'codigo': '3001900021', 'descricao': 'Seg. à Sex. 08:00 às 12:00 - Jovem Aprendiz'}, {'codigo': '3001900022', 'descricao': 'Seg. à Sex. 14:00 às 18:00 - Jovem Aprendiz'}, {'codigo': '3001900024', 'descricao': 'MARITIMO - NAUTICA'}, {'codigo': '3001900007', 'descricao': 'Seg. á Qui. 19:00 às 04:20 / Sex. 19:00 ás 03:00 / Almoço 22:00 às 23:00'}, {'codigo': '3001900038', 'descricao': 'JORNADA - 1 - 12 x 36 - Seg. á Sex. 07:00 ás 19:00 / Almoço  12:00 às 13:00'}, {'codigo': '3001900044', 'descricao': 'Seg. à Sex. 07:00 às 10:00 - Medico do trabalho 02'}, {'codigo': '3001900041', 'descricao': 'JORNADA - 12 x 36 -Seg. á Sext.19:00 às 07:00   / janta 22:00  às 23:00'}]

SECOES = [{'codigo': '0004.002.30019.2.00100', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI - ADMINISTRAÇÃO'}, {'codigo': '0004.002.30019.2.21000', 'descricao': 'CPRT  - GSB -  ADM'}, {'codigo': '0004.002.30019.2.15000', 'descricao': 'CPRT  - GEN -  ADM'}, {'codigo': '0004.002.30019.2.18001', 'descricao': 'CPRT - GPC -  CENTRAIS ARMACAO E CARPINTARIA'}, {'codigo': '0004.002.30019.2.20008', 'descricao': 'CPRT  - GPC -  FUNDACAO'}, {'codigo': '0004.002.30019.2.14001', 'descricao': 'CPRT  - GSU -  OPERACIONAL'}, {'codigo': '0004.002.30019.2.00003', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOD - PRODUÇÃO TERRAPLENAGEM'}, {'codigo': '0004.002.30019.2.19001', 'descricao': 'CPRT  - GPT -  TERRAPLENAGEM'}, {'codigo': '0004.002.30019.2.17002', 'descricao': 'CPRT  - GQL -  LABORATORIO'}, {'codigo': '0004.002.30019.2.00002', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOD - PRODUÇÃO OAE DIR'}, {'codigo': '0004.002.30019.2.20010', 'descricao': 'CPRT  - GPC -  MONTAGEM DE PRE-MOLDADOS E EXECUCAO IN-LOCO'}, {'codigo': '0004.002.30019.2.20005', 'descricao': 'CPRT  - GEQ -  MOVIMENTACAO DE CARGA'}, {'codigo': '0004.002.30019.2.13000', 'descricao': 'CPRT  - GAF -  ADM'}, {'codigo': '0004.002.30019.2.18002', 'descricao': 'CPRT - GPC -\xa0 PIPE-SHOP / EMPURRE SUPERESTRUTURA'}, {'codigo': '0004.002.30019.2.15001', 'descricao': 'CPRT  - GEN -  OPERACIONAL'}, {'codigo': '0004.002.30019.2.20004', 'descricao': 'CPRT  - GEQ  -  ELETRICA'}, {'codigo': '0004.002.30019.2.20006', 'descricao': 'CPRT  - GPC -  CENTRAIS DE CONCRETO'}, {'codigo': '0004.002.30019.2.00102', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI - EQUIPAMENTOS'}, {'codigo': '0004.002.30019.2.18003', 'descricao': 'CPRT  - GPC -  OBRAS CIVIS EM GERAL'}, {'codigo': '0004.002.30019.2.16001', 'descricao': 'CPRT  - GPL -  OPERACIONAL'}, {'codigo': '0004.002.30019.2.14000', 'descricao': 'CPRT  - GSU -  ADM'}, {'codigo': '0004.002.30019.2.13001', 'descricao': 'CPRT  - GAF -  TRANSPORTE'}, {'codigo': '0004.002.30019.2.00109', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI -  SUSTENTABILIDADE'}, {'codigo': '0004.002.30019.2.20000', 'descricao': 'CPRT  - GEQ -  ADM'}, {'codigo': '0004.002.30019.2.20003', 'descricao': 'CPRT  - GEQ  -  MANUTENCAO EQUIPAMENTOS'}, {'codigo': '0004.002.30019.2.00101', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI - ENGENHARIA OPERACIONAL'}, {'codigo': '0004.002.30019.2.17000', 'descricao': 'CPRT  - GQL -  ADM'}, {'codigo': '0004.002.30019.2.20002', 'descricao': 'CPRT  - GEQ -  LUBRIFICACAO E LAVAGEM'}, {'codigo': '0004.002.30019.2.00106', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI -  PLANEJAMENTO'}, {'codigo': '0004.002.30019.2.16000', 'descricao': 'CPRT  - GPL -  ADM'}, {'codigo': '0004.002.30019.2.00103', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI - EQUIPAMENTOS MANUTENÇÃO'}, {'codigo': '0004.002.30019.2.00104', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI -  MOVIMENTAÇÃO DE CARGA'}, {'codigo': '0004.002.30019.2.00108', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI -  SUPRIMENTOS'}, {'codigo': '0004.002.30019.2.17001', 'descricao': 'CPRT  - GQL -  QUALIDADE OPERACIONAL'}, {'codigo': '0004.002.30019.2.20009', 'descricao': 'CPRT  - GPC -  ATIVIDADE NAUTICA'}, {'codigo': '0004.002.30019.2.19000', 'descricao': 'CPRT  - GPT -  ADM'}, {'codigo': '0004.002.30019.2.00107', 'descricao': 'CONSORCIO PONTE RIO TOCANTINS MOI -  QUALIDADE'}, {'codigo': '0004.002.30019.2.22000', 'descricao': 'CPRT  - GPF -  ADM'}, {'codigo': '0004.002.30019.2.18004', 'descricao': 'CPRT - GPC -\xa0 LADO MARABA PIPE-SHOP / EMPURRE SUPERESTRUTURA'}, {'codigo': '0004.002.30019.2.22001', 'descricao': 'CPRT  - GPF -  OPERACIONAL'}, {'codigo': '0004.002.30019.2.21001', 'descricao': 'CPRT  - GSB -  OPERACIONAL'}, {'codigo': '0004.002.30019.2.18000', 'descricao': 'CPRT  - GPC -  ADM'}, {'codigo': '0004.002.30019.2.12000', 'descricao': 'CPRT  - GAC - ADM'}, {'codigo': '0004.002.30019.2.19003', 'descricao': 'CPRT  - GPT -  DRENAGEM'}]

SITUACAO_SEED = [{'descricao': 'Demitido'}, {'descricao': 'Ativo'}, {'descricao': 'Af.Previdência'}, {'descricao': 'Licença Mater.'}, {'descricao': 'Af.Ac.Trabalho'}, {'descricao': 'Férias'}, {'descricao': 'Admissão prox.mês'}, {'descricao': 'Prisão / Cárcere'}, {'descricao': 'Contrato de Trabalho Suspenso'}, {'descricao': 'Serv.Militar'}]

GERENCIAS = [{'gerente': 'ANDERSON REIS - SUSTENTABILIDADE', 'secao': '0004.002.30019.2.14001'}, {'gerente': 'ANDERSON REIS - SUSTENTABILIDADE', 'secao': '0004.002.30019.2.14000'}, {'gerente': 'RONALDO SABINO', 'secao': '0004.002.30019.2.16001'}, {'gerente': 'RONALDO SABINO', 'secao': '0004.002.30019.2.16000'}, {'gerente': 'MARIA DE FATIMA', 'secao': '0004.002.30019.2.21000'}, {'gerente': 'DECIO MAURO', 'secao': '0004.002.30019.2.17002'}, {'gerente': 'DECIO MAURO', 'secao': '0004.002.30019.2.17000'}, {'gerente': 'DECIO MAURO', 'secao': '0004.002.30019.2.17001'}, {'gerente': 'DECIO MAURO', 'secao': '0004.002.30019.2.20006'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.20008'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.20010'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.18002'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.18003'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.22000'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.22001'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.18004'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.20009'}, {'gerente': 'GUSTAVO MAGALHAES', 'secao': '0004.002.30019.2.18001'}, {'gerente': 'FERNANDO DUARTE', 'secao': '0004.002.30019.2.15000'}, {'gerente': 'FERNANDO DUARTE', 'secao': '0004.002.30019.2.15001'}, {'gerente': 'LUIZ NAUFEL', 'secao': '0004.002.30019.2.20005'}, {'gerente': 'LUIZ NAUFEL', 'secao': '0004.002.30019.2.20004'}, {'gerente': 'LUIZ NAUFEL', 'secao': '0004.002.30019.2.20003'}, {'gerente': 'LUIZ NAUFEL', 'secao': '0004.002.30019.2.20002'}, {'gerente': 'LUIZ NAUFEL', 'secao': '0004.002.30019.2.20000'}, {'gerente': 'MARIA DE FATIMA', 'secao': '0004.002.30019.2.12000'}, {'gerente': 'OTTO MENDES', 'secao': '0004.002.30019.2.13000'}, {'gerente': 'OTTO MENDES', 'secao': '0004.002.30019.2.13001'}, {'gerente': 'IGOR DA MATA /  DANIEL PALHARES', 'secao': '0004.002.30019.2.19001'}, {'gerente': 'IGOR DA MATA /  DANIEL PALHARES', 'secao': '0004.002.30019.2.19000'}, {'gerente': 'IGOR DA MATA /  DANIEL PALHARES', 'secao': '0004.002.30019.2.19003'}]

def seed_initial_data(session):
    # 1. Seed Horários
    try:
        for item in HORARIOS:
            code = item['codigo']
            desc = item['descricao']
            exists = session.query(Horario).filter_by(codigo=code).first()
            if not exists:
                session.add(Horario(codigo=code, descricao=desc))
        session.commit()
        print("Horários seeded statically.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding Horários: {e}")
        
    # 2. Seed Seções
    try:
        for item in SECOES:
            code = item['codigo']
            desc = item['descricao']
            exists = session.query(Secao).filter_by(codigo=code).first()
            if not exists:
                session.add(Secao(codigo=code, descricao=desc))
        session.commit()
        print("Seções seeded statically.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding Seções: {e}")

    # 3. Seed Situações
    try:
        for item in SITUACAO_SEED:
            desc = item['descricao']
            exists = session.query(Situacao).filter_by(descricao=desc).first()
            if not exists:
                session.add(Situacao(descricao=desc))
        session.commit()
        print("Situações seeded statically.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding Situações: {e}")

    # 4. Seed Gerência
    try:
        for item in GERENCIAS:
            mgr_name = item['gerente']
            sec_code = item['secao']
            manager = session.query(Gerencia).filter_by(nome=mgr_name).first()
            if not manager:
                manager = Gerencia(nome=mgr_name)
                session.add(manager)
                session.commit() # commit to get ID
            
            link_exists = session.query(GerenciaSecao).filter_by(gerencia_id=manager.id, secao_codigo=sec_code).first()
            if not link_exists:
                session.add(GerenciaSecao(gerencia_id=manager.id, secao_codigo=sec_code))
        session.commit()
        print("Gerência seeded statically.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding Gerência: {e}")

# 3. Create Tables and Seed Admin
def init_db():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Base.metadata.create_all(engine)

    # Ensure existing DB has the new menu_permissions column
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'menu_permissions'"
        ))
        count = result.scalar()
        if count == 0:
            print("Adicionando coluna menu_permissions à tabela users...")
            conn.execute(text(
                "ALTER TABLE users ADD menu_permissions VARCHAR(500) NOT NULL DEFAULT ('{}')"
            ))
            conn.commit()
            print("Coluna menu_permissions adicionada com sucesso.")

    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Check if admin exists
    admin = session.query(User).filter_by(username='admin').first()
    if not admin:
        print("Creating admin user...")
        hashed_password = generate_password_hash('admin123') # Default password
        new_admin = User(
            username='admin', 
            email='admin@kairos.com',
            full_name='Administrador',
            password_hash=hashed_password, 
            is_admin=True,
            must_change_password=False
        )
        session.add(new_admin)
        session.commit()
        print("Admin user created. Email: admin@kairos.com, Password: admin123")
    else:
        print("Admin user already exists.")
    
    # Seed initial data
    seed_initial_data(session)
    
    session.close()

if __name__ == "__main__":
    create_database()
    init_db()
