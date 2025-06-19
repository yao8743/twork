#!/usr/bin/env python
# pylint: disable=unused-argument

import asyncio
import time
import os

# 加载环境变量
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    # load_dotenv(dotenv_path='.20100034.sungfong.env')
    load_dotenv(dotenv_path='.28817994.luzai.env')



import random
import re
import json
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import MessageMediaWebPage
from telethon.tl.types import InputMessagesFilterEmpty
from peewee import DoesNotExist

from model.scrap_progress import ScrapProgress
from model.scrap_config import ScrapConfig
from database import db

from handlers.HandlerBJIClass import HandlerBJIClass
from handlers.HandlerBJILiteClass import HandlerBJILiteClass
from handlers.HandlerNoAction import HandlerNoAction
from handlers.HandlerNoDelete import HandlernNoDeleteClass

from handlers.HandlerRelayClass import HandlerRelayClass

from handlers.HandlerPrivateMessageClass import HandlerPrivateMessageClass

from telethon import functions, types
from telethon.errors import RPCError, ChannelPrivateError
from telethon.tl.functions.photos import DeletePhotosRequest
from telethon.tl.types import InputPhoto
from telethon.tl.types import ChannelForbidden
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.account import UpdateUsernameRequest
from telethon.tl.functions.channels import InviteToChannelRequest, TogglePreHistoryHiddenRequest


# 配置参数
config = {
    'api_id': os.getenv('API_ID',''),
    'api_hash': os.getenv('API_HASH',''),
    'phone_number': os.getenv('PHONE_NUMBER',''),
    'setting_chat_id': int(os.getenv('SETTING_CHAT_ID') or 0),
    'setting_thread_id': int(os.getenv('SETTING_THREAD_ID') or 0),
    'setting' : os.getenv('CONFIGURATION', '')
}

SESSION_STRING  = os.getenv("USER_SESSION_STRING")

# print(f"⚠️ 配置參數：{config}", flush=True)




# 嘗試載入 JSON 並合併參數
try:
    setting_json = json.loads(config['setting'])
    if isinstance(setting_json, dict):
        config.update(setting_json)  # 將 JSON 鍵值對合併到 config 中
except Exception as e:
    print(f"⚠️ 無法解析 CONFIGURATION：{e}")

config['session_name'] = str(config['api_id']) + 'session_name'  # 确保 session_name 正确

# print(f"⚠️ 配置參數：{config}")
   
# 在模块顶部初始化全局缓存
local_scrap_progress = {}  # key = (chat_id, api_id), value = message_id

last_message_id = 0

# 黑名单缓存
blacklist_entity_ids = set()

# 初始化 Telegram 客户端


if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), config['api_id'], config['api_hash'])
    print("【Telethon】使用 StringSession 登录。",flush=True)
else:
    client = TelegramClient(config['session_name'], config['api_id'], config['api_hash'])



# 常量
MAX_PROCESS_TIME = 20 * 60  # 最大运行时间 20 分钟



async def join(invite_hash):
    from telethon.tl.functions.messages import ImportChatInviteRequest
    try:
        await client(ImportChatInviteRequest(invite_hash))
        print("已成功加入群组")
    except Exception as e:
        if 'InviteRequestSentError' in str(e):
            print("加入请求已发送，等待审批")
        else:
            print(f"失败-加入群组: {invite_hash} {e}")

async def safe_remove_forbidden(entity):
    # 用一个“假”的 InputPeerChannel，只要有 channel_id 就够了
    fake_peer = types.InputPeerChannel(entity.id, 0)
    try:
        # 直接调用底层的 messages.DeleteDialogRequest，
        # 它只会把对话从列表里删掉，不会退群。
        await client(functions.messages.DeleteDialogRequest(peer=fake_peer))
        print(f"✅ 本地删除对话（不会退群）：{entity.id}")
    except RPCError as e:
        print(f"⚠️ DeleteDialogRequest 失败：{e}")

async def leave_group(entity):
    from telethon.tl.types import InputPeerChannel

    try:
        fake_peer = InputPeerChannel(channel_id=entity.id, access_hash=0)
        await client.delete_dialog(fake_peer, revoke=True)
        print(f'✅ 已安全退出/删除频道: {getattr(entity, "title", entity.id)}')
    except Exception as e:
        print(f'❌ 删除失败: {e}')

