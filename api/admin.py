from django.contrib import admin
from .models import Client, Trainer, Training, User, Membership, MembershipType, Attendance, Payment, Hall

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('surname', 'name', 'phone', 'registration_date')
    search_fields = ('surname', 'phone')

@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('date_time', 'trainer', 'training_type', 'hall', 'status')
    list_filter = ('status', 'trainer')

admin.site.register(User)
admin.site.register(Trainer)
admin.site.register(Membership)
admin.site.register(MembershipType)
admin.site.register(Payment)
admin.site.register(Attendance)
admin.site.register(Hall)