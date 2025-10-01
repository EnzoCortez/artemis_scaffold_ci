Proyecto Artemis - Scaffold inicial
----------------------------------
Instrucciones rápidas:
1. Crear virtualenv: python -m venv venv
2. Activar: venv\Scripts\activate (Windows) o source venv/bin/activate (Linux)
3. pip install -r requirements.txt
4. Configurar variables de entorno (.env): DB_HOST, DB_NAME, DB_USER, DB_PASS, DJANGO_SECRET_KEY, ALLOWED_HOST
5. python manage.py makemigrations && python manage.py migrate
6. python manage.py loaddata ioc_manager/fixtures/initial_data.json
7. python manage.py createsuperuser
8. start server: python manage.py runserver 0.0.0.0:8000 or use start_artemisa.bat with Waitress
