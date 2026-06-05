# apps/deployment/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ── Wizard principal ───────────────────────────────────────────────────
    path('welcome/',                          views.deployment_welcome,        name='deployment_welcome'),
    path('wizard/',                           views.SetupWizardView.as_view(), name='wizard'),

    # ── Steps HTMX ────────────────────────────────────────────────────────
    path('api/step1/',                        views.wizard_step_1,             name='wizard_step_1'),
    path('api/step2/',                        views.wizard_step_2,             name='wizard_step_2'),
    path('api/room/<int:room_id>/',           views.api_delete_room,           name='api_delete_room'),
    path('api/step3-intro/',                  views.wizard_step_3_intro,       name='wizard_step_3_intro'),
    path('api/step3/',                        views.wizard_step_3,             name='wizard_step_3'),
    path('api/configure-room/<int:room_id>/', views.configure_room_view,       name='configure_room'),
    path('api/scan/<int:room_id>/',           views.wizard_scan_radar,         name='wizard_scan_radar'),
    path('api/confirm-radars/<int:room_id>/', views.wizard_confirm_radars, name='wizard_confirm_radars'),

    # ── Captura para calibração ────────────────────────────────────────────
    path('api/calibration-capture/<int:room_id>/<str:radar_sn>/', views.wizard_calibration_capture, name='wizard_calibration_capture'),
    path('api/calibration-start/<int:room_id>/<str:radar_sn>/',   views.api_calibration_start,       name='api_calibration_start'),
    path('api/calibration-stop/<int:room_id>/<str:radar_sn>/',    views.api_calibration_stop,        name='api_calibration_stop'),

    # ── Calibração ─────────────────────────────────────────────────────────
    path('api/calibrate-intro/<int:room_id>/<str:radar_sn>/', views.wizard_calibrate_intro, name='wizard_calibrate_intro'),
    path('api/calibrate/<int:room_id>/<str:radar_sn>/', views.wizard_calibrate_radar, name='wizard_calibrate_radar'),
    
    path('api/calibrate-worker-intro/<int:room_id>/<str:radar_sn>/', views.wizard_calibrate_worker_intro, name='wizard_calibrate_worker_intro'),
    path('api/calibrate-worker/<int:room_id>/<str:radar_sn>/', views.wizard_calibrate_worker, name='wizard_calibrate_worker'),
    path('api/save-worker-position/<int:room_id>/<str:radar_sn>/', views.api_save_worker_position, name='api_save_worker_position'),

    # Endpoint JSON: devolve pontos frescos da InfluxDB (botão "Atualizar")
    path('api/calibration-context/<int:room_id>/<str:radar_sn>/',
         views.api_get_calibration_context,
         name='api_calibration_context'),

    # Endpoint POST: guarda azimute, tilt e posição no modelo Radar
    path('api/calibration/<str:radar_sn>/save/',
         views.api_save_calibration,
         name='api_save_calibration'),

     path('api/slave-sync/<int:room_id>/',      views.wizard_slave_sync,    name='wizard_slave_sync'),
     path('api/send-ntp-sync/<int:room_id>/',   views.api_send_ntp_sync,    name='api_send_ntp_sync'),
     path('api/sync-capture-intro/<int:room_id>/', views.wizard_sync_capture_intro, name='wizard_sync_capture_intro'),
     path('api/sync-capture/<int:room_id>/',    views.wizard_sync_capture,   name='wizard_sync_capture'),
     path('api/start-capture/<int:room_id>/',   views.api_start_capture,     name='api_start_capture'),
     path('api/stop-align/<int:room_id>/',      views.api_stop_and_align,    name='api_stop_and_align'),
     path('api/fusion-preview/<int:room_id>/',  views.wizard_fusion_preview, name='wizard_fusion_preview'),
     path('api/fusion-data/<int:room_id>/',     views.api_fusion_data,       name='api_fusion_data'),
]