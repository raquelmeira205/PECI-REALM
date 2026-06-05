import json
from channels.generic.websocket import AsyncWebsocketConsumer

class RadarConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_name}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def radar_message(self, event):
        html_alert = f"""
            <div id="radar-status" hx-swap-oob="true" class="p-4 bg-emerald-900/30 border border-emerald-500 text-emerald-400 rounded-lg text-center">
                <p>✅ Radar detected successfully!</p>
            </div>
            <button id="btn-finish" hx-swap-oob="true" 
                    onclick="window.location.href='/dashboard/'"
                    class="w-full bg-emerald-600 text-white py-3 rounded-lg">
                Go to Dashboard
            </button>
        """
        await self.send(text_data=html_alert)

    async def sync_status(self, event):
        radar_sn = event['radar_sn']
        html = f"""
            <div id="sync-badge-{radar_sn}" hx-swap-oob="true"
                 class="px-2 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-300">
                NTP OK ✓
            </div>
        """
        await self.send(text_data=html)

from asgiref.sync import sync_to_async

class AvailableRadarsConsumer(AsyncWebsocketConsumer):
    """ Consumer to handle available radars """

    async def connect(self):
        print("Connecting to available radars")
        self.room_group_name = 'available_radars'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        # Enviar imediatamente os radares já detetados e que não têm sala
        await self.broadcast_available_radars()

    @sync_to_async
    def get_existing_radars(self):
        from django.apps import apps
        from django.utils import timezone
        from datetime import timedelta
        
        Radar = apps.get_model('sensors_devices', 'Radar')
        cutoff = timezone.now() - timedelta(seconds=15)
        # Buscar radares sem sala e ativos recentemente
        return list(Radar.objects.filter(room__isnull=True, last_seen__gte=cutoff))

    async def send_existing_radars(self):
        radars = await self.get_existing_radars()
        for r in radars:
            timestamp_str = r.last_seen.strftime('%H:%M:%S') if r.last_seen else "Desconhecido"
            # Simulamos a mensagem que seria recebida pelo radar_discovery
            await self.radar_discovery({
                'data': {
                    'network_id': r.network_id,
                    'timestamp': timestamp_str
                }
            })

    async def broadcast_available_radars(self):
        """ Fetch the current state from DB and render the FULL list to avoid duplicates """
        radars = await self.get_existing_radars()
        
        if not radars:
            html_content = """
                <div class="text-center p-6 text-slate-400 bg-slate-800/50 rounded-lg border border-slate-600">
                    A aguardar deteção de radares na rede...
                </div>
            """
        else:
            # Lista simples em coluna única
            html_content = '<div class="space-y-4">'
            
            for r in radars:
                html_content += f"""
                    <div class="bg-white border border-slate-300 rounded p-4">
                        <div class="mb-2">
                            <h3 class="font-bold">ID: {r.network_id}</h3>
                        </div>

                        <form hx-post="/api/radar-assign/" hx-target="#btn-container-{r.network_id}" hx-swap="innerHTML">
                            <input type="hidden" name="network_id" value="{r.network_id}">
                            
                            <div class="mb-3">
                                <label class="text-sm font-bold">
                                    <input type="checkbox" name="is_master" class="mr-2">
                                    Set as Primary (Master)
                                </label>
                            </div>

                            <div id="btn-container-{r.network_id}">
                                <button type="submit" class="w-full bg-emerald-700 text-white font-bold py-2 rounded">
                                    Add Device
                                </button>
                            </div>
                        </form>
                    </div>
                """
            html_content += '</div>'

        # Substitui todo o conteúdo do container
        html_block = f"""
            <div id="available-radar-list" hx-swap-oob="innerHTML">
                {html_content}
            </div>
        """
        await self.send(text_data=html_block)

    async def disconnect(self, close_code):
        print("Disconnecting from available radars")
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def radar_discovery(self, event):
        await self.broadcast_available_radars()

    
