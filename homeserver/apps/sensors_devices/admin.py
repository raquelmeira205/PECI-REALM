from django.contrib import admin
from .models import Radar

@admin.register(Radar)
class RadarAdmin(admin.ModelAdmin):
    list_display = (
        'network_id',
        'status',
        'is_master',
        'is_online',
        'room',
        'last_seen',
        'azimuth_deg',
        'tilt_deg',
        'pos_x',
        'pos_y',
        'pos_z',
    )
    list_filter = ('status', 'is_master', 'is_online', 'room')
    search_fields = ('network_id',)
    readonly_fields = ('last_seen',)