async def open_chat_history(entity):
    try:
        result = await client(TogglePreHistoryHiddenRequest(
            channel=entity,
            enabled=False  # False = 允许新成员查看历史记录
        ))
        print(f'✅ 已开启历史记录可见: {result}')
    except Exception as e:
        print(f'❌ 操作失败: {e}')

async def delete_my_profile_photos(client):
    photos = await client.get_profile_photos('me')

    if not photos:
        print("你没有设置头像。")
        return

    input_photos = []
    for photo in photos:
        if hasattr(photo, 'id') and hasattr(photo, 'access_hash') and hasattr(photo, 'file_reference'):
            input_photos.append(InputPhoto(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference
            ))

    await client(DeletePhotosRequest(id=input_photos))
    print("头像已删除。")

async def update_my_name(client, first_name, last_name=''):
    await client(UpdateProfileRequest(first_name=first_name, last_name=last_name))
    print(f"已更新用户姓名为：{first_name} {last_name}")

async def update_username(client,username):
    try:
        await client(UpdateUsernameRequest(username))  # 设置空字符串即为移除
        print("用户名已成功变更。")
    except Exception as e:
        print(f"变更失败：{e}")

async def invite_bot(bot_username, entity):
# 获取 Bot 实体
    bot_entity = await client.get_entity(bot_username)
    # 邀请 Bot 到超级群
    try:
        await client.send_message(bot_username, '/start')
        await client.send_message(bot_username, 'Hello')
        await client(InviteToChannelRequest(
            channel=entity,
            users=[bot_entity]
        ))
        print(f'已邀请 @{bot_username} 进入本群')

        # 检查是否真的在群里
        participants = await client.get_participants(entity)
        if any(p.username and p.username.lower() == bot_username.lower() for p in participants):
            print(f'✅ 确认 @{bot_username} 已经加入')
        else:
            print(f'⚠️ @{bot_username} 似乎没有加入，可能已被踢出或受限')

    except Exception as e:
        print(f'邀请失败: {e}')

async def safe_delete_message(message):
    try:
        await client.delete_messages(message.chat_id, [message.id], revoke=True)
        print(f"🧹 成功刪除訊息A {message.id}（雙方）", flush=True)
    except Exception as e:
        print(f"⚠️ 刪除訊息失敗A {message.id}：{e}", flush=True)

async def keep_db_alive():
    if db.is_closed():
        db.connect()
    else:
        try:
            db.execute_sql('SELECT 1')
        except Exception as e:
            print(f"数据库连接保持错误: {e}")

async def send_completion_message(last_message_id):
    try:
        print(f"发送完成消息到 {config['setting_chat_id']} 线程 {config['setting_thread_id']}")
        if config['setting_chat_id'] == 0 or config['setting_thread_id'] == 0:
            print("未设置配置线程 ID，无法发送完成消息。")
            return
        async with client.conversation(config['setting_chat_id']) as conv:
            await conv.send_message('ok', reply_to=config['setting_thread_id'])
    except Exception as e:
        print("未设置配置线程 ID，无法发送完成消息。")
        pass

async def is_blacklisted(entity_id):
    global blacklist_entity_ids

    # ✅ 先查缓存
    if entity_id in blacklist_entity_ids:
        return True

    # ✅ 先尝试从 ScrapConfig 取黑名单
    try:
        record = ScrapConfig.get(
            (ScrapConfig.api_id == config['api_id']) &
            (ScrapConfig.title == 'BLACKLIST_IDS')
        )
        raw = record.value or ''
        
        ids = {int(x.strip()) for x in raw.split(',') if x.strip().isdigit()}
        blacklist_entity_ids.update(ids)  # 缓存

        return entity_id in blacklist_entity_ids
    except DoesNotExist:
        blacklist_entity_ids = set()
        # print("⚠️ scrap_config 中找不到 BLACKLIST_IDS")
        return False
    except Exception as e:
        print(f"⚠️ 加载黑名单失败: {e}")
        return False

