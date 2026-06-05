from django.db import models
from core.models import BaseModel

class Home(BaseModel):
    """ Represents a home environment where devices are deployed. 
        Examples: "John's Apartment", "Smith Family House" """
    name = models.CharField(max_length=255)
    
    owner = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='homes')

    def __str__(self):
        return self.name

class Room(BaseModel):
    name = models.CharField(max_length=100, help_text="Name of the room (e.g., Living Room, Kitchen)")
    
    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name='rooms')
    width = models.FloatField(help_text="Width in meters (X axis)", null=False, blank=False)
    depth = models.FloatField(help_text="Depth in meters (Y axis)", null=False, blank=False)
    height = models.FloatField(help_text="Height in meters (Z axis)", default=3.0)

    def __str__(self):
        return self.name
