from flask import request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, TextAreaField, SelectField, DateTimeField
from wtforms.validators import ValidationError, DataRequired, Length, Optional
import sqlalchemy as sa
from flask_babel import _, lazy_gettext as _l
from app import db
from app.models import User
from wtforms.fields import DateTimeField


class EditProfileForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=140)])
    profile_pic = FileField(_l('Profile Picture'), validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], _('Images only!'))
    ])
    is_private = SelectField(_l('Account Privacy'), choices=[
        ('False', 'Public'), ('True', 'Private')
    ], coerce=lambda x: x == 'True')
    submit = SubmitField(_l('Submit'))

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
    media = FileField(_l('Add Photo/Video'), validators=[
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