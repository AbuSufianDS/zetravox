from datetime import datetime, timezone, timedelta
import unittest
from app import create_app, db
from app.models import User, Post
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'
    LOGIN_DISABLED = False


class TestUserModel(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        user = User(username='testuser', email='test@example.com')
        user.set_password('secret123')

        self.assertFalse(user.check_password('wrong'))
        self.assertTrue(user.check_password('secret123'))

    def test_avatar_generation(self):
        user = User(username='john', email='john@example.com')
        avatar_url = user.avatar(128)

        expected_hash = 'd4c74594d841139328695756648b6bd6'
        self.assertIn(expected_hash, avatar_url)
        self.assertIn('s=128', avatar_url)

    def test_follow_unfollow(self):
        user1 = User(username='alice', email='alice@example.com')
        user2 = User(username='bob', email='bob@example.com')
        db.session.add_all([user1, user2])
        db.session.commit()

        self.assertFalse(user1.is_following(user2))
        self.assertEqual(user1.following_count(), 0)
        self.assertEqual(user2.followers_count(), 0)

        user1.follow(user2)
        db.session.commit()
        self.assertTrue(user1.is_following(user2))
        self.assertEqual(user1.following_count(), 1)
        self.assertEqual(user2.followers_count(), 1)

        user1.unfollow(user2)
        db.session.commit()
        self.assertFalse(user1.is_following(user2))
        self.assertEqual(user1.following_count(), 0)
        self.assertEqual(user2.followers_count(), 0)

    def test_follow_posts_feed(self):
        users = []
        for i in range(1, 5):
            user = User(username=f'user{i}', email=f'user{i}@example.com')
            users.append(user)
        db.session.add_all(users)
        db.session.commit()

        now = datetime.now(timezone.utc)
        posts = [
            Post(body='John\'s post', author=users[0], timestamp=now + timedelta(seconds=1)),
            Post(body='Susan\'s post', author=users[1], timestamp=now + timedelta(seconds=4)),
            Post(body='Mary\'s post', author=users[2], timestamp=now + timedelta(seconds=3)),
            Post(body='David\'s post', author=users[3], timestamp=now + timedelta(seconds=2))
        ]
        db.session.add_all(posts)
        db.session.commit()

        users[0].follow(users[1])
        users[0].follow(users[3])
        users[1].follow(users[2])
        users[2].follow(users[3])
        db.session.commit()

        feed_user1 = db.session.scalars(users[0].following_posts()).all()
        feed_user2 = db.session.scalars(users[1].following_posts()).all()
        feed_user3 = db.session.scalars(users[2].following_posts()).all()

        self.assertEqual([p.body for p in feed_user1],
                         ['Susan\'s post', 'David\'s post', 'John\'s post'])
        self.assertEqual([p.body for p in feed_user2],
                         ['Susan\'s post', 'Mary\'s post'])
        self.assertEqual([p.body for p in feed_user3],
                         ['Mary\'s post', 'David\'s post'])

    def test_user_representation(self):
        user = User(username='testuser', email='test@example.com')
        self.assertEqual(str(user), '<User testuser>')


class TestPostModel(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(username='author', email='author@example.com')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        """Clean up database."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_post_creation(self):
        post = Post(body='Test post content', author=self.user)
        db.session.add(post)
        db.session.commit()

        self.assertEqual(post.body, 'Test post content')
        self.assertEqual(post.author, self.user)
        self.assertIsNotNone(post.timestamp)

    def test_post_timestamp_auto_generated(self):
        post = Post(body='Test post', author=self.user)
        db.session.add(post)
        db.session.commit()

        self.assertIsNotNone(post.timestamp)
        self.assertLessEqual(post.timestamp, datetime.now(timezone.utc))

    def test_multiple_posts_per_user(self):
        post1 = Post(body='First post', author=self.user)
        post2 = Post(body='Second post', author=self.user)
        db.session.add_all([post1, post2])
        db.session.commit()

        self.assertEqual(self.user.posts.count(), 2)

    def test_post_ordering(self):
        now = datetime.now(timezone.utc)
        post1 = Post(body='Older post', author=self.user, timestamp=now)
        post2 = Post(body='Newer post', author=self.user, timestamp=now + timedelta(seconds=10))
        db.session.add_all([post1, post2])
        db.session.commit()

        posts = self.user.posts.all()
        self.assertEqual(posts[0].body, 'Newer post')
        self.assertEqual(posts[1].body, 'Older post')

    def test_post_representation(self):
        post = Post(body='My post content', author=self.user)
        self.assertEqual(str(post), '<Post My post content>')


class TestRoutes(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.user = User(username='testuser', email='test@example.com')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_home_page_without_login(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)

    def test_login_page(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sign In', response.data)

    def test_valid_login(self):
        response = self.login('testuser', 'password')
        self.assertEqual(response.status_code, 200)

    def test_invalid_login(self):
        response = self.login('testuser', 'wrongpassword')
        self.assertIn(b'Invalid', response.data)

    def test_registration(self):
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword',
            'password2': 'newpassword'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user)

    def test_logout(self):
        self.login('testuser', 'password')
        response = self.logout()
        self.assertEqual(response.status_code, 200)


class TestAPI(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.user = User(username='apiuser', email='api@example.com')
        self.user.set_password('apipassword')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def get_api_token(self):
        response = self.client.post('/api/tokens', auth=('apiuser', 'apipassword'))
        return response.json['token']

    def test_get_token(self):
        response = self.client.post('/api/tokens', auth=('apiuser', 'apipassword'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.json)

    def test_protected_api_without_token(self):
        response = self.client.get('/api/posts')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main(verbosity=2)