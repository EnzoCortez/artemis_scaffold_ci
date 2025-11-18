from django.apps import AppConfig

class IocManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ioc_manager'

    def ready(self):
        import ioc_manager.signals