async def get_max_source_message_id(source_chat_id):
    key = (source_chat_id, config['api_id'])
    if key in local_scrap_progress:
        return local_scrap_progress[key]

    try:
        record = ScrapProgress.select().where(
            (ScrapProgress.chat_id == source_chat_id) &
            (ScrapProgress.api_id == config['api_id'])
        ).order_by(ScrapProgress.update_datetime.desc()).limit(1).get()

        local_scrap_progress[key] = record.message_id
        return record.message_id

    except DoesNotExist:
        new_record = ScrapProgress.create(
            chat_id=source_chat_id,
            api_id=config['api_id'],
            message_id=0,
            update_datetime=datetime.now()
        )
        local_scrap_progress[key] = new_record.message_id
        return new_record.message_id

    except Exception as e:
        print(f"Error fetching max source_message_id: {e}")
        return None
        
async def save_scrap_progress(entity_id, message_id):
    key = (entity_id, config['api_id'])
    record = ScrapProgress.get_or_none(
        chat_id=entity_id,
        api_id=config['api_id'],
    )

    if record is None:
        # 不存在时新增
        ScrapProgress.create(
            chat_id=entity_id,
            api_id=config['api_id'],
            message_id=message_id,
            update_datetime=datetime.now()
        )
    elif message_id > record.message_id:
        # 存在且 message_id 更大时才更新
        record.message_id = message_id
        record.update_datetime = datetime.now()
        record.save()


    local_scrap_progress[key] = message_id  # ✅ 同步更新缓存

async def process_user_message(entity, message):

    botname = None

    if message.text:
        try:
            match = re.search(r'\|_kick_\|\s*(.*?)\s*(bot)', message.text, re.IGNORECASE)
            if match:
                botname = match.group(1) + match.group(2)
                await client.send_message(botname, "/start")
                await client.send_message(botname, "[~bot~]")
                await safe_delete_message(message)
                return
        except Exception as e:
                print(f"Error kicking bot: {e} {botname}", flush=True)


        try:
            #  |_ask_|4234@vampire666666666
            match = re.search(r'\|_ask_\|(\d+)@([-\w]+)', message.text, re.IGNORECASE)
            if match:
                # sort_content_id = match.group(1)
                # request_bot_name = match.group(2)
                send_msg = await client.send_message('@ztdthumb011bot', message.text)
                # 删除消息
                await safe_delete_message(send_msg)
                await safe_delete_message(message)
                return

        except Exception as e:
                print(f"Error kicking bot: {e} {botname}", flush=True)

        #  |_join_|QQCyh1N2sMU5ZGQ0

        try:
            inviteurl = None
            match2 = re.search(r'\|_join_\|(.*)', message.text, re.IGNORECASE)
            if match2:
                inviteurl = match2.group(1) 
                print(f"邀请链接: {inviteurl}")
                await join(inviteurl)    #Coniguration
                await safe_delete_message(message)
                return
        except Exception as e:
                print(f"Error livite: {e} {inviteurl}", flush=True)
   

    # # 打印来源
    # first_name = getattr(entity, "first_name", "") or ""
    # last_name = getattr(entity, "last_name", "") or ""
    # entity_title = f"{first_name} {last_name}".strip()
    # # print(f"[User] Message from {entity_title} ({self.entity.id}): {self.message.text}")
    # print(f"\r\n[User] Message from {entity_title} ({entity.id}): {message.id}")

    extra_data = {'app_id': config['api_id'],'config': config}

    # 如果 config 中 is_debug_enabled 有值, 且為 1, 則 pass
    if config.get('bypass_private_check') == 1:
        # print(f"⚠️ bypass_private_check: {config.get('bypass_private_check')}")
        return

    # 实现：根据 entity.id 映射到不同处理类
    class_map = {
        777000: HandlerNoAction,   # 替换为真实 entity.id 和处理类
        7521097665 : HandlernNoDeleteClass,   # 撸仔四号
    }

    handler_class = class_map.get(entity.id)
    if handler_class:
        handler = handler_class(client, entity, message, extra_data)
        handler.is_duplicate_allowed = True
        await handler.handle()
    else:
        
        handler = HandlerPrivateMessageClass(client, entity, message, extra_data)
        # handler = HandlerNoAction(client, entity, message, extra_data)
        handler.delete_after_process = True
        await handler.handle()
       
