from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config
from db_setup import User

def verify_users():
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        users = session.query(User).all()
        print(f"Total users: {len(users)}")
        for user in users:
            print(f"User: {user.username}, Email: {user.email}, Admin: {user.is_admin}")
    finally:
        session.close()

if __name__ == "__main__":
    verify_users()
