from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import *


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'trainer']

class MTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role.lower() if hasattr(user, 'role') else 'admin'
        return token

class TrainerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trainer
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'


class MembershipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipType
        fields = '__all__'


class MembershipSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.surname', read_only=True)
    type_name = serializers.CharField(source='type.name', read_only=True)

    class Meta:
        model = Membership
        fields = '__all__'


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = '__all__'


class TrainingSerializer(serializers.ModelSerializer):
    trainer_name = serializers.CharField(source='trainer.surname', read_only=True)
    hall_name = serializers.CharField(source='hall.name', read_only=True)
    type_name = serializers.CharField(source='training_type.name', read_only=True)

    class Meta:
        model = Training
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    client_details = ClientSerializer(source='client', read_only=True)

    class Meta:
        model = Attendance
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.surname', read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма платежа должна быть положительной (TC-PAY-02).")
        return value