async def process_group_message(entity, message):
    
    extra_data = {'app_id': config['api_id']}


    # 检测是否是 |_init_|
    if message.text == '|_init_|':
        await invite_bot('luzai01bot', entity)  # 替换为实际的 Bot 用户名
        await invite_bot('luzai01man', entity)  # 替换为实际的 Bot 用户名
        await invite_bot('luzai03bot', entity)  # 替换为实际的 Bot 用户名
        await invite_bot('has_no_access_bot', entity)  # 替换为实际的 Bot 用户名
        await invite_bot('DeletedAcconutBot', entity)  # 替换为实际的 Bot 用户名
        await invite_bot('freebsd66bot', entity)  # 替换为实际的 Bot 用户名
        await safe_delete_message(message)
        await open_chat_history(entity)
        await client.send_message(entity.id, f"entity.id: {str(entity.id)}"  )
        await leave_group(entity)

        return
            
    # 实现：根据 entity.id 映射到不同处理类
    class_map = {
        2210941198: HandlerBJIClass,   # 替换为真实 entity.id 和处理类
        # 2210941198: HandlerBJILiteClass,   # 替换为真实 entity.id 和处理类
        2021604352: HandlerRelayClass,
        # 2030683460: HandlerNoAction,        #Configuration
       
    }

   
    # entity_title = getattr(entity, 'title', f"Unknown entity {entity.id}")
    # print(f"[Group-X] Message from {entity_title} ({entity.id}): {message.text}")
    

    handler_class = class_map.get(entity.id)
    if handler_class:

       

        handler = handler_class(client, entity, message, extra_data)
        handler.is_duplicate_allowed = True
        await handler.handle()


    else:
        pass

async def man_bot_loop():
    last_message_id = 0  # 提前定义，避免 UnboundLocalError
    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        # if entity.id != 2210941198:
        #     continue

        # —— 新增：如果是私密／被封禁的频道，直接跳过并加入黑名单
        if isinstance(entity, ChannelForbidden):
            print(f"⚠️ 检测到私密或被封禁频道({entity.id})，跳过处理")
            blacklist_entity_ids.add(entity.id)
            continue

        # ✅ 跳过黑名单
        if await is_blacklisted(entity.id):
            # print(f"🚫 已屏蔽 entity: {entity.id}，跳过处理")
            continue

        current_entiry_title = None
        entity_title = getattr(entity, 'title', None)
        if not entity_title:
            first_name = getattr(entity, 'first_name', '') or ''
            last_name = getattr(entity, 'last_name', '') or ''
            entity_title = f"{first_name} {last_name}".strip() or getattr(entity, 'title', f"Unknown entity {entity.id}")



        print(f"当前对话: {entity_title} ({entity.id})", flush=True)

        if dialog.unread_count >= 0:
            if dialog.is_user:
                
                 # 如果 config 中 is_debug_enabled 有值, 且為 1, 則 pass
                if config.get('bypass_private_check') == 1:
                    # print(f"⚠️ bypass_private_check: {config.get('bypass_private_check')}")
                    return


                current_message = None
                max_message_id = await get_max_source_message_id(entity.id)
                if max_message_id is None:
                    continue
                min_id = max_message_id if max_message_id else 1
                async for message in client.iter_messages(
                    entity, min_id=min_id, limit=30, reverse=True, filter=InputMessagesFilterEmpty()
                ):
                    current_message = message
                    if current_entiry_title != entity_title:
                        print(f"User: {current_message.id} 来自: {entity_title} ({entity.id})", flush=True)
                        current_entiry_title = entity_title

                    await process_user_message(entity, message)

                if current_message:
                    await save_scrap_progress(entity.id, current_message.id)

                
                last_message_id = current_message.id if current_message else 0
                
                
            else:
                
                current_message = None
                max_message_id = await get_max_source_message_id(entity.id)
                if max_message_id is None:
                    continue
                min_id = max_message_id if max_message_id else 1

                try:
                    async for message in client.iter_messages(
                        entity, min_id=min_id, limit=500, reverse=True, filter=InputMessagesFilterEmpty()
                    ):
                        
                        if message.sticker:
                            continue
                        current_message = message
                        if current_entiry_title != entity_title:
                            print(f"Group: {current_message.id} 来自: {entity_title} ({entity.id})", flush=True)
                            current_entiry_title = entity_title


                        # print(f"当前消息ID(G): {current_message.id}")
                        await process_group_message(entity, message)
                except ChannelPrivateError as e:
                    print(f"❌ 无法访问频道：{e}")
                    await safe_remove_forbidden(entity)
                except Exception as e:
                    print(f"{e}", flush=True)
                    # print(f"{message}", flush=True)



              
                if current_message:
                    await save_scrap_progress(entity.id, current_message.id)
                    return last_message_id
    return last_message_id

