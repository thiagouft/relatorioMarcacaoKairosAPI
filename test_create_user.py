import unittest
from app import app, get_db_session, User
from werkzeug.security import generate_password_hash

class TestCreateUser(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        self.db = get_db_session()

        # Ensure admin exists
        admin = self.db.query(User).filter_by(email='adm@mixestec.com.br').first()
        if not admin:
            admin = User(
                username='master',
                email='adm@mixestec.com.br',
                full_name='Master Admin',
                password_hash=generate_password_hash('123'),
                is_admin=True,
                must_change_password=False
            )
            self.db.add(admin)
            self.db.commit()

    def tearDown(self):
        # Clean up test user
        user = self.db.query(User).filter_by(username='testuser_manual').first()
        if user:
            self.db.delete(user)
            self.db.commit()
        self.db.close()

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def test_create_user_manual_username(self):
        # Login as admin
        self.login('adm@mixestec.com.br', '123')

        # Create user with manual username
        response = self.client.post('/admin/create_user', data=dict(
            full_name='Test User',
            username='testuser_manual',
            email='test@example.com',
            password='password123'
        ), follow_redirects=True)

        # Check if user exists in DB
        user = self.db.query(User).filter_by(username='testuser_manual').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.full_name, 'Test User')
        
        print("\nTeste de criação de usuário com username manual: SUCESSO")

if __name__ == '__main__':
    unittest.main()
