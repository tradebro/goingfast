from goingfast import create_app
from os import environ

APP_HOST = environ.get('APP_HOST', '0.0.0.0')
APP_PORT = environ.get('APP_PORT', '8080')
APP_DEBUG = True if environ.get('APP_DEBUG') == '1' else False


if __name__ == '__main__':
    app = create_app()
    app.run(host=APP_HOST,
            port=APP_PORT,
            debug=APP_DEBUG)
