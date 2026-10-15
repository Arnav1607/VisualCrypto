import sys
import os

# Ensure the repository root and web_app directory are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

WEB_APP_DIR = os.path.join(ROOT_DIR, 'web_app')
if WEB_APP_DIR not in sys.path:
    sys.path.insert(0, WEB_APP_DIR)

# Import the Flask application instance
from web_app.app import app

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    if not debug:
        try:
            from waitress import serve
            print(f"Serving VisualCrypto on http://{host}:{port} with Waitress WSGI...")
            serve(app, host=host, port=port, threads=4)
        except ImportError:
            app.run(host=host, port=port, debug=debug)
    else:
        app.run(host=host, port=port, debug=debug)