async def main():
    await client.start(config['phone_number'])
    await keep_db_alive()

    me = await client.get_me()

       
    if config.get('is_debug_enabled') == 1:
        print(f'你的用户名: {me.username}',flush=True)
        print(f'你的ID: {me.id}')
        print(f'你的名字: {me.first_name} {me.last_name or ""}')
        print(f'是否是Bot: {me.bot}',flush=True)

    intbotname = '@Qing001bot'
    await client.send_message(intbotname, "/start")
    await client.send_message(intbotname, "[~bot~]")

    # await client.send_message('@nezhamowan1', "/start")
    
    # exit()

    # await

    # group_identifier = -1002592636499
    # participants = await client.get_participants(group_identifier)

    # # 遍历输出用户名和 ID
    # for user in participants:
    #     sql = f"INSERT INTO pure (user_id, done) VALUES ({user.id}, 0);"
    #     print(sql)
    #     db.execute_sql(sql)
    #     # 插入数据库 INSERT INTO `pure` (`user_id`, `done`) VALUES ('user.id', '0');


    # exit()
    # await delete_my_profile_photos(client)
    # await update_my_name(client,'Luzai', 'Man')
    # await update_username(client,"luzai02man")
    # exit()
    # await join("fRCAnbinkG1hYjU0")  #封面备份群   2086579883  #setting: thumb, func: handle_bid(update_thumb_info_by_send_photo), get_thumb
    # await join("6gAolpGeQq8wYmM0")  #封面图中转站 2134630453  Relay #setting: photo_relay , func: process_update_sora_thumb_info,push_notification_action

    

    #01 DIE 6874    2017145941  await join("") 22329346  / 20100034 ( Die )
    #02 OK  7258    2091886937  
    # await join("fTMvarjGSckxZmI8") 

    #03 DIE 7275    2063167161  await join("")                 22329346   / 20100034 ( Die ? )
    #04 DIE 7287    2108982395  await join("cr_hRjB_dRtkODdk") 20100034 (Die)
    #05 DIE 6376    1997235289  await join("")                 20100034 ( Die ? )
    #06 OK  6659    2000730581  
    # await join("li2wwjC6vEc5Mzdk") #22329346   / 20100034

    #07 DIE 7350    2145325974  await join("")                 20100034
    #08 DIE 5891    2062860209  await join("")                 20100034 (?)
    #09 DIE 7338    2015918658  await join("")                 20100034
    
    #10 OK  06315   2047726819  
    # await join("QQCyh1N2sMU5ZGQ0") #shunfeng807
    
    #11 OK  06393   2003243227  
    # await join("3eDZvSPvkVgyNmY0") #@shunfeng807
    
    #12 OK  #6463   1843229948  
    # await join("MyiRfuLls-U0Zjk0") 

    #13 DIE 7246    2021739085  
    # await join("XkHrmdZd-u80M2I0")
    
    #14 DIE 6234                await join("")
    
    #15 OK  6553    2061165152  
    # await join("xCcAV1mgMCs1ZDE8")


    # 2091886937,2000730581,2047726819,2003243227,1843229948,2061165152
    # |_join_|fTMvarjGSckxZmI8
    # |_join_|li2wwjC6vEc5Mzdk
    # |_join_|QQCyh1N2sMU5ZGQ0
    # |_join_|3eDZvSPvkVgyNmY0
    # |_join_|MyiRfuLls-U0Zjk0
    # |_join_|xCcAV1mgMCs1ZDE8


   
   
    # await join("y6blcEsK-P01MmJl")  # FILEDEPOT_FORWARD_CHAT_ID ,2132486952
    # exit()
  
  
    # await join("xbY8S-04jnEzYWE0")   
    
    
    start_time = time.time()
    # 显示现在时间
    now = datetime.now()
    print(f"Current: {now.strftime('%Y-%m-%d %H:%M:%S')}",flush=True)

    while (time.time() - start_time) < MAX_PROCESS_TIME:
        try:
            last_message_id = await asyncio.wait_for(man_bot_loop(), timeout=600)  # 5分钟超时
        except asyncio.TimeoutError:
            print("⚠️ 任务超时，跳过本轮", flush=True)
        # await asyncio.sleep(random.randint(5, 10))
       

    await send_completion_message(last_message_id)

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())


