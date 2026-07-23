from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

REPORT_CATEGORIES = [
    ("사기 의심", "사기 의심"),
    ("금지 물품", "금지 물품"),
    ("부적절한 메시지", "부적절한 메시지"),
    ("부정확한 정보", "부정확한 정보"),
    ("기타", "기타"),
]


class ReportForm(FlaskForm):
    target_type = HiddenField("대상 유형", validators=[DataRequired()])
    target_id = HiddenField("대상 ID", validators=[DataRequired()])
    reason_category = SelectField("신고 사유", choices=REPORT_CATEGORIES, validators=[DataRequired()])
    reason_detail = TextAreaField("상세 사유", validators=[DataRequired(), Length(min=5, max=1000)])
    submit = SubmitField("신고하기")

