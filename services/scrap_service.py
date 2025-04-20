from model.scrap_progress import ScrapProgress
from datetime import datetime

def save_scrap_progress(message, appid: int):
    record, _ = ScrapProgress.get_or_create(
        chat_id=message.peer_id.channel_id,
        api_id=appid
    )
    record.message_id = message.id
    record.update_datetime = datetime.now()
    record.save()
