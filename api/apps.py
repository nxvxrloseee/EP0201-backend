from django.apps import AppConfig
from django.contrib.auth.hashers import make_password
from django.db import OperationalError, ProgrammingError


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        from .models import User, Trainer

        try:
            if User.objects.exists():
                return


            trainer = Trainer.objects.create(
                name="Иван",
                surname="Иванов",
                secondname="",
                specialization="Фитнес",
                phone="+79990000000"
            )

            User.objects.create(
                username="admin",
                password=make_password("admin123"),
                role="admin",
                is_active=True
            )

            User.objects.create(
                username="manager",
                password=make_password("manager123"),
                role="manager",
                is_staff=True
            )

            User.objects.create(
                username="trainer",
                password=make_password("trainer123"),
                role="trainer",
                trainer=trainer
            )

        except (OperationalError, ProgrammingError):
            pass

