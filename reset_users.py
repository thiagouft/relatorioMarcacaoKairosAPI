from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from config import Config
from db_setup import User, Base

def reset_users():
    # Connect to the database
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Delete all existing users
        print("Deleting all existing users...")
        session.query(User).delete()
        session.commit()
        print("All users deleted.")

        # Create master user
        print("Creating master user...")
        hashed_password = generate_password_hash('123')
        master_user = User(
            username='master',
            email='adm@mixestec.com.br',
            full_name='Master Admin',
            password_hash=hashed_password,
            is_admin=True,
            must_change_password=False
        )
        session.add(master_user)
        session.commit()
        print("Master user created successfully.")
        print("Email: adm@mixestec.com.br")
        print("Password: 123")

    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    reset_users()
