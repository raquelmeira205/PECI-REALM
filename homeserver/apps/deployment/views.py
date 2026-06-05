import json
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from django.db.models import Exists, OuterRef
from environments.models import Room, Home
from sensors_devices.models import Radar
from sensors_devices.utils import get_radar_calibration_snapshot, get_radar_pointcloud_snapshot

import os
import paho.mqtt.client as mqtt
from django.core.cache import cache
from datetime import datetime, timezone as dt_tz
from sensors_devices.alignment import run_alignment


@login_required
def deployment_welcome(request):
    """Welcome page for new residents after signup."""
    return render(request, 'deployment/welcome.html')


class SetupWizardView(TemplateView):
    template_name = "deployment/wizard.html"


@login_required
def wizard_step_1(request):
    if request.method == "POST":
        name = request.POST.get('home_name', '').strip()
        if not name:
            name = f"Casa de {request.user.first_name}"
        home, _ = Home.objects.get_or_create(owner=request.user)
        home.name = name
        home.save()
        return render(request, 'deployment/partials/step_2.html', {'rooms': home.rooms.all()})

    home, _ = Home.objects.get_or_create(owner=request.user)
    if not home.name:
        home.name = f"Casa de {request.user.first_name}"
    return render(request, 'deployment/partials/step_1.html', {'home': home})


@login_required
def wizard_step_2(request):
    home = Home.objects.get(owner=request.user)
    if request.method == "POST":
        name = request.POST.get('name')
        width = request.POST.get('width')
        depth = request.POST.get('depth')
        if name:
            Room.objects.create(home=home, name=name, width=width or 0.0, depth=depth or 0.0)
    return render(request, 'deployment/partials/step_2.html', {'rooms': home.rooms.all()})


@login_required
@require_http_methods(['DELETE'])
def api_delete_room(request, room_id):
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)
    home = room.home
    room.delete()
    return render(request, 'deployment/partials/step_2.html', {'rooms': home.rooms.all()})


@login_required
def wizard_step_3_intro(request):
    return render(request, 'deployment/partials/step_3_intro.html')


@login_required
def wizard_step_3(request):
    home = Home.objects.get(owner=request.user)
    rooms = home.rooms.annotate(
        has_master=Exists(Radar.objects.filter(room=OuterRef('pk'), is_master=True))
    )
    return render(request, 'deployment/partials/step_3.html', {'rooms': rooms})


@login_required
def configure_room_view(request, room_id):
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)
    has_master = Radar.objects.filter(room=room, is_master=True).exists()
    return render(request, 'deployment/partials/step_3_configure_room.html', {'room': room, 'has_master': has_master})


@login_required
def wizard_scan_radar(request, room_id):
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)
    recent_cutoff = timezone.now() - timedelta(seconds=30)
    available_radars = Radar.objects.filter(room__isnull=True, last_seen__gte=recent_cutoff)
    has_master = Radar.objects.filter(room=room, is_master=True).exists()

    if available_radars.exists():
        role_label = "Mestre" if not has_master else "Secundários"
        return render(request, 'deployment/partials/step_3_scan.html', {
            'status': 'found_radars',
            'radars': available_radars,
            'role_label': role_label,
            'has_master': has_master,
            'room': room,
            'confirm_url': f'/deployment/api/confirm-radars/{room.id}/',
        })
    else:
        return render(request, 'deployment/partials/step_3_scan.html', {
            'status': 'scanning',
            'msg':    'A procurar radares (Ligue o radar agora)...',
            'room':   room,
        })


