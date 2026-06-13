# ZETRAVOX

**A Social Media Platform with Transformer-Based Spam Detection**

Developed as a final year project at Guizhou University, Department of Computer Science and Technology.

---

## Overview

ZETRAVOX is a full-stack social media platform built with Flask. It integrates a transformer-based spam detection system, real-time messaging, multimedia content sharing, and a complete administrative dashboard. The platform is designed with production-grade security practices and is deployable on Render.com with PostgreSQL.

---

## Features

### User Management

- Registration and login with email verification
- Two-factor authentication (2FA) via TOTP
- Password recovery using OTP over email
- Session management and login history tracking
- Account lockout after repeated failed login attempts

### Content Creation and Sharing

- Post creation with up to 280 characters of text
- Multimedia uploads: images and videos, up to 10 files per post
- Privacy controls: public, followers only, or private
- Six post reactions: applaud, love, haha, wow, sad, angry
- Nested comment system with per-comment reactions
- Share and repost functionality
- Bookmark and pin posts to profile

### Feed System

- Home feed (chronological stream)
- For You feed (AI-personalized recommendations)
- Discover feed (content from unfollowed users)
- Trending feed (ranked by engagement)
- Following feed (posts from followed accounts only)
- Explore page for content discovery

### Stories

- Upload images and videos as 24-hour stories
- Text stories with customizable background colors
- Story reactions and comments
- Story viewer with sequential navigation

### Messaging

- Real-time one-on-one chat
- Emoji picker with 24+ emojis
- Image sharing with inline preview
- Reply to specific messages
- Message reactions: love, like, haha, wow
- Read receipts: sent, delivered, seen
- Typing indicator and online/offline status
- Unread message count and conversation list

### Notifications

- Real-time notifications for likes, comments, follows, shares, and messages
- Notification bell with dropdown
- Mark-as-read and notification history
- Configurable email notifications

### Security

- CSRF protection on all forms
- XSS prevention using bleach sanitization
- SQL injection prevention via SQLAlchemy ORM
- Rate limiting on API endpoints
- Active session management
- Login history and security event logging
- GDPR compliance: data export and account deletion requests
- Theme persistence: dark, light, system

### Administrative Dashboard

- Moderation queue for flagged and spam content
- Approve and reject content moderation actions
- Analytics dashboard with real-time charts
- CSV export for users, posts, reports, and engagement
- Spam review interface with confidence scores

### Machine Learning

- Transformer-based spam detection (BERT architecture)
- Confidence scoring on flagged posts
- Automatic routing of high-confidence spam to moderation queue

---

## Technology Stack

### Backend

| Component | Technology |
|-----------|------------|
| Framework | Flask 3.1 |
| Database | SQLite (development), PostgreSQL (production) |
| ORM | SQLAlchemy |
| Authentication | Flask-Login |
| Forms | Flask-WTF with CSRF protection |
| Task Queue | Redis + RQ |
| Internationalization | Flask-Babel |

### Frontend

| Component | Technology |
|-----------|------------|
| CSS Framework | Bootstrap 5 |
| Icons | Font Awesome 6 |
| Typography | Google Inter |
| Charts | Chart.js |
| Date Handling | Moment.js |
| Theme System | CSS custom properties |

### Machine Learning and AI

| Component | Technology |
|-----------|------------|
| Spam Detection | BERT-based transformer model |
| AI Chat Assistant | OpenAI or Gemini API (configurable) |

### Infrastructure

| Component | Technology |
|-----------|------------|
| Email | Brevo SMTP API |
| Deployment | Render.com |
| Environment | python-dotenv |
| Version Control | Git |

---

## Database Schema

The system uses 25+ relational tables:

- `User` — profile, authentication, preferences
- `Post` — content, privacy, scheduling
- `Comment` — nested replies via `parent_id`
- `PostMedia` — image and video attachments
- `PostReaction`, `CommentReaction` — per-content reactions
- `ChatMessage` — private messaging
- `Story`, `StoryView`, `StoryReaction`, `StoryComment` — moments system
- `FriendRequest` — connection and follow system
- `Notification` — push and email notification records
- `BlockedUser` — user blocking
- `SavedPost` — bookmarked content
- `Hashtag` — content categorization
- `LoginHistory`, `SecurityEvent`, `UserSession` — security tracking
- `DataDeletionRequest` — GDPR compliance
- `PasswordResetOTP` — secure password recovery

---

## Installation

### Prerequisites

- Python 3.11 or higher
- Redis server
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/mdabusufian/zetravox.git
cd zetravox

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your values

# Initialize the database
flask db upgrade

# Start the development server
flask run
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | User login |
| POST | `/auth/register` | User registration |
| POST | `/auth/logout` | User logout |
| POST | `/auth/forgot-password` | Request password reset |
| POST | `/auth/reset-password` | Confirm password reset |

