from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from environments.models import Room

@login_required
def manage_environments(request):
    """ View for managing environments (homes and rooms) """

    if request.user.role not in ['RESIDENT', 'DEVELOPER']:
        return render(request, '403.html', status=403)
    
    rooms = Room.objects.filter(home__owner=request.user)
    return render(request, 'environments/manage.html', {'rooms': rooms})