@login_required
@require_http_methods(['POST'])
def wizard_confirm_radars(request, room_id):
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)
    has_master = Radar.objects.filter(room=room, is_master=True).exists()
    
    radar_sns = request.POST.getlist('radar_sns')
    if not radar_sns:
        return render(request, 'deployment/partials/step_3_scan.html', {
            'status': 'error',
            'msg': 'Nenhum radar selecionado.',
            'room': room,
        })
        
    radars = list(Radar.objects.filter(network_id__in=radar_sns, room__isnull=True))
    if not radars:
        return render(request, 'deployment/partials/step_3_scan.html', {
            'status': 'error',
            'msg': 'Os radares selecionados já não estão disponíveis.',
            'room': room,
        })

    if not has_master:
        radar = radars[0]
        radar.room = room
        radar.is_master = True
        radar.status = Radar.OperationalStatus.PENDING
        radar.save()
        return render(request, 'deployment/partials/step_3_scan.html', {
            'status': 'calibrate',
            'msg': f'Radar {radar.network_id} associado como Master.',
            'room': room,
            'calibrate_url': f'/deployment/api/calibrate-intro/{room.id}/{radar.network_id}/',
        })
    else:
        for radar in radars:
            radar.room = room
            radar.is_master = False
            radar.status = Radar.OperationalStatus.PENDING
            radar.save()
            
        pending_list = [r.network_id for r in radars]
        request.session[f'pending_slaves_{room.id}'] = pending_list
        request.session[f'total_pending_slaves_{room.id}'] = len(pending_list)
        
        first_radar_sn = pending_list[0]
        return render(request, 'deployment/partials/step_3_scan.html', {
            'status': 'calibrate_worker',
            'msg': f'{len(radars)} radares associados como Secundários.',
            'room': room,
            'calibrate_url': f'/deployment/api/calibrate-worker-intro/{room.id}/{first_radar_sn}/',
        })


@login_required
def wizard_calibration_capture(request, room_id, radar_sn):
    """Ecrã intermédio de captura (Iniciar / Encerrar) antes dos ajustes."""
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)
    return render(request, 'deployment/partials/step_3_capture.html', {
        'room':   room,
        'radar':  radar,
        'status': 'idle',
    })


@login_required
@require_http_methods(['POST'])
def api_calibration_start(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)
    _publish_mqtt_command(radar_sn, 'start')
    cache.set(f'calibration_start_{radar_sn}', datetime.now(dt_tz.utc).isoformat(), timeout=86400)
    return render(request, 'deployment/partials/step_3_capture.html', {
        'room':   room,
        'radar':  radar,
        'status': 'capturing',
    })


@login_required
@require_http_methods(['POST'])
def api_calibration_stop(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)
    _publish_mqtt_command(radar_sn, 'stop')

    stop_time = datetime.now(dt_tz.utc)
    cache.set(f'calibration_stop_{radar_sn}', stop_time.isoformat(), timeout=86400)
    start_time, _ = _get_cached_capture_window(radar_sn)

    room_bounds = {
        'x_max': float(room.width),
        'y_max': float(room.depth),
        'z_max': float(room.height),
    }
    raw_points = get_radar_calibration_snapshot(radar_sn, start_time=start_time, stop_time=stop_time)
    radar_config = {
        'x':       float(radar.pos_x       or 0),
        'y':       float(radar.pos_y       or 0),
        'z':       float(radar.pos_z       or 0),
        'azimuth': float(radar.azimuth_deg or 0),
        'tilt':    float(radar.tilt_deg    or 90),
    }
    calibration_data = {
        'room':                 room_bounds,
        'radar_current_config': radar_config,
        'raw_points':           raw_points,
    }
    pos_fields = [
        ('X', str(radar_config['x']), str(round(room_bounds['x_max'], 2))),
        ('Y', str(radar_config['y']), str(round(room_bounds['y_max'], 2))),
        ('Z', str(radar_config['z']), str(round(room_bounds['z_max'], 2))),
    ]
    return render(request, 'deployment/partials/step_3b_calibrate.html', {
        'room':                  room,
        'radar':                 radar,
        'calibration_data_json': json.dumps(calibration_data),
        'point_count':           len(raw_points),
        'pos_fields':            pos_fields,
        'effective_azimuth':     str(radar_config['azimuth']),
        'effective_tilt':        str(radar_config['tilt']),
    })


@login_required
def wizard_calibrate_intro(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)
    return render(request, 'deployment/partials/step_3_calibrate_intro.html', {'room': room, 'radar': radar})

