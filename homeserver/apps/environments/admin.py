from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Room, Home

@admin.register(Home)
class HomeAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'delete_button')
    search_fields = ('name', 'owner__username')
    
    def delete_button(self, obj):
        url = reverse('admin:environments_home_delete', args=[obj.pk])
        return format_html('<a class="button" style="background-color: #ba2121; color: white; padding: 4px 8px; border-radius: 4px;" href="{}">Deletar</a>', url)
    delete_button.short_description = 'Deletar'


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'width', 'depth', 'height', 'delete_button')
    search_fields = ('name',)
    
    def delete_button(self, obj):
        url = reverse('admin:environments_room_delete', args=[obj.pk])
        return format_html('<a class="button" style="background-color: #ba2121; color: white; padding: 4px 8px; border-radius: 4px;" href="{}">Deletar</a>', url)
    delete_button.short_description = 'Deletar'