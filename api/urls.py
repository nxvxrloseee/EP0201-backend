from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

router = DefaultRouter()
router.register(r'trainers', TrainerListViewSet)
router.register(r'clients', ClientViewSet)
router.register(r'memberships', MembershipViewSet)
router.register(r'trainings', TrainingViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'halls', HallViewSet)

urlpatterns = [
    path('auth/login/', MTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),

# Отчёты (НЕ через ViewSet!)
    path('reports/revenue/', revenue_report, name='revenue_report'),
    path('reports/attendance/', attendance_report, name='attendance_report'),
    path('reports/trainer_performance/', trainer_performance_report, name='trainer_performance'),
    path('reports/expiring_memberships/', expiring_memberships_report, name='expiring_memberships'),
]