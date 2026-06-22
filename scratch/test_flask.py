import unittest
from server import create_app, db
from schema import User, Question, QuizAttempt, Subject, AttemptAnswer
from flask import session

class FlaskAppTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        self.client = self.app.test_client()
        
        # Re-create the database in memory
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            
            # Seed minimum required data for tests
            admin = User(
                username="admin",
                email="admin@govprep.local",
                password_hash="pbkdf2:sha256:260000$test$hash",  # dummy hash
                role="admin"
            )
            student = User(
                username="student",
                email="student@govprep.local",
                password_hash="pbkdf2:sha256:260000$test$hash",  # dummy hash
                role="student"
            )
            db.session.add(admin)
            db.session.add(student)
            
            subject = Subject(name="Quantitative Aptitude", emoji="QA", description="Math questions")
            db.session.add(subject)
            
            q1 = Question(
                subject="Quantitative Aptitude",
                difficulty="Easy",
                text="What is 2+2?",
                option_a="3",
                option_b="4",
                option_c="5",
                option_d="6",
                correct_option="B",
                explanation="2+2 is 4"
            )
            db.session.add(q1)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, username, password):
        # We simulate the login route. In tests we can also directly set the session
        # but let's test the /login endpoint if we have real passwords.
        # Since we hashed a dummy password, we can also just set session variables in client.session_transaction
        pass

    def set_session(self, user_id, username, role):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['username'] = username
            sess['role'] = role

    def test_login_page(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'GovPrep', response.data)

    def test_dashboard_redirects_for_anonymous(self):
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_dashboard_loads_for_student(self):
        self.set_session(2, 'student', 'student')
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome Back', response.data)

    def test_quiz_select_page(self):
        self.set_session(2, 'student', 'student')
        response = self.client.get('/quiz')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Quantitative Aptitude', response.data)

    def test_quiz_start(self):
        self.set_session(2, 'student', 'student')
        response = self.client.post('/quiz/start', data={
            'subject': 'Quantitative Aptitude',
            'num_questions': '5',
            'duration': '5'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'What is 2+2?', response.data)

    def test_quiz_submit_and_view_result(self):
        self.set_session(2, 'student', 'student')
        # First start the quiz to populate session
        with self.client.session_transaction() as sess:
            sess['quiz_question_ids'] = [1]
            sess['quiz_subject'] = 'Quantitative Aptitude'
            sess['quiz_duration_seconds'] = 300
            sess['user_id'] = 2
            sess['username'] = 'student'
            sess['role'] = 'student'
            
        response = self.client.post('/quiz/submit', data={
            'answers_json': '{"1": "B"}',
            'time_taken': '30'
        })
        self.assertEqual(response.status_code, 302) # Redirects to result
        
        # Test result page
        result_response = self.client.get('/quiz/result/1')
        self.assertEqual(result_response.status_code, 200)
        self.assertIn(b'Score', result_response.data)

    def test_admin_page_denied_for_student(self):
        self.set_session(2, 'student', 'student')
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.headers['Location'])

    def test_admin_page_allowed_for_admin(self):
        self.set_session(1, 'admin', 'admin')
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)

    def test_download_all_attempts_csv(self):
        self.set_session(2, 'student', 'student')
        # Create a mock attempt first
        with self.app.app_context():
            attempt = QuizAttempt(
                user_id=2,
                subject='Quantitative Aptitude',
                total_questions=1,
                correct_answers=1,
                percentage=100.0,
                time_taken=10
            )
            db.session.add(attempt)
            db.session.commit()
            
        response = self.client.get('/download/all-attempts/csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        self.assertIn(b'Quiz Attempts Report', response.data)

    def test_dashboard_with_attempts(self):
        self.set_session(2, 'student', 'student')
        with self.app.app_context():
            attempt1 = QuizAttempt(
                user_id=2,
                subject='Quantitative Aptitude',
                total_questions=10,
                correct_answers=8,
                percentage=80.0,
                time_taken=300
            )
            attempt2 = QuizAttempt(
                user_id=2,
                subject='Reasoning',
                total_questions=10,
                correct_answers=9,
                percentage=90.0,
                time_taken=540
            )
            db.session.add(attempt1)
            db.session.add(attempt2)
            db.session.commit()
            
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Quantitative Aptitude', response.data)
        self.assertIn(b'Reasoning', response.data)
        self.assertIn(b'80.0%', response.data)
        self.assertIn(b'90.0%', response.data)

if __name__ == '__main__':
    unittest.main()
