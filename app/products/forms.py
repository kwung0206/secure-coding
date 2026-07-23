from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange

CATEGORY_CHOICES = [
    ("디지털", "디지털"),
    ("생활", "생활"),
    ("가구", "가구"),
    ("의류", "의류"),
    ("도서", "도서"),
    ("기타", "기타"),
]

CONDITION_CHOICES = [
    ("새상품", "새상품"),
    ("좋음", "좋음"),
    ("사용감 있음", "사용감 있음"),
]

SELLER_STATUS_CHOICES = [
    ("SELLING", "판매 중"),
    ("RESERVED", "예약 중"),
    ("SOLD", "거래 완료"),
]


class ProductForm(FlaskForm):
    title = StringField("상품명", validators=[DataRequired(), Length(min=2, max=120)])
    description = TextAreaField("설명", validators=[DataRequired(), Length(min=5, max=2000)])
    price = IntegerField("가격", validators=[DataRequired(), NumberRange(min=0)])
    category = SelectField("카테고리", choices=CATEGORY_CHOICES, validators=[DataRequired()])
    condition = SelectField("상태", choices=CONDITION_CHOICES, validators=[DataRequired()])
    region = StringField("지역", validators=[DataRequired(), Length(max=80)])
    images = MultipleFileField("상품 이미지")
    submit = SubmitField("저장")


class ProductStatusForm(FlaskForm):
    status = SelectField("거래 상태", choices=SELLER_STATUS_CHOICES, validators=[DataRequired()])
    submit = SubmitField("상태 변경")

