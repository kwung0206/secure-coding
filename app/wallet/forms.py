from uuid import uuid4

from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

MAX_TEST_MONEY_AMOUNT = 1_000_000_000


class TransferForm(FlaskForm):
    receiver_username = StringField("받는 사용자명", validators=[DataRequired(), Length(max=40)])
    amount = IntegerField(
        "보낼 테스트 머니",
        validators=[DataRequired(), NumberRange(min=1, max=MAX_TEST_MONEY_AMOUNT)],
    )
    idempotency_key = HiddenField("요청 키", default=lambda: uuid4().hex, validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("송금")
