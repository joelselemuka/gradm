from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not self.scope.get("user") or not self.scope["user"].is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = f"notifications_{self.scope['user'].pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification(self, event):
        await self.send_json(event["payload"])
