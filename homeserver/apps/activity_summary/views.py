import os
from datetime import timedelta
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from environments.models import Room
from sensors_data.influx_manager import get_influx_client


@login_required
def weekly_summary(request):
    user = request.user
    rooms = Room.objects.filter(home__owner=user)
    if not rooms.exists():
        return redirect('deployment:wizard_start')

    room_id = request.GET.get('room_id')
    if room_id:
        try:
            room = rooms.get(id=room_id)
        except Room.DoesNotExist:
            room = rooms.first()
    else:
        room = rooms.first()

    now = timezone.now()
    start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    bucket = os.getenv('INFLUXDB_BUCKET', 'sensors_data')
    org = os.getenv('INFLUXDB_ORG', '')

    flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start.isoformat()}, stop: {now.isoformat()})
  |> filter(fn: (r) => r["_measurement"] == "radar_data")
  |> filter(fn: (r) => r["room_id"] == "{room.id}")
  |> filter(fn: (r) => r["_field"] == "x")
  |> aggregateWindow(every: 1d, fn: count, createEmpty: true)
'''

    client = get_influx_client()
    tables = client.query_api().query(flux, org=org)
    client.close()

    day_counts = {(start + timedelta(days=i)).date(): 0 for i in range(7)}
    for table in tables:
        for record in table.records:
            record_time = record.get_time()
            if record_time is None:
                continue
            record_date = record_time.date()
            if record_date in day_counts:
                day_counts[record_date] = int(record.get_value() or 0)

    days = []
    for i in range(7):
        current_date = (start + timedelta(days=i)).date()
        days.append({
            'date': current_date,
            'label': current_date.strftime('%a'),
            'count': day_counts.get(current_date, 0),
        })

    max_count = max([day['count'] for day in days] + [1])
    for day in days:
        day['height'] = int((day['count'] / max_count) * 100)

    total_activity = sum(day['count'] for day in days)
    average_activity = total_activity / 7
    if max_count == 0:
        summary_title = 'Sem atividade registada nesta semana'
        summary_message = 'Não foram encontrados dados de presença para este espaço nos últimos 7 dias.'
    elif average_activity >= max_count * 0.65:
        summary_title = 'Semana ativa'
        summary_message = 'Esta semana está acima da sua média, com bastante presença registada.'
    elif average_activity >= max_count * 0.35:
        summary_title = 'Semana moderada'
        summary_message = 'A sua atividade esta semana foi equilibrada. Continue monitorizando.'
    else:
        summary_title = 'Semana tranquila'
        summary_message = 'A atividade foi mais baixa do que o habitual nos últimos 7 dias.'

    # ── Daily stats: today vs yesterday ─────────────────────────────────────
    today_date = now.date()
    yesterday_date = (now - timedelta(days=1)).date()
    today_count = day_counts.get(today_date, 0)
    yesterday_count = day_counts.get(yesterday_date, 0)

    if yesterday_count == 0:
        daily_change_pct = None
        daily_trend = 'neutral'
    else:
        daily_change_pct = round(((today_count - yesterday_count) / yesterday_count) * 100)
        daily_trend = 'up' if daily_change_pct > 0 else ('down' if daily_change_pct < 0 else 'neutral')

    return render(request, 'activity_summary/weekly.html', {
        'rooms': rooms,
        'room': room,
        'days': days,
        'total_activity': total_activity,
        'summary_title': summary_title,
        'summary_message': summary_message,
        # daily comparison
        'today_count': today_count,
        'yesterday_count': yesterday_count,
        'daily_change_pct': daily_change_pct,
        'daily_trend': daily_trend,
        'today_label': today_date.strftime('%d %b'),
        'yesterday_label': yesterday_date.strftime('%d %b'),
        # sidebar / user context
        'role_display': user.get_role_display(),
        'is_developer': user.role == 'DEVELOPER',
    })