@login_required
def wizard_calibrate_worker_intro(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)
    
    pending = request.session.get(f'pending_slaves_{room.id}', [])
    total = request.session.get(f'total_pending_slaves_{room.id}', len(pending))
    current_index = total - len(pending) + 1 if total > 0 else 1
    
    return render(request, 'deployment/partials/step_3_calibrate_worker_intro.html', {
        'room': room, 
        'radar': radar,
        'current_index': current_index,
        'total_pending': total
    })

@login_required
def wizard_calibrate_worker(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)
    pos_fields = [
        ('X', float(radar.pos_x or 0), round(float(room.width),  2)),
        ('Y', float(radar.pos_y or 0), round(float(room.depth),  2)),
        ('Z', float(radar.pos_z or 0), round(float(room.height), 2)),
    ]
    return render(request, 'deployment/partials/step_3_calibrate_worker.html', {
        'room':            room,
        'radar':           radar,
        'pos_fields':      pos_fields,
        'azimuth_initial': float(radar.azimuth_deg or 0),
        'room_bounds':     {'x_max': float(room.width), 'y_max': float(room.depth)},
    })


@login_required
@require_http_methods(['POST'])
def api_save_worker_position(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)

    radar.pos_x       = float(request.POST.get('x',       radar.pos_x       or 0))
    radar.pos_y       = float(request.POST.get('y',       radar.pos_y       or 0))
    radar.pos_z       = float(request.POST.get('z',       radar.pos_z       or 0))
    radar.azimuth_deg = float(request.POST.get('azimuth', radar.azimuth_deg or 0))
    radar.is_calibrated = True
    radar.status = Radar.OperationalStatus.ACTIVE
    radar.save()

    session_key = f'pending_slaves_{room.id}'
    pending = request.session.get(session_key, [])
    if radar_sn in pending:
        pending.remove(radar_sn)
        request.session[session_key] = pending

    if pending:
        next_radar_sn = pending[0]
        return wizard_calibrate_worker_intro(request, room_id, next_radar_sn)

    slaves     = Radar.objects.filter(room=room, is_master=False)
    all_active = all(r.status == Radar.OperationalStatus.ACTIVE for r in slaves)
    return render(request, 'deployment/partials/step_slave_sync.html', {
        'room':       room,
        'slaves':     slaves,
        'all_active': all_active,
    })


@login_required
def wizard_calibrate_radar(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)

    room_bounds = {
        'x_max': float(room.width),
        'y_max': float(room.depth),
        'z_max': float(room.height),
    }

    start_time, stop_time = _get_cached_capture_window(radar_sn)
    raw_points = get_radar_calibration_snapshot(radar_sn, start_time=start_time, stop_time=stop_time)

    radar_config = {
        'x':       float(radar.pos_x       or 0),
        'y':       float(radar.pos_y       or 0),
        'z':       float(radar.pos_z       or 0),
        'azimuth': float(radar.azimuth_deg or 0),
        'tilt':    float(radar.tilt_deg    or 90),
    }

    calibration_data = {
        'room':                 room_bounds,
        'radar_current_config': radar_config,
        'raw_points':           raw_points,  # [[x,y,z], ...]
    }

    pos_fields = [
        ('X', str(radar_config['x']), str(round(room_bounds['x_max'], 2))),
        ('Y', str(radar_config['y']), str(round(room_bounds['y_max'], 2))),
        ('Z', str(radar_config['z']), str(round(room_bounds['z_max'], 2))),
    ]

    return render(request, 'deployment/partials/step_3b_calibrate.html', {
        'room':                  room,
        'radar':                 radar,
        'calibration_data_json': json.dumps(calibration_data),
        'point_count':           len(raw_points),
        'pos_fields':            pos_fields,
        'effective_azimuth':     str(radar_config['azimuth']),
        'effective_tilt':        str(radar_config['tilt']),
    })


