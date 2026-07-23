from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange


class ReasonForm(FlaskForm):
    reason = TextAreaField("사유", validators=[DataRequired(), Length(min=2, max=500)])
    submit = SubmitField("처리")


class UserStatusForm(ReasonForm):
    status = SelectField(
        "사용자 상태",
        choices=[
            ("ACTIVE", "복구"),
            ("RESTRICTED", "제한"),
            ("SUSPENDED", "정지"),
        ],
        validators=[DataRequired()],
    )


class ReportResolveForm(ReasonForm):
    status = SelectField(
        "신고 처리",
        choices=[
            ("RESOLVED", "승인"),
            ("REJECTED", "기각"),
        ],
        validators=[DataRequired()],
    )


class WalletGrantForm(ReasonForm):
    amount = IntegerField("지급 테스트 머니", validators=[DataRequired(), NumberRange(min=1)])
    idempotency_key = HiddenField("요청 키", validators=[DataRequired(), Length(max=80)])
