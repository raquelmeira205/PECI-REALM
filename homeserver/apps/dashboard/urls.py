from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard:home', permanent=False)),
    path('resident/', views.home, name='home'),
    path('developer/', views.developer_dashboard, name='developer_dashboard'),
    path('api/heatmap/<int:room_id>/', views.heatmap_data, name='heatmap_data'),
    
    path('monitor/', views.caregiver_home, name='caregiver_home'),
]