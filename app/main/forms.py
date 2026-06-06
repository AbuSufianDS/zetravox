from flask import request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, TextAreaField, SelectField, DateTimeField, BooleanField
from wtforms.validators import ValidationError, DataRequired, Length, Optional
import sqlalchemy as sa
from flask_babel import _, lazy_gettext as _l
from app import db
from app.models import User
from wtforms.fields import DateTimeField
from flask_wtf.file import MultipleFileField


class EditProfileForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=140)])
    profile_pic = FileField(_l('Profile Picture'), validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], _('Images only!'))
    ])
    cover_pic = FileField(_l('Cover Photo'), validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], _('Images only!'))
    ])
    is_private = SelectField(_l('Account Privacy'), choices=[
        ('False', 'Public'), ('True', 'Private')
    ], coerce=lambda x: x == 'True')

    relationship_status = SelectField(_l('Relationship Status'), choices=[
        ('', 'Select'),
        ('single', 'Single'),
        ('in_relationship', 'In a Relationship'),
        ('engaged', 'Engaged'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('complicated', "It's Complicated")
    ], validators=[Optional()])

    work = StringField(_l('Work'), validators=[Length(max=100), Optional()])
    education = StringField(_l('Education'), validators=[Length(max=100), Optional()])
    location = StringField(_l('Location'), validators=[Length(max=100), Optional()])
    website = StringField(_l('Website'), validators=[Length(max=200), Optional()])
    birthday = StringField(_l('Birthday'), validators=[Length(max=20), Optional()],
                           render_kw={"placeholder": "YYYY-MM-DD"})

    gender = SelectField(_l('Gender'), choices=[
        ('', 'Select'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[Optional()])

    interested_in = SelectField(_l('Interested In'), choices=[
        ('', 'Select'),
        ('men', 'Men'),
        ('women', 'Women'),
        ('everyone', 'Everyone')
    ], validators=[Optional()])

    phone = StringField(_l('Phone'), validators=[Length(max=20), Optional()])
    submit = SubmitField(_l('Save Changes'))

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(sa.select(User).where(User.username == username.data))
            if user is not None:
                raise ValidationError(_('Please use a different username.'))


class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')


class PostForm(FlaskForm):
    post = TextAreaField(_l('What\'s on your mind?'), validators=[
        DataRequired(), Length(min=1, max=280)])
    media_files = MultipleFileField(_l('Add Photos/Videos'), validators=[
        FileAllowed(['png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'], _('Images and videos only!'))
    ])
    privacy = SelectField(_l('Privacy'), choices=[
        ('public', '🌍 Public'),
        ('followers', '👥 Followers Only'),
        ('only_me', '🔒 Only Me')
    ], default='public')
    schedule_date = DateTimeField(_l('Schedule for later'), validators=[Optional()], format='%Y-%m-%d %H:%M')
    submit = SubmitField(_l('Post'))


class CommentForm(FlaskForm):
    body = TextAreaField(_l('Write a comment...'), validators=[DataRequired(), Length(min=1, max=500)])
    submit = SubmitField(_l('Post'))


class SearchForm(FlaskForm):
    q = StringField(_l('Search'), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'meta' not in kwargs:
            kwargs['meta'] = {'csrf': False}
        super(SearchForm, self).__init__(*args, **kwargs)


class MessageForm(FlaskForm):
    message = TextAreaField(_l('Message'), validators=[
        DataRequired(), Length(min=1, max=1000)])
    submit = SubmitField(_l('Send'))


class ReportForm(FlaskForm):
    reason = SelectField(_l('Reason'), choices=[
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('hate_speech', 'Hate Speech'),
        ('violence', 'Violence'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    details = TextAreaField(_l('Additional details'), validators=[Optional(), Length(max=500)])
    submit = SubmitField(_l('Submit Report'))


class StoryForm(FlaskForm):
    media = FileField(_l('Add to Story'), validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'mp4'], _('Images and videos only!'))
    ])
    caption = TextAreaField(_l('Caption'), validators=[Optional(), Length(max=200)])
    submit = SubmitField(_l('Share to Story'))


class NotificationSettingsForm(FlaskForm):
    notify_on_like = BooleanField(_l('Likes on my posts'), default=True)
    notify_on_comment = BooleanField(_l('Comments on my posts'), default=True)
    notify_on_follow = BooleanField(_l('New followers'), default=True)
    notify_on_share = BooleanField(_l('Shares of my posts'), default=True)
    notify_on_friend_request = BooleanField(_l('Friend requests'), default=True)
    notify_on_message = BooleanField(_l('New messages'), default=True)

    email_on_like = BooleanField(_l('Email me when someone likes my post'), default=False)
    email_on_comment = BooleanField(_l('Email me when someone comments'), default=False)
    email_on_follow = BooleanField(_l('Email me when someone follows me'), default=False)
    email_on_message = BooleanField(_l('Email me when I receive a message'), default=False)

    submit = SubmitField(_l('Save Notification Settings'))


class NotificationSettingsForm(FlaskForm):
    notify_push_likes = BooleanField(_l('Likes on my posts'), default=True)
    notify_push_comments = BooleanField(_l('Comments on my posts'), default=True)
    notify_push_follows = BooleanField(_l('New followers'), default=True)
    notify_push_shares = BooleanField(_l('Shares of my posts'), default=True)
    notify_push_friend_requests = BooleanField(_l('Friend requests'), default=True)
    notify_push_messages = BooleanField(_l('New messages'), default=True)

    notify_email_likes = BooleanField(_l('Email when someone likes my post'), default=False)
    notify_email_comments = BooleanField(_l('Email when someone comments'), default=False)
    notify_email_follows = BooleanField(_l('Email when someone follows me'), default=False)
    notify_email_shares = BooleanField(_l('Email when someone shares my post'), default=False)
    notify_email_friend_requests = BooleanField(_l('Email when I get a friend request'), default=False)
    notify_email_messages = BooleanField(_l('Email when I receive a message'), default=False)

    submit = SubmitField(_l('Save Notification Settings'))