@login_required
@require_http_methods(['GET'])
def api_get_calibration_context(request, room_id, radar_sn):
    room  = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radar = get_object_or_404(Radar, network_id=radar_sn, room=room)

    room_bounds = {
        'x_max': float(room.width),
        'y_max': float(room.depth),
        'z_max': float(room.height),
    }
    start_time, stop_time = _get_cached_capture_window(radar_sn)
    raw_points = get_radar_calibration_snapshot(radar_sn, start_time=start_time, stop_time=stop_time)

    return JsonResponse({
        'room': room_bounds,
        'radar_current_config': {
            'x':       float(radar.pos_x       or 0),
            'y':       float(radar.pos_y       or 0),
            'z':       float(radar.pos_z       or 0),
            'azimuth': float(radar.azimuth_deg or 0),
            'tilt':    float(radar.tilt_deg    or 90),
        },
        'raw_points': raw_points,
    })


@login_required
@require_http_methods(['POST'])
def api_save_calibration(request, radar_sn):
    try:
        data  = json.loads(request.body)
        radar = get_object_or_404(Radar, network_id=radar_sn)

        if radar.room and radar.room.home.owner != request.user:
            return JsonResponse({'status': 'error', 'message': 'Sem permissão.'}, status=403)

        radar.pos_x        = float(data.get('x',       radar.pos_x       or 0))
        radar.pos_y        = float(data.get('y',       radar.pos_y       or 0))
        radar.pos_z        = float(data.get('z',       radar.pos_z       or 0))
        radar.azimuth_deg  = float(data.get('azimuth', radar.azimuth_deg or 0))
        radar.tilt_deg     = float(data.get('tilt',    radar.tilt_deg    or 90))
        radar.is_calibrated = True
        radar.status = Radar.OperationalStatus.ACTIVE
        radar.save()

        if radar.is_online:
            _publish_mqtt_command(radar_sn, 'start')

        return JsonResponse({
            'status':  'success',
            'message': f'Calibração de {radar_sn} guardada com sucesso.',
        })

    except (ValueError, KeyError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Step 5b — Visualizador de fusão 2D
# ---------------------------------------------------------------------------

@login_required
def wizard_fusion_preview(request, room_id):
    room   = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radars = Radar.objects.filter(room=room)
    room_bounds   = {'x_max': float(room.width), 'y_max': float(room.depth)}
    radar_configs = [
        {'sn': r.network_id, 'is_master': r.is_master,
         'pos_x': float(r.pos_x), 'pos_y': float(r.pos_y)}
        for r in radars
    ]
    return render(request, 'deployment/partials/step_fusion_preview.html', {
        'room':               room,
        'room_bounds_json':   json.dumps(room_bounds),
        'radar_configs_json': json.dumps(radar_configs),
    })


@login_required
def api_fusion_data(request, room_id):
    from sensors_devices.alignment import transform_radar_points
    room   = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radars = Radar.objects.filter(room=room)

    start_str = cache.get(f'capture_start_{room_id}')
    stop_str  = cache.get(f'capture_stop_{room_id}')
    start_time = datetime.fromisoformat(start_str) if start_str else None
    stop_time  = datetime.fromisoformat(stop_str)  if stop_str  else None

    result = {}
    for radar in radars:
        raw = get_radar_pointcloud_snapshot(
            radar.network_id, seconds=30,
            start_time=start_time, stop_time=stop_time,
        )
        result[radar.network_id] = {
            'is_master': radar.is_master,
            'points':    transform_radar_points(raw, radar),
        }
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _publish_mqtt_command(radar_sn, command):
    """Publica um comando a um radar via MQTT (cliente one-shot)."""
    broker = os.getenv('MQTT_BROKER_HOST', 'mosquitto')
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(broker, 1883, 60)
    client.publish(f"radar/{radar_sn}/command", json.dumps({"command": command}))
    client.disconnect()


def _get_cached_capture_window(radar_sn):
    """Devolve (start_time, stop_time) UTC da última captura, ou (None, None)."""
    start_str = cache.get(f'calibration_start_{radar_sn}')
    stop_str  = cache.get(f'calibration_stop_{radar_sn}')
    if start_str and stop_str:
        return datetime.fromisoformat(start_str), datetime.fromisoformat(stop_str)
    return None, None


# ---------------------------------------------------------------------------
# Step 4 — Sincronização NTP dos slaves
# ---------------------------------------------------------------------------

@login_required
def wizard_slave_sync(request, room_id):
    room   = get_object_or_404(Room, id=room_id, home__owner=request.user)
    slaves = Radar.objects.filter(room=room, is_master=False)
    all_active = all(r.status == Radar.OperationalStatus.ACTIVE for r in slaves)
    return render(request, 'deployment/partials/step_slave_sync.html', {
        'room':       room,
        'slaves':     slaves,
        'all_active': all_active,
    })


@login_required
@require_http_methods(['POST'])
def api_send_ntp_sync(request, room_id):
    room   = get_object_or_404(Room, id=room_id, home__owner=request.user)
    slaves = Radar.objects.filter(room=room, is_master=False)

    for radar in slaves:
        radar.status = Radar.OperationalStatus.SYNCING
        radar.save(update_fields=['status'])
        _publish_mqtt_command(radar.network_id, 'ntp_sync')

    all_active = all(r.status == Radar.OperationalStatus.ACTIVE for r in slaves)
    return render(request, 'deployment/partials/step_slave_sync.html', {
        'room':       room,
        'slaves':     Radar.objects.filter(room=room, is_master=False),
        'all_active': all_active,
    })


# ---------------------------------------------------------------------------
# Step 5 — Captura sincronizada + alinhamento
# ---------------------------------------------------------------------------

@login_required
def wizard_sync_capture_intro(request, room_id):
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)
    return render(request, 'deployment/partials/slave_alignment_instruction.html', {'room': room})


