from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError

from app.security import validate_password_strength


class RegisterForm(FlaskForm):
    username = StringField(
        "사용자명",
        validators=[
            DataRequired(),
            Length(min=3, max=40),
            Regexp(r"^[0-9A-Za-z_가-힣]+$", message="사용자명은 문자, 숫자, 밑줄만 사용할 수 있습니다."),
        ],
    )
    password = PasswordField("비밀번호", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("회원가입")

    def validate_password(self, field):
        errors = validate_password_strength(field.data)
        if errors:
            raise ValidationError(" ".join(errors))


class LoginForm(FlaskForm):
    username = StringField("사용자명", validators=[DataRequired(), Length(max=40)])
    password = PasswordField("비밀번호", validators=[DataRequired(), Length(max=128)])
    submit = SubmitField("로그인")
