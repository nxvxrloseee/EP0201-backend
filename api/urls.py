from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, TrainingViewSet, ReportViewSet

router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'trainings', TrainingViewSet)
router.register(r'reports', ReportViewSet, basename='reports')

urlpatterns = [
    path('', include(router.urls)),

]