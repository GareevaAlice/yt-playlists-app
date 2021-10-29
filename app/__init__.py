from flask import Flask

app = Flask(__name__)  # создаем приложение на Flask
app.config.from_object('config')  # загрузка настроек из config.py

from . import views
