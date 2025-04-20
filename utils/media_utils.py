import imagehash
from PIL import Image as PILImage
import json
import os
from telethon.errors import ChatForwardsRestrictedError

from datetime import datetime


async def get_image_hash(image_path: str) -> str:
    img = PILImage.open(image_path)
    return str(imagehash.phash(img))

async def safe_forward_or_send(client, message_id, from_chat_id, to_chat_id, material, caption_json: str, to_protect_chat_id=None):
    try:
        if to_protect_chat_id is None:
            to_protect_chat_id = to_chat_id

        if isinstance(material, list):
            print(f"📤 发送 Album，共 {len(material)} 个媒体")
        else:
            print("📤 发送单个媒体")

        await client.send_file(
            to_chat_id,
            material,
            disable_notification=False,
            parse_mode='html',
            caption=caption_json
        )
        print("✅ 成功转发消息！")
    except ChatForwardsRestrictedError:
        print(f"⚠️ 该消息禁止转发，尝试重新发送...{message_id}")
        await fetch_and_send(client, from_chat_id, message_id, to_protect_chat_id, material, caption_json)



async def fetch_and_send(client, from_chat_id, message_id, to_chat_id, material, caption_json: str):
    new_material = []
    message_single = await client.get_messages(from_chat_id, ids=message_id)

    DOWNLOAD_DIR = "./media/"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    def generate_filename(message, index=None):
        if message.document and message.document.attributes:
            for attr in message.document.attributes:
                if hasattr(attr, "file_name"):
                    return attr.file_name  # 使用原始文件名
        base = message.file.unique_id if message.file else f"file_{datetime.now().timestamp()}"
        suffix = f"_{index}" if index is not None else ""
        ext = message.file.ext if message.file and message.file.ext else ".bin"
        return f"{base}{suffix}{ext}"

    if isinstance(material, list):
        for idx, message in enumerate(material):
            if message.media:
                filename = generate_filename(message, idx)
                file_path = os.path.join(DOWNLOAD_DIR, filename)
                await message.download_media(file=file_path)
                new_material.append(file_path)
    elif message_single.media:
        filename = generate_filename(message_single)
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        await message_single.download_media(file=file_path)
        new_material = file_path

    if new_material:
        parsed_json = json.loads(caption_json)
        parsed_json["protect"] = "1"
        if "闪照模式5秒后此消息自动销毁" in parsed_json:
            parsed_json["flash"] = "1"
        caption_json2 = json.dumps(parsed_json, ensure_ascii=False, indent=4)

        await client.send_file(
            to_chat_id,
            new_material,
            disable_notification=False,
            parse_mode='html',
            caption=caption_json2
        )
        print("✅ 重新发送成功！")
    else:
        print("❌ 无法发送，未找到可用媒体")
