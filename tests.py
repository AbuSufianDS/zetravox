import unittest
import csv
import time
import sys
from datetime import datetime, timezone, timedelta
from app import create_app, db
from app.models import User, Post, Comment, Message, Notification, Like, ChatMessage, FriendRequest, BlockedUser
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    ELASTICSEARCH_URL = None
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    LOGIN_DISABLED = False
    SERVER_NAME = 'localhost'
    PREFERRED_URL_SCHEME = 'http'
    RATELIMIT_ENABLED = False


class TestResultCollector:
    results = []

    @classmethod
    def add_result(cls, test_name, status, execution_time):
        cls.results.append({
            'test_name': test_name,
            'status': status,
            'execution_time': round(execution_time, 3),
            'timestamp': datetime.now().isoformat()
        })

    @classmethod
    def save_to_csv(cls):
        if not cls.results:
            return

        filename = f'test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ZETRAVOX TEST EXECUTION REPORT'])
            writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([])
            writer.writerow(['Test Name', 'Status', 'Execution Time (s)', 'Timestamp'])

            for result in cls.results:
                writer.writerow([
                    result['test_name'],
                    result['status'],
                    result['execution_time'],
                    result['timestamp']
                ])

            passed = len([r for r in cls.results if r['status'] == 'PASS'])
            failed = len([r for r in cls.results if r['status'] == 'FAIL'])
            total = len(cls.results)

            writer.writerow([])
            writer.writerow(['SUMMARY'])
            writer.writerow(['Total Tests', total])
            writer.writerow(['Passed', passed])
            writer.writerow(['Failed', failed])
            writer.writerow(['Success Rate', f"{(passed / total * 100):.2f}%" if total > 0 else "0%"])

        print(f"\n✓ Test report saved to: {filename}")
        return filename


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        self.start_time = time.time()
        self.create_test_users()

    def tearDown(self):
        execution_time = time.time() - self.start_time
        test_name = f"{self.__class__.__name__}.{self._testMethodName}"

        # Check if test failed
        has_error = False
        if hasattr(self, '_outcome'):
            result = self._outcome.result
            if hasattr(result, 'failures') or hasattr(result, 'errors'):
                has_error = len(result.failures) > 0 or len(result.errors) > 0

        status = 'FAIL' if has_error else 'PASS'

        TestResultCollector.add_result(test_name, status, execution_time)

        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @classmethod
    def tearDownClass(cls):
        TestResultCollector.save_to_csv()

    def create_test_users(self):
        self.user1 = User(username='testuser1', email='test1@example.com')
        self.user1.set_password('password123')

        self.user2 = User(username='testuser2', email='test2@example.com')
        self.user2.set_password('password123')

        self.admin_user = User(username='admin', email='admin@example.com', is_admin=True)
        self.admin_user.set_password('admin123')

        db.session.add_all([self.user1, self.user2, self.admin_user])
        db.session.commit()

    def login_user(self, username='testuser1', password='password123'):
        return self.client.post('/auth/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def logout_user(self):
        return self.client.get('/auth/logout', follow_redirects=True)


class UnitTests(BaseTestCase):

    def test_user_creation(self):
        user = User(username='newuser', email='new@example.com')
        user.set_password('secure123')
        db.session.add(user)
        db.session.commit()

        retrieved_user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(retrieved_user)
        self.assertEqual(retrieved_user.email, 'new@example.com')
        self.assertTrue(retrieved_user.check_password('secure123'))

    def test_password_hashing(self):
        user = User(username='hashtest', email='hash@example.com')
        user.set_password('Secret@123')
        db.session.add(user)
        db.session.commit()

        self.assertIsNotNone(user.password_hash)
        self.assertTrue(user.check_password('Secret@123'))
        self.assertFalse(user.check_password('WrongPassword'))

    def test_avatar_generation(self):
        user = User(username='avataruser', email='avatar@example.com')
        db.session.add(user)
        db.session.commit()

        avatar_url = user.avatar(128)
        self.assertIsInstance(avatar_url, str)
        self.assertIn('gravatar', avatar_url.lower())

    def test_follow_functionality(self):
        self.user1.follow(self.user2)
        db.session.commit()

        self.assertTrue(self.user1.is_following(self.user2))
        self.assertEqual(self.user1.following_count(), 1)
        self.assertEqual(self.user2.followers_count(), 1)

    def test_unfollow_functionality(self):
        self.user1.follow(self.user2)
        db.session.commit()

        self.user1.unfollow(self.user2)
        db.session.commit()

        self.assertFalse(self.user1.is_following(self.user2))
        self.assertEqual(self.user1.following_count(), 0)
        self.assertEqual(self.user2.followers_count(), 0)

    def test_post_creation(self):
        post = Post(body='This is a test post content', author=self.user1)
        db.session.add(post)
        db.session.commit()

        self.assertIsNotNone(post.id)
        self.assertEqual(post.body, 'This is a test post content')
        self.assertEqual(post.author.username, self.user1.username)

    def test_comment_creation(self):
        post = Post(body='Parent post for comment', author=self.user1)
        db.session.add(post)
        db.session.commit()

        comment = Comment(body='This is a comment', author=self.user2, post_id=post.id)
        db.session.add(comment)
        db.session.commit()

        self.assertIsNotNone(comment.id)
        self.assertEqual(comment.body, 'This is a comment')
        self.assertEqual(comment.post_id, post.id)
        self.assertEqual(comment.user_id, self.user2.id)

    def test_like_functionality(self):
        post = Post(body='Post to like', author=self.user2)
        db.session.add(post)
        db.session.commit()

        like = Like(user_id=self.user1.id, post_id=post.id)
        db.session.add(like)
        db.session.commit()

        self.assertEqual(post.like_count(), 1)

    def test_message_sending(self):
        message = Message(sender_id=self.user1.id, recipient_id=self.user2.id, body='Hello from user1')
        db.session.add(message)
        db.session.commit()

        self.assertIsNotNone(message.id)
        self.assertEqual(message.body, 'Hello from user1')
        self.assertEqual(message.sender_id, self.user1.id)
        self.assertEqual(message.recipient_id, self.user2.id)

    def test_friend_request_sending(self):
        request = FriendRequest(from_user_id=self.user1.id, to_user_id=self.user2.id, status='pending')
        db.session.add(request)
        db.session.commit()

        self.assertIsNotNone(request.id)
        self.assertEqual(request.status, 'pending')
        self.assertEqual(request.from_user_id, self.user1.id)
        self.assertEqual(request.to_user_id, self.user2.id)

    def test_chat_message_creation(self):
        chat = ChatMessage(sender_id=self.user1.id, recipient_id=self.user2.id, message='Test chat message')
        db.session.add(chat)
        db.session.commit()

        self.assertIsNotNone(chat.id)
        self.assertEqual(chat.message, 'Test chat message')
        self.assertEqual(chat.sender_id, self.user1.id)
        self.assertEqual(chat.recipient_id, self.user2.id)

    def test_notification_creation(self):
        notification = Notification(
            user_id=self.user2.id,
            name='like',
            payload_json='{"post_id": 1, "from_user": "testuser1"}'
        )
        db.session.add(notification)
        db.session.commit()

        self.assertIsNotNone(notification.id)
        self.assertEqual(notification.user_id, self.user2.id)
        self.assertEqual(notification.name, 'like')


class IntegrationTests(BaseTestCase):

    def test_homepage_load(self):
        self.login_user()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_explore_page_load(self):
        self.login_user()
        response = self.client.get('/explore')
        self.assertEqual(response.status_code, 200)

    def test_discover_page_load(self):
        self.login_user()
        response = self.client.get('/discover')
        self.assertEqual(response.status_code, 200)

    def test_trending_page_load(self):
        self.login_user()
        response = self.client.get('/trending')
        self.assertEqual(response.status_code, 200)

    def test_for_you_page_load(self):
        self.login_user()
        response = self.client.get('/for-you')
        self.assertEqual(response.status_code, 200)

    def test_profile_page_load(self):
        self.login_user()
        response = self.client.get(f'/user/{self.user1.username}')
        self.assertEqual(response.status_code, 200)

    def test_edit_profile_page_load(self):
        self.login_user()
        response = self.client.get('/edit_profile')
        self.assertEqual(response.status_code, 200)

    def test_friends_page_load(self):
        self.login_user()
        response = self.client.get('/friends')
        self.assertEqual(response.status_code, 200)

    def test_conversations_page_load(self):
        self.login_user()
        response = self.client.get('/conversations')
        self.assertEqual(response.status_code, 200)

    def test_saved_posts_page_load(self):
        self.login_user()
        response = self.client.get('/saved')
        self.assertEqual(response.status_code, 200)


class SystemAndAcceptanceTests(BaseTestCase):

    def test_homepage_load_authenticated(self):
        self.login_user()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_login_page_load(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)

    def test_register_page_load(self):
        response = self.client.get('/auth/register')
        self.assertEqual(response.status_code, 200)

    def test_404_error_page(self):
        response = self.client.get('/nonexistent-page-xyz-123')
        self.assertEqual(response.status_code, 404)

    def test_admin_panel_access_denied_for_normal_user(self):
        self.login_user()
        response = self.client.get('/admin/moderation')
        self.assertEqual(response.status_code, 403)


class SecurityTests(BaseTestCase):

    def test_password_hashing_security(self):
        user = User(username='secureuser', email='secure@example.com')
        user.set_password('MySecretPass123!')
        db.session.add(user)
        db.session.commit()

        self.assertIsNotNone(user.password_hash)
        self.assertNotEqual(user.password_hash, 'MySecretPass123!')
        self.assertTrue(user.check_password('MySecretPass123!'))
        self.assertFalse(user.check_password('WrongPassword'))

    def test_sql_injection_prevention(self):
        malicious_input = "admin' OR '1'='1"

        user = User.query.filter_by(username=malicious_input).first()
        self.assertIsNone(user)

    def test_duplicate_email_prevention(self):
        with self.assertRaises(Exception):
            duplicate_user = User(username='duplicate2', email='test1@example.com')
            duplicate_user.set_password('pass')
            db.session.add(duplicate_user)
            db.session.commit()

    def test_duplicate_username_prevention(self):
        with self.assertRaises(Exception):
            duplicate_user = User(username='testuser1', email='unique@example.com')
            duplicate_user.set_password('pass')
            db.session.add(duplicate_user)
            db.session.commit()


class PerformanceTests(BaseTestCase):

    def test_database_query_performance(self):
        start_time = time.time()

        users = User.query.all()
        query_time = time.time() - start_time

        self.assertLess(query_time, 1.0)
        self.assertEqual(len(users), 3)

    def test_post_creation_performance(self):
        start_time = time.time()

        for i in range(50):
            post = Post(body=f'Performance test post {i}', author=self.user1)
            db.session.add(post)
        db.session.commit()

        creation_time = time.time() - start_time
        self.assertLess(creation_time, 2.0)
        self.assertEqual(self.user1.posts_count(), 50)

    def test_profile_page_load_performance(self):
        self.login_user()

        start_time = time.time()
        response = self.client.get(f'/user/{self.user1.username}')
        load_time = time.time() - start_time

        self.assertLess(load_time, 2.0)
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("ZETRAVOX TEST EXECUTION")
    print("=" * 60 + "\n")

    loader = unittest.TestLoader()
    test_suites = [
        ('Unit Tests', loader.loadTestsFromTestCase(UnitTests)),
        ('Integration Tests', loader.loadTestsFromTestCase(IntegrationTests)),
        ('System & Acceptance Tests', loader.loadTestsFromTestCase(SystemAndAcceptanceTests)),
        ('Security Tests', loader.loadTestsFromTestCase(SecurityTests)),
        ('Performance Tests', loader.loadTestsFromTestCase(PerformanceTests))
    ]

    total_tests = 0
    total_passed = 0
    total_failed = 0

    for suite_name, suite in test_suites:
        print(f"\n{'=' * 50}")
        print(f"Running {suite_name}...")
        print(f"{'=' * 50}")

        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        total_tests += result.testsRun
        total_passed += result.testsRun - len(result.failures) - len(result.errors)
        total_failed += len(result.failures) + len(result.errors)

    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Success Rate: {(total_passed / total_tests * 100):.2f}%" if total_tests > 0 else "0%")
    print("=" * 60)

    TestResultCollector.save_to_csv()