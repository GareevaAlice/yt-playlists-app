from flask_wtf import FlaskForm
from wtforms import StringField, RadioField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length


# Форма для главной страницы.
class UrlOrIdForm(FlaskForm):
    url_or_id = StringField('Ссылка или id плейлиста',
                            validators=[DataRequired()],
                            description='Ссылка или id плейлиста')
    submit = SubmitField('Искать')


# Форма для страницы поиска.
class SearchForm(FlaskForm):
    code_words = StringField('Ключевые слова:',
                             validators=[
                                 Length(max=70,
                                        message='Ключевые слова'
                                                ' должны быть не длиннее'
                                                ' 70 символов')])
    search_by_description = BooleanField('Искать по описанию',
                                         default=False)
    bilingual_search = BooleanField('Искать по двум языкам (рус | анг)',
                                    default=False)
    author = StringField('Автор:',
                         validators=[
                             Length(max=40,
                                    message='Ник автора'
                                            ' должен быть не длиннее'
                                            ' 40 символов')])
    search_type = RadioField('Тип поиска:',
                             choices=[('verbatim_search',
                                       'Дословный поиск'),
                                      ('non_verbatim_search',
                                       'Поиск в любом порядке')],
                             default='verbatim_search')
    show_preview = BooleanField('Показывать превью',
                                default=False)
    submit = SubmitField('Искать')
