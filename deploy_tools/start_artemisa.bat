\
        @echo off
        set DJANGO_SETTINGS_MODULE=artemis_project.settings
        call venv\Scripts\activate
        waitress-serve --listen=0.0.0.0:8000 artemis_project.wsgi:application
