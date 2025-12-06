import pyodbc
from config import Config

def update_schema():
    conn_str = f"DRIVER={Config.DRIVER};SERVER={Config.SERVER};DATABASE={Config.DATABASE};UID={Config.USERNAME};PWD={Config.PASSWORD};"
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        
        print("Updating schema...")
        
        # Add email column
        try:
            cursor.execute("ALTER TABLE users ADD email VARCHAR(120)")
            print("Added email column.")
        except Exception as e:
            print(f"Email column might already exist: {e}")

        # Add full_name column
        try:
            cursor.execute("ALTER TABLE users ADD full_name VARCHAR(100)")
            print("Added full_name column.")
        except Exception as e:
            print(f"full_name column might already exist: {e}")

        # Add must_change_password column
        try:
            cursor.execute("ALTER TABLE users ADD must_change_password BIT DEFAULT 1")
            print("Added must_change_password column.")
        except Exception as e:
            print(f"must_change_password column might already exist: {e}")
            
        # Update existing admin to have an email if null
        try:
            cursor.execute("UPDATE users SET email = 'admin@kairos.com', full_name = 'Administrador', must_change_password = 0 WHERE username = 'admin' AND email IS NULL")
            print("Updated admin user.")
        except Exception as e:
            print(f"Error updating admin: {e}")

        conn.close()
        print("Schema update complete.")
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    update_schema()
