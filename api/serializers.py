from rest_framework import serializers
from .models import Client, Trainer, Training, Membership, Payment, User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'email']

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

class TrainingSerializer(serializers.ModelSerializer):
    trainer_name = serializers.ReadOnlyField(source='trainer.surname')
    class Meta:
        model = Training
        fields = '__all__'

class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
