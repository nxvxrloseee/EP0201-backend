from django.contrib import admin
from .models import Client, Trainer, Training, User, Membership, MembershipType, Attendance, Payment, Hall

admin.site.register(Hall)

admin.site.register(Client)
admin.site.register(Trainer)
admin.site.register(Training)
admin.site.register(User)
admin.site.register(Membership)
admin.site.register(MembershipType)
admin.site.register(Attendance)
admin.site.register(Payment)