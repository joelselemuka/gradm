from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification
def notify(*,recipient,level,title,message,target_url=""):
    notice=Notification.objects.create(recipient=recipient,level=level,title=title,message=message,target_url=target_url or "")
    channel_layer=get_channel_layer()
    if channel_layer: async_to_sync(channel_layer.group_send)(f"notifications_{recipient.pk}",{"type":"notification","payload":{"id":notice.pk,"level":level,"title":title,"message":message,"target_url":notice.target_url}})
    return notice
