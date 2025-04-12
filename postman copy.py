import os
import re
import random
import asyncio
from collections import defaultdict
from typing import List
from telethon import TelegramClient, events
from telethon.tl.types import (
    User,
    Message,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageService
)

# Load .env
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    load_dotenv()

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
session_name = f"{api_id}_session"

# Load forward targets from .env
targets_raw = os.getenv('FORWARD_TARGETS', '')
fallback_chat_ids = [int(x.strip()) for x in targets_raw.split(',') if x.strip().isdigit()]

client = TelegramClient(session_name, api_id, api_hash)
reset_event = asyncio.Event()

# Regex pattern for |forward|@chat_id
forward_pattern = re.compile(r'\|_forward_\|\@(\d+)')

async def fetch_recent_messages(dialog):
    messages = []
    async for msg in client.iter_messages(dialog.id, limit=30):
        if not isinstance(msg, MessageService):
            messages.append(msg)
    return messages

def separate_messages(messages: List[Message]):
    albums = defaultdict(list)
    solos = []
    for msg in messages:
        if msg.grouped_id:
            albums[msg.grouped_id].append(msg)
        else:
            solos.append(msg)
    return albums, solos

async def safe_delete_message(msg):
    try:
        await client.delete_messages(msg.chat_id, [msg.id], revoke=True)
        print(f"🧹 成功刪除訊息 {msg.id}（雙方）")
    except Exception as e:
        print(f"⚠️ 刪除訊息失敗 {msg.id}：{e}")

async def process_album_messages(album_groups, source_user: str = "未知"):
    for group_id, messages in album_groups.items():
        caption = messages[0].message or ""
        match = forward_pattern.search(caption)
        if match:
            target_chat_id = int(match.group(1))
        elif fallback_chat_ids:
            target_chat_id = random.choice(fallback_chat_ids)
            print(f"🌟 無轉發標記，相簿改轉發至 chat_id={target_chat_id}")
        else:
            print("⚠️ 無 chat_id 可用，跳過相簿")
            continue

        try:
            await client.forward_messages(
                entity=target_chat_id,
                messages=messages,
                from_peer=messages[0].peer_id
            )
            print(f"✅ 相簿轉發至 chat_id={target_chat_id}")
            for msg in messages:
                await safe_delete_message(msg)
        except Exception as e:
            try:
                chat = await client.get_entity(target_chat_id)
                title = getattr(chat, "title", getattr(chat, "username", "未知"))
            except Exception:
                title = "（無法取得）"
            print(f"⚠️ 相簿轉發失敗 chat_id={target_chat_id}, chat_title={title}，來源使用者={source_user}：{e}")

async def process_solo_messages(messages: List[Message], source_user: str = "未知"):
    for msg in messages:
        media = msg.media
        caption = msg.message or ""

        if isinstance(media, (MessageMediaPhoto, MessageMediaDocument)):
            match = forward_pattern.search(caption)
            if match:
                target_chat_id = int(match.group(1))
            elif fallback_chat_ids:
                target_chat_id = random.choice(fallback_chat_ids)
                print(f"🌟 無轉發標記，媒體改轉發至 chat_id={target_chat_id}")
            else:
                print("⚠️ 無 chat_id 可用，跳過訊息")
                continue

            try:
                await msg.forward_to(target_chat_id)
                print(f"✅ 媒體轉發至 chat_id={target_chat_id}")
                await safe_delete_message(msg)
                continue
            except Exception as e:
                try:
                    chat = await client.get_entity(target_chat_id)
                    title = getattr(chat, "title", getattr(chat, "username", "未知"))
                except Exception:
                    title = "（無法取得）"
                print(f"⚠️ 媒體轉發失敗 chat_id={target_chat_id}, chat_title={title}，來源使用者={source_user}：{e}")

        await safe_delete_message(msg)

async def process_private_messages(messages: List[Message], source_user: str = "未知"):
    album_groups, solo_msgs = separate_messages(messages)
    await process_album_messages(album_groups, source_user)
    await process_solo_messages(solo_msgs, source_user)

async def process_incoming_private_messages():
    print("\n🔍 處理最近 30 則私訊：")
    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, User):
            source_user = dialog.name or "未知"
            messages = await fetch_recent_messages(dialog)
            await process_private_messages(messages, source_user)
    print("------")

@client.on(events.NewMessage)
async def handle_new_message(event):
    sender = await event.get_sender()
    name = sender.username or sender.first_name or '未知'
    print(f"📩 來自 {name}：{event.text}")
    await process_private_messages([event.message], source_user=name)
    reset_event.set()

@client.on(events.Album)
async def handle_album(event):
    sender = await event.get_sender()
    name = sender.username or sender.first_name or '未知'
    print(f"📸 來自 {name} 的相簿，共 {len(event.messages)} 則")
    await process_private_messages(event.messages, source_user=name)
    reset_event.set()

async def idle_checker():
    while True:
        reset_event.clear()
        try:
            await asyncio.wait_for(reset_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            await process_incoming_private_messages()

async def run_with_timeout():
    try:
        await asyncio.wait_for(
            asyncio.gather(
                idle_checker(),
                client.run_until_disconnected()
            ),
            timeout=20 * 60
        )
    except asyncio.TimeoutError:
        print("\n⏰ 執行超過 20 分鐘，自動結束。")

async def main():
    await client.start()
    print("✅ 開始監聽中（執行時間上限 20 分鐘）")
    await run_with_timeout()

client.loop.run_until_complete(main())