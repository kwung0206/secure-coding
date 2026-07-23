from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError

from app.security import validate_password_strength


class ProfileForm(FlaskForm):
    bio = TextAreaField("소개글", validators=[Length(max=500)])
    region = StringField("지역", validators=[Length(max=80)])
    profile_image = FileField("프로필 이미지")
    submit = SubmitField("저장")


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField("현재 비밀번호", validators=[DataRequired(), Length(max=128)])
    new_password = PasswordField("새 비밀번호", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("비밀번호 변경")

    def validate_new_password(self, field):
        errors = validate_password_strength(field.data)
        if errors:
            raise ValidationError(" ".join(errors))
