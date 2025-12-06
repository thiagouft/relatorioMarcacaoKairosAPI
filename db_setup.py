import pyodbc
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash
import datetime
from config import Config

# 1. Create Database if not exists (using raw pyodbc because sqlalchemy needs an existing DB to connect usually, or master)
def create_database():
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True) # Nullable in case user is deleted or system action
    username = Column(String(50), nullable=True) # Store username for easier history
    action = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# 3. Create Tables and Seed Admin
def init_db():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Base.metadata.create_all(engine)
    
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
    
    session.close()

if __name__ == "__main__":
    create_database()
    init_db()
