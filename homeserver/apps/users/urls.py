# apps/users/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.register_view, name='signup'), # Ou 'register/'
    path('', views.root_redirect_view, name='root'),
]