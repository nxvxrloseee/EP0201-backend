from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *

router = DefaultRouter()
router.register(r'trainers', TrainerListViewSet)
router.register(r'clients', ClientViewSet)
router.register(r'memberships', MembershipViewSet)
router.register(r'trainings', TrainingViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'reports', ReportViewSet, basename='reports')

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),

]