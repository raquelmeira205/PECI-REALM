from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import StartCaptureForm
from .models import AcquisitionSession
from sensors_devices.models import Radar
from deployment.views import _publish_mqtt_command


def _get_active_radars():
    """Devolve queryset de radares ativos e online."""
    return Radar.objects.filter(is_online=True)


def _stop_active_sessions():
    """Encerra todas as sessões de aquisição ainda em curso."""
    active_sessions = AcquisitionSession.objects.filter(ended_at__isnull=True)
    now = timezone.now()
    for session in active_sessions:
        # Enviar comando de stop ao radar via MQTT
        try:
            _publish_mqtt_command(session.radar.network_id, 'stop')
        except Exception:
            pass  # Não bloquear se o MQTT falhar
        session.ended_at = now
        session.total_frames = session.frames.count()
        session.save()


class DeveloperHomeView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        form = StartCaptureForm()
        query = request.GET.get('q', '').strip()
        sessions = AcquisitionSession.objects.select_related('radar').all().order_by('-started_at')
        if query:
            sessions = sessions.filter(
                Q(source_file__icontains=query)
                | Q(radar__network_id__icontains=query)
                | Q(radar__name__icontains=query)
            )
        active_sessions = AcquisitionSession.objects.filter(ended_at__isnull=True).select_related('radar')
        available_radars = _get_active_radars()

        return render(request, 'developer/home.html', {
            'form': form,
            'sessions': sessions,
            'active_sessions': active_sessions,
            'available_radars': available_radars,
            'query': query,
        })

    def post(self, request, *args, **kwargs):
        form = StartCaptureForm(request.POST)
        query = request.GET.get('q', '').strip()
        error = None

        if form.is_valid():
            # Recolher IDs de radar selecionados via checkboxes
            selected_ids = request.POST.getlist('radar_ids')

            if selected_ids:
                # Usar apenas os radares selecionados que existam e estejam online
                radars_to_capture = Radar.objects.filter(
                    id__in=selected_ids, is_online=True
                )
            else:
                # DEFAULT: todos os radares online (captura conjunta e sincronizada)
                radars_to_capture = _get_active_radars()

            if not radars_to_capture.exists():
                error = 'Nenhum radar online disponível para captura.'
            else:
                # Encerrar automaticamente quaisquer sessões ativas (auto-stop + MQTT stop)
                _stop_active_sessions()

                started_at = timezone.now()
                capture_name = form.cleaned_data['name']

                # Criar uma sessão por radar e enviar comando start via MQTT
                for radar in radars_to_capture:
                    AcquisitionSession.objects.create(
                        radar=radar,
                        started_at=started_at,
                        source_file=capture_name,
                    )
                    try:
                        _publish_mqtt_command(radar.network_id, 'start')
                    except Exception:
                        pass  # Não bloquear se o MQTT falhar

                return redirect('developer:developer_home')
        else:
            error = 'Corrija os erros do formulário e tente novamente.'

        sessions = AcquisitionSession.objects.select_related('radar').all().order_by('-started_at')
        if query:
            sessions = sessions.filter(
                Q(source_file__icontains=query)
                | Q(radar__network_id__icontains=query)
                | Q(radar__name__icontains=query)
            )
        active_sessions = AcquisitionSession.objects.filter(ended_at__isnull=True).select_related('radar')
        available_radars = _get_active_radars()

        return render(request, 'developer/home.html', {
            'form': form,
            'sessions': sessions,
            'active_sessions': active_sessions,
            'available_radars': available_radars,
            'query': query,
            'error': error,
        })


class SessionDetailView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, session_id, *args, **kwargs):
        session = get_object_or_404(AcquisitionSession.objects.select_related('radar'), pk=session_id)
        frames = session.frames.all().order_by('frame_number')
        return render(request, 'developer/session_detail.html', {
            'session': session,
            'frames': frames,
        })


def stop_capture_view(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(AcquisitionSession, pk=session_id, ended_at__isnull=True)
        try:
            _publish_mqtt_command(session.radar.network_id, 'stop')
        except Exception:
            pass
        session.ended_at = timezone.now()
        session.total_frames = session.frames.count()
        session.save()
    return redirect('developer:developer_home')
