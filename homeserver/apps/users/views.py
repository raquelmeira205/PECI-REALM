from django.shortcuts import render
from django.shortcuts import redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from environments.models import Room, Home
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm

class RedirectAfterLoginView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        role = user.role
        
        has_rooms = Room.objects.filter(home__owner=user).exists()

        # Developer users must complete setup if they have no rooms
        if role == 'DEVELOPER':
            if not has_rooms:
                return redirect('/deployment/wizard')
            return redirect('/developer/home')
        
        print(has_rooms)
        print(user)
        if role == 'RESIDENT':
            if not has_rooms:
                return redirect('/deployment/wizard')
            return redirect('/dashboard/resident')
        elif role == 'CAREGIVER':
            return redirect('/dashboard/caregiver_home')
        
        return redirect('/admin/')
    
def register_view(request):
    """ View for user registration. """

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            if user.role == 'RESIDENT':
                Home.objects.create(owner=user, name=f"Casa de {user.first_name}")
            elif user.role == 'DEVELOPER':
                Home.objects.create(owner=user, name="Sala de testes")

            login(request, user)

            # Redirect to welcome page for new residents and developers instead of straight to dashboard
            if user.role in ['RESIDENT', 'DEVELOPER']:
                return redirect('deployment_welcome')
            
            return redirect('redirect_after_login')
        
    else:
        form = CustomUserCreationForm()

    return render(request, 'users/signup.html', {'form': form})

def root_redirect_view(request):
    if request.user.is_authenticated:
        return redirect('redirect_after_login')
    else:
        return redirect('login')

def custom_logout_view(request):
    logout(request)
    return redirect('login')
