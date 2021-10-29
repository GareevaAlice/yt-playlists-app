from app import app
from config import host, port, debug
import os

# запускаем приложение на http://host:port/ с отладкой или без
if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(host=host, port=port, debug=debug)
