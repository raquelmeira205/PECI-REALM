from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from users.views import RedirectAfterLoginView
from users import views as users_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('api/', include('deployment.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', users_views.custom_logout_view, name='logout'),
    path('redirect-user/', RedirectAfterLoginView.as_view(), name='redirect_after_login'),
    path('dashboard/', include('dashboard.urls')),
    path('deployment/', include('deployment.urls')),
    path('developer/', include('developer.urls')),
    path('activity-summary/', include('activity_summary.urls')),
]
