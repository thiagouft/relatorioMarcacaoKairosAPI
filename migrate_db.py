import pyodbc
import os
import shutil
from sqlalchemy import create_engine, inspect, text
from db_setup import Base, Config

def upgrade_database_schema():
    print("Iniciando verificação de atualização do banco de dados (Produção)...")
    
    # 1. Conecta ao banco de produção
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    
    # 2. Cria tabelas inteiramente novas (O create_all não apaga tabelas existentes)
    Base.metadata.create_all(engine)
    print("Verificação de novas tabelas (como 'logs') concluída.")
    
    # Carga de dados iniciais do CPRT
    from db_setup import seed_initial_data
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        seed_initial_data(session)
    except Exception as e:
        print(f"Erro ao rodar seed inicial na migração: {e}")
    finally:
        session.close()
    
    # 3. Inspeciona a estrutura para encontrar colunas que foram adicionadas no código Python
    # mas que ainda não existem no banco de dados.
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        for table_name, table in Base.metadata.tables.items():
            if inspector.has_table(table_name):
                # Extrai a lista de colunas que já existem fisicamente no banco
                existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
                
                # Para cada coluna projetada no sistema (app.py ou db_setup.py)
                for column in table.columns:
                    if column.name not in existing_columns:
                        print(f"-> Oops! Nova coluna '{column.name}' detectada para a tabela '{table_name}'.")
                        
                        # Extrai o tipo exato que o SQL Server utiliza
                        compiled_type = column.type.compile(engine.dialect)
                        
                        nullable = "NULL" if column.nullable else "NOT NULL"
                        
                        # Trata os valores padrões genéricos para não explodir em tabelas pré-cheias
                        default_val = ""
                        if not column.nullable and column.default is not None:
                            val = column.default.arg
                            if callable(val):
                                # Evita rodar funções em strings no ALTER TABLE
                                pass
                            elif isinstance(val, str):
                                default_val = f" DEFAULT '{val}'"
                            elif isinstance(val, bool):
                                default_val = f" DEFAULT {1 if val else 0}"
                            elif isinstance(val, (int, float)):
                                default_val = f" DEFAULT {val}"
                                
                        alter_cmd = f"ALTER TABLE {table_name} ADD {column.name} {compiled_type} {nullable}{default_val}"
                        
                        try:
                            conn.execute(text(alter_cmd))
                            conn.commit()
                            print(f"    [Sucesso] Coluna '{column.name}' injetada na tabela '{table_name}' sem perda de dados.")
                        except Exception as e:
                            print(f"    [Erro] Falha ao injetar '{column.name}': {e}")

    migrate_physical_files_and_db_paths(engine)
    print("\nAtualização de Banco de Dados finalizada! Suas informações de produção estão a salvo.")

def migrate_physical_files_and_db_paths(engine):
    print("\nIniciando migração física de arquivos e caminhos no banco de dados...")
    
    # 1. Migração física dos arquivos
    static_path = os.path.join(os.path.dirname(__file__), 'static')
    documents_path = os.path.join(static_path, 'documents')
    
    # Garante a existência da pasta documents
    if not os.path.exists(documents_path):
        os.makedirs(documents_path, exist_ok=True)
        print(f"Diretório de documentos criado em: {documents_path}")
        
    if os.path.exists(static_path):
        moved_count = 0
        for filename in os.listdir(static_path):
            file_path = os.path.join(static_path, filename)
            # Apenas arquivos (não diretórios) com extensões conhecidas na raiz de static
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.pdf', '.txt', '.json']:
                    dest_path = os.path.join(documents_path, filename)
                    try:
                        shutil.move(file_path, dest_path)
                        moved_count += 1
                        print(f"  [Mover] {filename} -> static/documents/{filename}")
                    except Exception as move_err:
                        print(f"  [Erro Mover] Falha ao mover {filename}: {move_err}")
        print(f"Total de arquivos físicos movidos para a pasta 'documents': {moved_count}")
        
    # 2. Atualização dos caminhos no banco de dados
    with engine.connect() as conn:
        try:
            # Atualiza agendamento_comandos (sucesso_file)
            r1 = conn.execute(text("""
                UPDATE agendamento_comandos 
                SET sucesso_file = 'documents/' + sucesso_file 
                WHERE sucesso_file IS NOT NULL 
                  AND sucesso_file <> '' 
                  AND sucesso_file NOT LIKE 'documents/%'
            """))
            
            # Atualiza agendamento_comandos (falha_file)
            r2 = conn.execute(text("""
                UPDATE agendamento_comandos 
                SET falha_file = 'documents/' + falha_file 
                WHERE falha_file IS NOT NULL 
                  AND falha_file <> '' 
                  AND falha_file NOT LIKE 'documents/%'
            """))
            
            # Atualiza comandos_recorrentes (log_file)
            r3 = conn.execute(text("""
                UPDATE comandos_recorrentes 
                SET log_file = 'documents/' + log_file 
                WHERE log_file IS NOT NULL 
                  AND log_file <> '' 
                  AND log_file NOT LIKE 'documents/%'
            """))
            
            conn.commit()
            print(f"Caminhos atualizados no banco de dados:")
            print(f"  - agendamento_comandos (sucesso_file): {r1.rowcount} linhas")
            print(f"  - agendamento_comandos (falha_file): {r2.rowcount} linhas")
            print(f"  - comandos_recorrentes (log_file): {r3.rowcount} linhas")
        except Exception as db_err:
            print(f"[Erro DB] Falha ao atualizar caminhos no banco de dados: {db_err}")
            
    print("Migração de arquivos e banco de dados finalizada com sucesso!\n")

if __name__ == "__main__":
    upgrade_database_schema()
