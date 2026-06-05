from django.db import models
from core.models import BaseModel

class AcquisitionSession(BaseModel):
    """Represents one recording session (one JSON file from data_acquisition.py)"""
    radar = models.ForeignKey('sensors_devices.Radar', on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    total_frames = models.IntegerField(default=0)
    source_file = models.CharField(max_length=255, blank=True, help_text="Original JSON filename")

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Session {self.source_file} ({self.total_frames} frames)"


class RadarFrame(models.Model):
    """One frame from the radar — corresponds to one entry in the JSON array"""
    session = models.ForeignKey(AcquisitionSession, on_delete=models.CASCADE, related_name='frames')
    frame_number = models.IntegerField()
    timestamp = models.DateTimeField()
    num_detected_points = models.IntegerField(default=0)
    num_detected_tracks = models.IntegerField(default=0)

    # Stored directly as JSON 
    # Format: [[x, y, z, velocity, intensity], ...]
    point_cloud = models.JSONField(default=list)

    # Format: [[track_id, x, y, z, vx, vy, vz], ...]
    track_data = models.JSONField(default=list)

    class Meta:
        ordering = ['frame_number']

    def __str__(self):
        return f"Frame {self.frame_number} (session {self.session_id})"
