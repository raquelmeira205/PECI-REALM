from django.db import models
from core.models import BaseModel

class Radar(BaseModel):
    class OperationalStatus(models.TextChoices):
        UNASSIGNED = 'UNASSIGNED', 'Not Assigned to Room'
        PENDING = 'PENDING', 'Calibration Pending'
        ACTIVE = 'ACTIVE', 'Active and Monitoring'
        ERROR = 'ERROR', 'Error State'
        SYNCING = 'SYNCING', 'Synchronizing Data'

    network_id = models.CharField(max_length=100, unique=True)

    room = models.ForeignKey('environments.Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='radars')

    is_master = models.BooleanField(default=False, help_text="Indicates if this radar is the master in its room")
    is_online = models.BooleanField(default=False, help_text="Indicates if the radar is currently online and communicating")

    status = models.CharField(max_length=20, choices=OperationalStatus.choices, default=OperationalStatus.UNASSIGNED)
    last_seen = models.DateTimeField(null=True, blank=True)

    # CALIBRATION PARAMETERES
    pos_x = models.FloatField(default=0.0, help_text="Posição X na sala (metros)")
    pos_y = models.FloatField(default=0.0, help_text="Posição Y na sala (metros)")
    pos_z = models.FloatField(default=0.0, help_text="Altura Z do radar (metros)")
    
    azimuth_deg = models.FloatField(default=0.0, help_text="Rotação no plano XY (graus)")
    tilt_deg = models.FloatField(default=0.0, help_text="Inclinação em relação ao chão (graus)")
    
    # Booleano para saber se o passo 4 foi concluído
    is_calibrated = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # If this radar is set as master, ensure all other radars in the same room are not master
        if self.is_master and self.room:
            Radar.objects.filter(
                room=self.room, 
                is_master=True
            ).exclude(id=self.id).update(is_master=False)
        super().save(*args, **kwargs)

    def __str__(self):
        # network_id is the canonical human-readable identifier for a Radar.
        # There is no separate 'name' field on this model.
        return self.network_id