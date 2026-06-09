# ZETRAVOX - Social Media Platform

## Project Overview

ZETRAVOX is a comprehensive social media platform developed as a final year project at Guizhou University. The platform integrates machine learning-based spam detection, real-time communication features, and modern security protocols to provide a complete social networking experience.

The system includes user authentication with two-factor authentication, real-time messaging, content sharing with multimedia support, stories/moments feature, AI-powered chat assistant, and an administrative dashboard with analytics and reporting capabilities.

## Key Features

### User Management
- User registration and authentication with email verification
- Two-factor authentication (2FA) using TOTP
- Password recovery with OTP via email
- Session management and login history tracking
- Account lockout protection after failed attempts

### Content Creation and Sharing
- Post creation with text (up to 280 characters)
- Multimedia upload support (images and videos, up to 10 files per post)
- Privacy settings (public, followers only, only me)
- Post reactions (applaud, love, haha, wow, sad, angry)
- Comment system with nested replies and reaction support
- Share/repost functionality
- Bookmark/save posts
- Pin posts to profile

### Feed System
- Home feed (stream)
- For You feed (AI personalized recommendations)
- Discover feed (posts from unfollowed users)
- Trending feed (engagement-based ranking)
- Following feed (posts from followed users only)
- Explore page with content discovery

### Stories and Moments
- Image and video upload as stories
- 24-hour automatic expiration
- Text stories with customizable backgrounds
- Story reactions and comments
- Story viewer with navigation between stories

### Chat and Messaging
- Real-time one-on-one messaging
- Emoji picker with 24+ emojis
- Image sharing with preview
- Reply to specific messages
- Message reactions (love, like, haha, wow)
- Read receipts (sent, delivered, seen)
- Typing indicator
- Online/offline status display
- Conversation list with last message preview
- Unread message count
- Conversation clearing functionality

### Notification System
- Real-time notifications for likes, comments, follows, shares, messages
- Notification bell with dropdown interface
- Mark as read functionality
- Notifications history page
- Email notifications (configurable)

### Security Features
- CSRF protection on all forms
- XSS prevention using bleach sanitization
- SQL injection prevention via SQLAlchemy ORM
- Rate limiting on API endpoints
- Account lockout after failed login attempts
- Login history tracking
- Active session management
- GDPR compliance features (data export, account deletion request)
- Theme preference persistence (dark, light, system)

### Administrative Dashboard
- Moderation queue for flagged posts
- Approve/reject content moderation
- Analytics dashboard with real-time charts
- CSV report generation (users, posts, reports, engagement)
- Spam content review interface

### Machine Learning Integration
- Transformer-based spam detection for posts
- Confidence scoring for flagged content
- Automatic routing of spam to moderation queue

## Technology Stack

### Backend
- Framework: Flask 3.1
- Database: SQLite (development) / PostgreSQL (production)
- ORM: SQLAlchemy
- Authentication: Flask-Login
- Form Handling: Flask-WTF with CSRF protection
- Task Queue: Redis + RQ
- Internationalization: Flask-Babel

### Frontend
- CSS Framework: Bootstrap 5
- Icons: Font Awesome 6
- Fonts: Google Inter font family
- JavaScript Libraries: Chart.js for analytics, Moment.js for dates
- Theme System: CSS custom properties with dark/light mode

### Machine Learning
- Spam Detection: Transformer-based model (BERT architecture)
- AI Assistant: Integration with OpenAI/Gemini API (configurable)

### Email Services
- SMTP integration with Brevo API for transactional emails
- OTP generation and delivery for password recovery

### Development and Deployment
- Version Control: Git
- Deployment: Render.com compatible
- Environment Configuration: python-dotenv

## Database Schema

The system implements 25+ database tables including:

- User (profile management, authentication, settings)
- Post (content, privacy, scheduling)
- Comment (with parent_id for nested replies)
- PostMedia (image/video attachments)
- PostReaction (reactions on posts)
- CommentReaction (reactions on comments)
- ChatMessage (private messaging)
- Story (moments with expiration)
- StoryView, StoryReaction, StoryComment
- FriendRequest (connection system)
- Notification (push and email notifications)
- BlockedUser (user blocking)
- SavedPost (bookmarks)
- Hashtag (content categorization)
- LoginHistory, SecurityEvent, UserSession
- DataDeletionRequest (GDPR compliance)
- PasswordResetOTP (secure password recovery)

## Installation Instructions

### Prerequisites

- Python 3.11 or higher
- Redis server (for task queue)
- Git

### Setup Steps

```bash
# Clone the repository
git clone https://github.com/AbuSufianDS/zetravox.git
cd zetravox

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
flask db upgrade

# Run the application
flask run