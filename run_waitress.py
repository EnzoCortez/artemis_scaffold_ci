
import os
import sys

# Add the project directory to the sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from waitress import serve
from artemis_project.wsgi import application

if __name__ == '__main__':
    print("Serving on http://localhost:8080")
    serve(application, host='0.0.0.0', port=8080)