@login_required
def wizard_sync_capture(request, room_id):
    room = get_object_or_404(Room, id=room_id, home__owner=request.user)
    return render(request, 'deployment/partials/step_sync_capture.html', {'room': room})


@login_required
@require_http_methods(['POST'])
def api_start_capture(request, room_id):
    room   = get_object_or_404(Room, id=room_id, home__owner=request.user)
    radars = Radar.objects.filter(room=room)

    start_time = timezone.now()
    cache.set(f'capture_start_{room_id}', start_time.isoformat(), timeout=3600)

    for radar in radars:
        _publish_mqtt_command(radar.network_id, 'start')

    return render(request, 'deployment/partials/step_sync_capture.html', {
        'room':       room,
        'capturing':  True,
        'start_time': start_time.strftime('%H:%M:%S'),
    })


@login_required
@require_http_methods(['POST'])
def api_stop_and_align(request, room_id):
    room     = get_object_or_404(Room, id=room_id, home__owner=request.user)
    end_time = timezone.now()
    cache.set(f'capture_stop_{room_id}', end_time.isoformat(), timeout=3600)

    start_time_str = cache.get(f'capture_start_{room_id}')
    if not start_time_str:
        return render(request, 'deployment/partials/step_sync_capture.html', {
            'room':  room,
            'error': 'Nenhuma captura em curso. Clica em "Iniciar Captura" primeiro.',
        })

    start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=dt_tz.utc)

    # Parar todos os radares
    for radar in Radar.objects.filter(room=room):
        _publish_mqtt_command(radar.network_id, 'stop')

    # Correr alinhamento
    master = Radar.objects.filter(room=room, is_master=True).first()
    slaves = list(Radar.objects.filter(room=room, is_master=False))
    results = run_alignment(master.network_id, slaves, start_time, end_time)

    for radar in Radar.objects.filter(room=room, is_calibrated=True, is_online=True):
        _publish_mqtt_command(radar.network_id, 'start')

    cache.delete(f'capture_start_{room_id}')

    return render(request, 'deployment/partials/step_sync_capture.html', {
        'room':    room,
        'done':    True,
        'results': results,
    })