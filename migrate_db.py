import pyodbc
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

    print("\nAtualização de Banco de Dados finalizada! Suas informações de produção estão a salvo.")

if __name__ == "__main__":
    upgrade_database_schema()
