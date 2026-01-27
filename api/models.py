from datetime import date
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('trainer', 'Тренер'),
        ('manager', 'Руководитель'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    trainer = models.OneToOneField('Trainer', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        if self.pk is None or not self.password.statswith('pbkdf2_'):
            self.set_password(self.password)
            super().save(*args, **kwargs)

class Trainer(models.Model):
    name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    secondname = models.CharField(max_length=50, blank=True)
    specialization = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.surname} {self.name}"

class Client(models.Model):
    name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    secondname = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(null=True, blank=True)
    birth_date = models.DateField()
    registration_date = models.DateField(auto_now_add=True)

class MembershipType(models.Model):
    name = models.CharField(max_length=50)
    duration_days = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(null=True, blank=True)

    def clean(self):
        if self.price < 0:
            raise ValidationError('Цена не может быть отрицательной')

class Membership(models.Model):
    STATUS_CHOICES = [('Активен', 'Активен'), ('Приостановлен', 'Приостановлен'), ('Истёк', 'Истёк')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    type = models.ForeignKey(MembershipType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    def save(self, *args, **kwargs):
        if self.end_date < date.today():
            self.status = 'Истёк'
        super().save(*args, **kwargs)

class Hall(models.Model):
    name = models.CharField(max_length=50, unique=True)
    capacity = models.IntegerField()
    equipment = models.TextField(null=True, blank=True)

class Training(models.Model):
    STATUS_CHOICES = [('Запланирована', 'Запланирована'), ('Отменена', 'Отменена'), ('Завершена', 'Завершена')]
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE)
    training_type = models.ForeignKey(MembershipType, on_delete=models.CASCADE)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    date_time = models.DateTimeField()
    max_clients = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

class Attendance(models.Model):
    STATUS_CHOICES = [('Записан', 'Записан'), ('Посетил', 'Посетил'), ('Отмена', 'Отмена'), ('Неявка', 'Неявка')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    training = models.ForeignKey(Training, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    is_present = models.BooleanField(default=False) # Добавлено для отчетов
    check_in_time = models.DateTimeField(null=True, blank=True)

class Payment(models.Model):
    TYPE_CHOICES = [('Наличные', 'Наличные'), ('Карта', 'Карта'), ('Перевод', 'Перевод')]
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    membership = models.ForeignKey(Membership, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.CharField(max_length=200, null=True, blank=True)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError('Сумма платежа должна быть больше нуля') # TC-PAY-02