### Posts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home feed |
| POST | `/` | Create a post |
| GET | `/post/<id>` | View a single post |
| GET | `/delete_post/<id>` | Delete a post |
| GET | `/react_post/<id>/<reaction>` | React to a post |

### Comments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/add_comment/<post_id>` | Add a comment |
| POST | `/comment/<id>/react` | React to a comment |
| POST | `/comment/<id>/reply` | Reply to a comment |
| DELETE | `/comment/<id>/delete` | Delete a comment |

### Messaging

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/send_chat_message` | Send a message |
| GET | `/get_chat_messages/<user_id>` | Retrieve messages |
| POST | `/react-to-message/<id>` | React to a message |
| DELETE | `/delete-message/<id>` | Delete a message |

### User Profile

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/user/<username>` | View user profile |
| POST | `/edit_profile` | Update profile |
| POST | `/follow/<username>` | Follow a user |
| POST | `/unfollow/<username>` | Unfollow a user |

### Stories

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/add_story` | Create a story |
| GET | `/view_story/<id>` | View a story |
| POST | `/react_story/<id>/<reaction>` | React to a story |

### Analytics (Admin Only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/stats` | Platform statistics |
| GET | `/api/analytics/user-growth` | User growth data |
| GET | `/api/analytics/top-users` | Most active users |
| GET | `/api/analytics/activity` | Daily activity metrics |
| GET | `/api/analytics/engagement` | Engagement distribution |

---

## Testing

The project includes manual testing coverage across all major workflows:

- User registration and login flows, including 2FA and OTP recovery
- Post creation with media uploads and privacy settings
- Comment threading and nested reactions
- Real-time messaging and read receipts
- Story creation, viewing, and expiration
- Admin moderation queue and content review
- Password recovery end-to-end

---

## Deployment

The project is configured for deployment on Render.com. The included `render.yaml` covers web service configuration with Gunicorn, PostgreSQL provisioning, and environment variable management.

For manual production deployment:

```bash
# Run database migrations
flask db upgrade

# Start the production server
gunicorn run:app
```

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

Under this license:

- You may copy, distribute, and modify the software
- Source code must be disclosed when you distribute or run the software over a network
- Modifications must be released under the same license
- No warranty is provided

### Dual Licensing

- Core application code (backend, ML models, database schemas): AGPL-3.0
- Reusable components and third-party integrations: MIT License

For complete license terms, see the `LICENSE` file in the project root.

---

## Copyright

Copyright (c) 2026 MD. ABU SUFIAN

All rights reserved under the terms of the GNU Affero General Public License v3.0.

---

## Author

**MD. ABU SUFIAN**
Ungraduate Student and Research Assistant,
Bachelor of Computer Science,
Guizhou University, Guiyang, Guizhou Province, China

- Email: mdabusufian1323@example.com
- GitHub: [github.com/AbuSufianDS](https://github.com/AbuSufianDS)
- LinkedIn: [https://www.linkedin.com/in/md-abu-sufian-ds1323](https://linkedin.com/in/md-abu-sufian-ds1323)

**Supervisor:**  Professor Xu Ji (徐计) 
**Department:** Computer Science and Technology, Guizhou University
**Project Completion:** 10 June 2026

---

## Citation

If you use this project in academic research, teaching, or publication, please cite as follows.

**BibTeX**

```bibtex
@software{sufian2026zetravox,
  author    = {Sufian, MD. ABU},
  title     = {ZETRAVOX: A Social Media Platform with Transformer-Based Spam Detection},
  year      = {2026},
  month     = {June},
  institution = {Guizhou University},
  url       = {https://github.com/mdabusufian/zetravox},
  version   = {1.0.0},
  license   = {AGPL-3.0}
}
```

**APA**

Sufian, M. A. (2026). *ZETRAVOX: A Social Media Platform with Transformer-Based Spam Detection* (Version 1.0.0) [Computer software]. Guizhou University. https://github.com/mdabusufian/zetravox

**MLA**

Sufian, MD. ABU. *ZETRAVOX: A Social Media Platform with Transformer-Based Spam Detection*. Version 1.0.0, Guizhou University, 10 June 2026, github.com/mdabusufian/zetravox.

---

## Acknowledgments

- Flask and SQLAlchemy documentation for framework guidance
- Bootstrap team for the responsive grid system
- Chart.js contributors for analytics visualization
- The open source community for the libraries used throughout this project
- Guizhou University faculty for project supervision
- Family and friends for continuous support

---

## Project Status

| Field | Detail |
|-------|--------|
| Version | 1.0.0 |
| Release Date | 10 June 2026 |
| Status | Production Ready |
| Maintenance | Active |
| Supported Platforms | Windows, Linux, macOS |

---

## Disclaimer

This software is provided "AS IS" without warranty of any kind, either expressed or implied. The author assumes no responsibility for any damage or loss resulting from the use of this software. The full terms of the AGPL-3.0 license apply. See the `LICENSE` file included in the distribution for complete details.
