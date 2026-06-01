import csv
import os
from datetime import datetime, timezone
from flask import current_app
from app import db
from app.models import User, Post, Comment, Like, SpamReport, UserActivity


class ReportService:

    REPORTS_DIR = 'reports'

    @classmethod
    def ensure_reports_dir(cls):
        reports_path = os.path.join(current_app.root_path, '..', cls.REPORTS_DIR)
        os.makedirs(reports_path, exist_ok=True)
        return reports_path

    @classmethod
    def generate_users_report(cls):
        reports_path = cls.ensure_reports_dir()
        filename = f"users_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(reports_path, filename)

        users = User.query.all()

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                ['User ID', 'Username', 'Email', 'Admin', 'Verified', 'Posts Count', 'Followers', 'Following', 'Points',
                 'Joined Date', 'Last Seen'])

            for user in users:
                writer.writerow([
                    user.id,
                    user.username,
                    user.email,
                    'Yes' if user.is_admin else 'No',
                    'Yes' if user.is_verified else 'No',
                    user.posts_count(),
                    user.followers_count(),
                    user.following_count(),
                    user.points,
                    user.last_seen.strftime('%Y-%m-%d %H:%M:%S') if user.last_seen else '',
                    user.last_seen.strftime('%Y-%m-%d %H:%M:%S') if user.last_seen else ''
                ])

        return filepath, filename

    @classmethod
    def generate_posts_report(cls):
        reports_path = cls.ensure_reports_dir()
        filename = f"posts_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(reports_path, filename)

        posts = Post.query.order_by(Post.timestamp.desc()).all()

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                ['Post ID', 'Author', 'Content', 'Likes', 'Comments', 'Shares', 'Is Spam', 'Privacy', 'Created At'])

            for post in posts:
                writer.writerow([
                    post.id,
                    post.author.username,
                    post.body[:100] + '...' if len(post.body) > 100 else post.body,
                    post.like_count(),
                    post.comment_count(),
                    post.share_count,
                    'Yes' if post.is_spam else 'No',
                    post.privacy,
                    post.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                ])

        return filepath, filename

    @classmethod
    def generate_reports_summary(cls):
        reports_path = cls.ensure_reports_dir()
        filename = f"reports_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(reports_path, filename)

        reports = SpamReport.query.order_by(SpamReport.timestamp.desc()).all()

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Report ID', 'Post ID', 'Post Content', 'Post Author', 'Reported By', 'Reason', 'Reviewed',
                             'Reported At'])

            for report in reports:
                writer.writerow([
                    report.id,
                    report.post_id,
                    report.post.body[:100] + '...' if report.post and len(report.post.body) > 100 else (
                        report.post.body if report.post else 'Deleted'),
                    report.post.author.username if report.post else 'Deleted User',
                    report.reporter.username,
                    report.reason,
                    'Yes' if report.reviewed else 'No',
                    datetime.fromtimestamp(report.timestamp).strftime('%Y-%m-%d %H:%M:%S') if report.timestamp else ''
                ])

        return filepath, filename

    @classmethod
    def generate_engagement_report(cls):
        reports_path = cls.ensure_reports_dir()
        filename = f"engagement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(reports_path, filename)

        users = User.query.all()

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                ['Username', 'Posts', 'Likes Given', 'Likes Received', 'Comments Given', 'Comments Received',
                 'Total Engagement'])

            for user in users:
                likes_given = Like.query.filter_by(user_id=user.id).count()
                likes_received = Like.query.join(Post).filter(Post.user_id == user.id).count()
                comments_given = Comment.query.filter_by(user_id=user.id).count()
                comments_received = Comment.query.join(Post).filter(Post.user_id == user.id).count()

                writer.writerow([
                    user.username,
                    user.posts_count(),
                    likes_given,
                    likes_received,
                    comments_given,
                    comments_received,
                    likes_given + likes_received + comments_given + comments_received
                ])

        return filepath, filename

    @classmethod
    def get_all_reports(cls):
        reports_path = cls.ensure_reports_dir()
        reports = []

        if os.path.exists(reports_path):
            for filename in os.listdir(reports_path):
                if filename.endswith('.csv'):
                    filepath = os.path.join(reports_path, filename)
                    reports.append({
                        'name': filename,
                        'path': filepath,
                        'size': os.path.getsize(filepath),
                        'created': datetime.fromtimestamp(os.path.getctime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                    })

        return sorted(reports, key=lambda x: x['created'], reverse=True)


report_service = ReportService()