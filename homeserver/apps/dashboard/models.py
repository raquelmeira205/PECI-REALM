from django.db import models

class ActivitySummary(models.Model):
    # Link to the room that is in the 'environments' app
    room = models.ForeignKey('environments.Room', on_delete=models.CASCADE, related_name='summaries')
    date = models.DateField()
    distance_covered = models.FloatField(default=0.0)
    average_speed = models.FloatField(default=0.0)
    activity_level = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('room', 'date')
        ordering = ['-date']