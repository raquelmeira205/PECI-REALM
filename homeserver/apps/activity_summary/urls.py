from django.urls import path
from . import views

app_name = 'activity_summary'

urlpatterns = [
    path('weekly/', views.weekly_summary, name='weekly_summary'),
]
