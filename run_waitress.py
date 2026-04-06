from waitress import serve
from artemis_project.wsgi import application
import os

if __name__ == '__main__':
    port = os.environ.get('PORT', '8090')
    print(f"Serving Artemis on http://127.0.0.1:{port} using Waitress...")
    serve(application, host='127.0.0.1', port=int(port), threads=8)
