from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from environments.models import Room
from django.http import JsonResponse
from datetime import datetime, timezone, timedelta
from sensors_data.influx_manager import get_influx_client
import os

@login_required
def home(request):
    """ Main dashboard view. Restricted access to RESIDENT and DEVELOPER (tests)"""

    user = request.user

    if user.role == 'CAREGIVER':
        return redirect('dashboard:caregiver_home')

    if user.role == 'DEVELOPER':
        return redirect('developer:developer_home')
    
    if user.role not in ['RESIDENT', 'DEVELOPER']:
        return redirect('login')

    if not Room.objects.filter(home__owner=user).exists():
        return redirect('wizard')
    
    rooms = Room.objects.filter(home__owner=user)
    
    context = {
        'role_display': user.get_role_display(),
        'is_developer': user.role == 'DEVELOPER',
        'rooms': rooms
    }

    return render(request, 'dashboard/resident.html', context)

@login_required
def developer_dashboard(request):
    """ Dashboard view for developers. Restricted access to DEVELOPER role. """
    user = request.user

    if user.role != 'DEVELOPER':
        return redirect('dashboard:home')
    
    # Developers see all rooms or we can just pass all rooms in the system
    rooms = Room.objects.all()
    
    context = {
        'role_display': user.get_role_display(),
        'is_developer': True,
        'rooms': rooms
    }

    return render(request, 'dashboard/resident.html', context)

@login_required
def caregiver_home(request):
    """ Dashboard view for caregivers. Restricted access to CAREGIVER role. """

    if request.user.role != 'CAREGIVER' and request.user.role != 'DEVELOPER':
        return redirect('dashboard:home')
    
    context = {
        'view_type': 'Caregiver',
    }

    return render(request, 'dashboard/caregiver_home.html', context)

@login_required
def heatmap_data(request, room_id):

    mode = request.GET.get('mode', 'accumulated')
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)

    now = datetime.now(timezone.utc)
    if mode == 'live':
        start = now - timedelta(seconds=30)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    bucket = os.getenv("INFLUXDB_BUCKET", "sensors_data")
    org = os.getenv("INFLUXDB_ORG")

    flux = f'''
    from(bucket: "{bucket}")
      |> range(start: {start.isoformat()}, stop: {now.isoformat()})
      |> filter(fn: (r) => r["_measurement"] == "radar_data")
      |> filter(fn: (r) => r["room_id"] == "{room.id}")
      |> filter(fn: (r) => r["_field"] == "x" or r["_field"] == "y")
      |> pivot(rowKey:["_time","target_id","radar_sn"], columnKey:["_field"], valueColumn:"_value")
      |> keep(columns:["x","y"])
    '''

    client = get_influx_client()
    tables = client.query_api().query(flux, org=org)
    client.close()

    points = []
    for table in tables:
        for record in table.records:
            x = record.values.get("x")
            y = record.values.get("y")
            if x is not None and y is not None:
                points.append({"x": round(x, 4), "y": round(y, 4)})

    return JsonResponse({
        "points": points,
        "room": {"width": room.width, "depth": room.depth, "name": room.name},
        "query_range": {"start": start.isoformat(), "end": now.isoformat()},
    })