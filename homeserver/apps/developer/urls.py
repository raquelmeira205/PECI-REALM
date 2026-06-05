from django.urls import path
from . import views

app_name = 'developer'

urlpatterns = [
    path('home/', views.DeveloperHomeView.as_view(), name='developer_home'),
    path('session/<int:session_id>/', views.SessionDetailView.as_view(), name='developer_session_detail'),
    path('session/<int:session_id>/stop/', views.stop_capture_view, name='developer_stop_capture'),
]
