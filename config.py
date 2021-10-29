import random

rand = random.SystemRandom()


def get_random_key(length=50):
    characters = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return ''.join(rand.choice(characters) for _ in range(length))


# Секретный ключ для валидации формы.
SECRET_KEY = get_random_key()

# Где разворачиваем приложение.
host = 'localhost'
port = 5000
debug = True

# Путь к ютуб-ключу (!!!)
# YouTube Data API v3
# (https://developers.google.com/youtube/v3/getting-started)
yt_api_key_file_path = './files/youtube-api-key.txt'

# Путь к detectlanguage-ключу (!!!)
# Detect Language API (https://detectlanguage.com)
dl_key_file_path = './files/detectlanguage-api-key.txt'

# Путь к OAuth информации (!!!)
# (https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps)
client_secret = './files/client_secret.json'
