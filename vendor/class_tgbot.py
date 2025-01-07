import asyncio
import json
import re
import sys
import time
import traceback
from telethon import events,types,errors
from telegram import InputMediaDocument, InputMediaPhoto, InputMediaVideo
from telegram.constants import ParseMode, MessageEntityType
from telethon.errors import WorkerBusyTooLongRetryError
from telethon.tl.types import InputMessagesFilterEmpty, Message, User, Chat, Channel, MessageMediaWebPage
from collections import defaultdict
from peewee import PostgresqlDatabase, Model, CharField, BigIntegerField, CompositeKey, fn, AutoField 

#密文機器人

# # - 用戶轉資源,得到密文 ( get_code_from_resource )
# -- 用户传相册, 得到一个密文
# --- 机器人收到任何的资源都会写到DB
# -- 用户传单一文档,图,视频, 得到一个密文
# --- 机器人收到任何的资源都会写到DB
# -- 用户传网址, 得到一个密文


# - 密文转资源 ( get_resource_from_code )
# -- 密文转单一资源
# -- 密文转相册
# -- 密文转网址

# - 回馈机制
# -- 新用户读取密文, 上传者得到回馈
# --- 新用户存到db
# --- 回馈给谁? 密文要包括上传者


# - 防炸继承
# -- 收到密文先解析 
# --- 自己的密文 => 密文转资源
# --- 别人的密文 => 查询自己是否有 file_id
# ------ 若有则回覆 => 密文转资源
# ------ 没有, 确认 HW_BOT 有没有, 若有则让 HWBOT 传给 ManBOT => Pool , 出现 "正在同步资源中,请一小时后再试"

# - ManBOT
# -- ManBOT 只要收到私发的资源,就会传到 Pool  (ACT_BOT , WH_BOT, LY_BK_BOT)
# -- ManBOT 不会传给个人,机器人,只会传到 Pool

# - ACT_BOT / WH_BOT
# -- BOT 不会转传任何群 (包括 Pool) 的资源, 但会吸收进数据库
# -- 机器人收到任何的资源都会写到DB
# -- BOT 只会私发资源,不会发在群组, 但会转给 ManBOT => Pool  (ACT_BOT , WH_BOT, LY_BK_BOT)

             

class lybot:
    def __init__(self,db):
        self.albums = defaultdict(list)
        self.album_tasks = {}
        self.setting = {}
        self.ALBUM_TIMEOUT = 0.5
        self.MAX_PROCESS_TIME = 2400

        class BaseModel(Model):
            class Meta:
                database = db

        self.BaseModel = BaseModel

        class FileInfo(BaseModel):
            file_unique_id = CharField(max_length=50)
            file_id = CharField(max_length=100, primary_key=True,unique=True)
            file_type = CharField(max_length=10, null=True)
            bot_name = CharField(max_length=50)

        class MediaGroup(BaseModel):
            id = AutoField()  # 自动主键字段
            media_group_id = BigIntegerField()
            file_id = CharField(max_length=100)
            file_type = CharField(max_length=10, null=True)

        class ShowFiles(BaseModel):
            enc_str = CharField(max_length=100, primary_key=True, unique=True)

        class User(BaseModel):
            user_id = BigIntegerField(primary_key=True)
            first_name = CharField(max_length=50, null=True)
            last_name = CharField(max_length=50, null=True)
            username = CharField(max_length=50, null=True)

            class Meta:
                constraints = [
                    # 添加无符号约束
                    'CHECK(user_id >= 0)'
                ]

        self.FileInfo = FileInfo
        self.MediaGroup = MediaGroup
        self.ShowFiles = ShowFiles
        self.User = User

    def convert_base(self, value, from_base, to_base):
   
        # Converts a number from one base to another using a custom character set.

        # Args:
        #     value (str or int): The value to convert. Can be a string for non-decimal bases.
        #     from_base (int): The base of the input value. Must be between 2 and 157.
        #     to_base (int): The base to convert to. Must be between 2 and 157.

        # Returns:
        #     str: The value converted to the target base.
   
        # Define the 157-character set
        charset = (
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
            "¡¢£¤¥¦¨©ª¬®¯°±²³´µ¶·¸¹º¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ"
        )

        # 检查 base 是否在有效范围内
        max_base = len(charset)
        if not (2 <= from_base <= max_base and 2 <= to_base <= max_base):
            raise ValueError(f"Bases must be between 2 and {max_base}.")

        # Step 1: Convert the input value to decimal
        decimal_value = 0
        if isinstance(value, str):
            for char in value:
                if char not in charset[:from_base]:
                    raise ValueError(f"Invalid character '{char}' for base {from_base}.")
                decimal_value = decimal_value * from_base + charset.index(char)
        else:
            decimal_value = int(value)

        # Step 2: Convert the decimal value to the target base
        if decimal_value == 0:
            return charset[0]

        result = []
        while decimal_value > 0:
            result.append(charset[decimal_value % to_base])
            decimal_value //= to_base

        return ''.join(reversed(result)) 
    
    # 密文格式: [type]_didipanbot_[file_unique_id]§[file_id]§[bot_name]§[send_id];
    # 传入字符串 file_unique_id, file_id, bot_name, sender_id, type ,会返回一个字符串, 该字符串的格式是上面的格式,并份字串会以§分隔
    # sender_id 可以为空, 为空时, 会自动填充为 0
    async def encode(self, file_unique_id, file_id, bot_name, file_type,sender_id=None):
         # 如果 sender_id 为空，则默认为 "0"
        sender_id = sender_id or "0"

        file_unique_id_enc = self.convert_base(file_unique_id, 64, 155)
        
        file_id_enc = self.convert_base(file_id, 64, 155)
        
        bot_name_enc = self.convert_base(bot_name, 64, 155)
        sender_id_enc = self.convert_base(sender_id, 10, 155)
        file_type_enc = file_type
        return f"{file_type_enc}_didipanbot_{file_unique_id_enc}§{file_id_enc}§{bot_name_enc}§{sender_id_enc}§"
  
    async def encode_message(self, message):
        # Encodes a Telegram message into a string that can be decoded back into its original components.

        # Args:
        #     message (telegram.Message): The message to encode.

        # Returns:
        #     str: The encoded string. Format:
        #          [type]_didipanbot_[file_unique_id]§[file_id]§[bot_name]§[send_id]§

        # Raises:
        #     ValueError: If the message is not a supported type.
        
        if hasattr(message, 'media_group_id') and message.media_group_id:
            file_id = ''
            file_unique_id = message.media_group_id
            file_type = 'a'
        elif message.photo:
            file_id = message.photo[-1].file_id
            file_unique_id = message.photo[-1].file_unique_id
            file_type = 'p'
        elif message.video:
            file_id = message.video.file_id
            file_unique_id = message.video.file_unique_id
            file_type = 'v'
        elif message.document:
            file_id = message.document.file_id
            file_unique_id = message.document.file_unique_id
            file_type = 'd'
        else:
            raise ValueError("Unsupported message type.")

        bot_name = self.bot_username
        sender_id = message.from_user.id

        return await self.encode(file_unique_id, file_id, bot_name, file_type, sender_id)

    
    def decode(self, encoded_str):
        
        # Decodes a string generated by the encode method back into its original components.

        # Args:
        #     encoded_str (str): The encoded string to decode. Format:
        #                       [type]_didipanbot_[file_unique_id]§[file_id]§[bot_name]§[send_id]§

        # Returns:
        #     dict: A dictionary containing the decoded components:
        #           - file_unique_id
        #           - file_id
        #           - bot_name
        #           - sender_id
        #           - file_type

        # Raises:
        #     ValueError: If the encoded string is not in the expected format.
        
        try:
            # Split the encoded string into the main type and the rest
            type_part, data_part = encoded_str.split('_didipanbot_', 1)
            components = data_part.split('§')
           
            if len(components) != 5:
                raise ValueError("Invalid encoded string format.")

            file_unique_id_enc, file_id_enc, bot_name_enc, sender_id_enc, tail = components

            # Decode each component
            file_unique_id = self.convert_base(file_unique_id_enc, 155, 64)
            file_id = self.convert_base(file_id_enc, 155, 64)
            bot_name = self.convert_base(bot_name_enc, 155, 64)
            sender_id = self.convert_base(sender_id_enc, 155, 10)
            file_type = type_part

            return {
                "file_unique_id": file_unique_id,
                "file_id": file_id,
                "bot_name": bot_name,
                "sender_id": sender_id,
                "file_type": file_type
            }

        except (ValueError, IndexError) as e:
            raise ValueError(f"Failed to decode the string: {e}, {encoded_str}")   

    #寫一個函數, 用來判斷給出的字符串是否是加密字符串
    def find_encode_code(self, text):
       
        # 允许的字符集
        # allowed_chars = r"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz\-_¡¢£¤¥¦¨©ª¬®¯°±²³´µ¶·¸¹º¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ"
        # pattern = fr"^[pvdau]_didipanbot_[{allowed_chars}]*§[{allowed_chars}]*§[{allowed_chars}]*§[{allowed_chars}]*§$"

        # 构造正则表达式
        pattern = r"^[pvdau]_didipanbot_[^\s]*§[^\s]*§[^\s]*§[^\s]*§$"
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        return matches


    async def set_man_bot_info(self, client):
        me = await client.get_me()
        self.config['man_bot_id'] = me.id
        # print(f"User ID: {me.id}")
        # print(f"Username: {me.username}")
        # print(f"Phone: {me.phone}")

    async def set_bot_info(self, application):
        # 获取机器人信息并设置 tgbot.bot_username
        bot_info = await application.bot.get_me()
        self.bot_username = bot_info.username
        self.bot_id = bot_info.id
        self.bot_name = bot_info.first_name
       

    def extract_entity_from_message(self, message, entity_type=None):
        """
        从 Telegram 消息中提取指定类型的实体。

        Args:
            message (telegram.Message): Telegram 消息对象。
            entity_type (str, optional): 要提取的实体类型。如果为 None，则提取所有实体。

        Returns:
            list: 包含消息中所有指定类型实体的列表。如果没有找到，则返回空列表。
        """
        entities = []

        # 检查消息中的实体
        if message.entities:
            for entity in message.entities:
                if entity_type is None or entity.type == entity_type:
                    start = entity.offset
                    end = entity.offset + entity.length
                    entities.append(message.text[start:end])

        # 如果类型是 URL 并且没有在实体中找到，用正则表达式作为备选
        if entity_type == MessageEntityType.URL and not entities:
            url_pattern = re.compile(
                r'(?:(?:https?|ftp):\/\/)'  # 协议部分
                r'[\w/\-?=%.]+\.[\w/\-?=%.]+',  # 域名部分
                re.IGNORECASE
            )
            entities = re.findall(url_pattern, message.text or "")

        return entities

   
    # 错误处理器
    async def error_handler(self, update, context):
        error_message = (
            f"An error occurred:\n"
            f"Update: {update}\n"
            f"Error: {context.error}\n"
        )

        # 获取异常信息
        exc_type, exc_obj, exc_tb = sys.exc_info()
        if exc_tb is not None:
            # 提取异常发生的行号
            line_number = exc_tb.tb_lineno
            # 将行号添加到错误信息
            error_message += f"Error occurred on line: {line_number}\n"
        
        # 记录错误信息到日志
        self.logger.error(error_message, exc_info=True)

        



    async def handle_bot_message(self,update, context) -> None:
        

        # 使用类内方法提取 URL
        urls = self.extract_entity_from_message(update.message, MessageEntityType.URL)
        if urls:

            bot_name = self.bot_username
            sender_id = update.message.from_user.id
            file_type = 'u'
            for url in urls:
                #检查 url 的开头是否为 https://t.me/+ 或 https://t.me/joinchat/ , 若不是则跳过
                if not url.startswith("https://t.me/+") and not url.startswith("https://t.me/joinchat/"):
                    continue
                # 将字符中的 https://t.me/+ 或 https://t.me/joinchat/ 替换为空
                file_id_url = url.replace("https://t.me/+", "").replace("https://t.me/joinchat/", "")
                url_word = await self.encode(file_id_url,"0", bot_name, file_type, sender_id)
                #回覆指定的 update.message.message_id消息
               
                await context.bot.send_message(
                    chat_id=update.message.chat.id,
                    reply_to_message_id=update.message.message_id,
                    text=f"<code>{url_word}</code>",
                    parse_mode=ParseMode.HTML
                )
               
                self.logger.info(f"Detected URL: {url_word}")
               
            
            return


        # print(f"Received message: {update.message}", flush=True)
        if hasattr(update.message, 'media_group_id') and update.message.media_group_id:
            media_group_id = update.message.media_group_id

            # 添加消息到 Album
            self.albums[media_group_id].append(update.message)

            # 如果已有任务，取消旧任务
            if media_group_id in self.album_tasks:
                self.album_tasks[media_group_id].cancel()

            # 创建新的定时任务
            self.album_tasks[media_group_id] = asyncio.create_task(self.handle_album_completion(media_group_id,context))

            # print(f"Media Group ID: {media_group_id}, Photos in Album: {len(self.albums[media_group_id])}")

            # print(f"[B]media_group_id message received {update.message.media_group_id}", flush=True)
        elif update.message.photo or update.message.video or update.message.document:
            self.logger.info(f"{self.bot_username}-[B]Video message received")
            # print(f"{self.bot_username}-[B]Video message received", flush=True)
            await self.upsert_file_info(update.message)
            
            # 如果不是私聊的内容，则停止
            if update.message.chat.type not in ['private']:
                return
                
            # 转发消息
            await context.bot.forward_message(
                chat_id=self.config['man_bot_id'],
                from_chat_id=update.message.chat.id,
                message_id=update.message.message_id
            )

            reply_code = await self.encode_message(update.message)
            reply_message = f"Send to @{self.bot_username} to fetch content\r\n\r\n<code>{reply_code}</code>"
            res = await context.bot.send_message(
                chat_id=update.message.chat.id,
                reply_to_message_id=update.message.message_id,
                text=reply_message,
                parse_mode=ParseMode.HTML
            )

            # print(f"Reply message: {res.message_id}", flush=True)

            await context.bot.send_message(
                chat_id=update.message.chat.id,
                reply_to_message_id=res.message_id,
                text="👆🏻 Share the code in groups; new users using it earn you extra rewards. \r\n分享代码到群，新用户使用可得额外奖励。",
                parse_mode=ParseMode.HTML
            )

                
            
            
        elif update.message.text:
            # 检查是否为私信
            if update.message.chat.type not in ['private']:
                return
            
            # # -- 收到密文先解析 
            # --- 自己的密文 => 密文转资源
            # --- 别人的密文 => 查询自己是否有 file_id
            # ------ 若有则回覆 => 密文转资源
            # ------ 没有, 确认 HW_BOT 有没有, 若有则让 HWBOT 传给 ManBOT => Pool , 出现 "正在同步资源中,请一小时后再试"
            # print("[B]Text message received", flush=True)
            # 检查是否为加密字符串
            
            encode_code_list = self.find_encode_code(update.message.text)
            # print(f"Found {len(encode_code_list)} encode codes in the message.")
            if encode_code_list:
                for encode_code in encode_code_list:
                    try:
                        
                        reply_to_message_id = update.message.message_id
                        chat_id = update.message.chat_id
                        decode_row = self.decode(encode_code)

                        if decode_row['bot_name'] == self.bot_username:
                            
                            # 密文转资源
                            await self.send_material_by_row(decode_row,context,reply_to_message_id,chat_id)
                            await self.referral_reward(decode_row,context,chat_id)
                        else:
                            # --- 别人的密文 => 查询自己是否有 file_id
                            # ------ 若有则回覆 => 密文转资源
                            # ------ 没有, 确认 HW_BOT 有没有, 若有则让 HWBOT 传给 ManBOT => Pool , 出现 "正在同步资源中,请一小时后再试"
                            if decode_row['file_type'] == 'a':
                                await context.send_message(
                                    chat_id=update.message.chat_id,
                                    text="Album syncing, please try again in an hour. 相册同步中，请一小时后再试。"
                                )
                                return
                            else:
                                try:
                                    # 尝试获取记录
                                    rows = self.FileInfo.select().where(self.FileInfo.file_unique_id == decode_row['file_unique_id'])
                                    dyer_dict = None
                                    for fileInfoRow in rows:
                                        if fileInfoRow.bot_name == self.dyer_bot_username:
                                            dyer_dict = dict(
                                                file_unique_id=fileInfoRow.file_unique_id, 
                                                file_id=fileInfoRow.file_id,
                                                bot_name=fileInfoRow.bot_name,
                                                file_type=fileInfoRow.file_type
                                                )
                                        elif fileInfoRow.bot_name == self.bot_username:
                                            # print(f"=>Found - {fileInfoRow} ")
                                            #展示fileInfoRow的资料型态
                                            # print(type(fileInfoRow))
                                            
                                            new_dict = dict(
                                                file_unique_id=fileInfoRow.file_unique_id, 
                                                file_id=fileInfoRow.file_id,
                                                bot_name=fileInfoRow.bot_name,
                                                file_type=fileInfoRow.file_type
                                                )

                                            return await self.send_material_by_row(new_dict,context,reply_to_message_id,chat_id)
                                    
                                    if dyer_dict:
                                        await context.bot.send_message(  
                                            chat_id=update.message.chat_id,
                                            reply_to_message_id=update.message.message_id,
                                            text="Old data restoring, please try again in an hour. 旧数复原中，请一小时后再试。"
                                        )
                                        

                                        await self.send_material_by_row(dyer_dict,self.dyer_application ,0, self.config['man_bot_id']) 
                                        # await self.send_material_by_row(dyer_dict,context,reply_to_message_id,chat_id)
                                    else:
                                        await context.bot.send_message(
                                            chat_id=update.message.chat_id,
                                            reply_to_message_id=update.message.message_id,
                                            text="Code invalid or expired. 代码错误或已过期。"
                                        )
                                       
                                    return None
                                except self.FileInfo.DoesNotExist:
                                    # 如果未找到，返回 None
                                    print(f"Not Found2")  
                                    return None
                                # 查询是否存在 file_id
                               
                            
                            
                    except ValueError as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        line_number = exc_tb.tb_lineno
                        self.logger.error(f"An exception occurred on line {line_number}: {e}")
                        # print(f"Failed to decode message: {e}")
        else:
            await update.message.reply_text(update.message.text)

    async def referral_reward(self,decode_row,context,user_id):
        # 如果 decode_row['sender_id'] 无值或等于 0，则返回
        if decode_row['sender_id'] == "0":
            return

        # - 回馈机制
        # -- 新用户读取密文, 上传者得到回馈
        # --- 新用户存到db
        # --- 回馈给谁? 密文要包括上传者
        # 从数据库检查 chat_id 是否存在于 User 表中,若存在则返回 false, 否则就对 decode_row['sender_id'] 进行奖励
        try:
            user = self.User.get(self.User.user_id == user_id)
            return False
        except self.User.DoesNotExist:
            self.User.create(user_id=user_id)
            #从数据表 showfiles 随机取5条数据,每条都断行,汇整成一个信息，再传送给 decode_row['sender_id']
            # 从数据库中随机取5条记录
            records = self.ShowFiles.select().order_by(fn.Random()).limit(5)
            # 汇总记录
            message_text = "New member joined via you; earned codes.\r\n新群友因你加入，获密文奖励。\r\n\r\n"
            for record in records:
                message_text += f"{record.enc_str}\r\n"
            # 发送消息
            await context.bot.send_message(
                chat_id=decode_row['sender_id'],
                text=message_text,
                parse_mode="HTML"
            )
            # 发送奖励
            user_first_name = ""
            try:
                user = context.bot.get_chat(chat_id=decode_row['sender_id'])
                user_first_name = user.first_name
            except Exception as e:
                self.logger.error(f"Failed to get user info: {e}")

            

            # 发送消息到中文群
            await context.bot.send_message(
                chat_id=-1002086803190,
                text=f"群友{user_first_name}分享了他的代码到<u>其他友群</u>，轻松领取了额外的五个珍贵资源！机会难得，你也赶快试试吧！",
                parse_mode="HTML"
            )

            

            # 发送消息到外文群
            english_message_text = "New member joined via you; earned codes.\r\n\r\n"
            await context.bot.send_message(
                chat_id=-1002138063591,
                text=f"Our group member, {user_first_name}, shared his code with <u>other groups</u> and easily earned five extra valuable resources! Don't miss out—give it a try now!",
                parse_mode="HTML"
            )

            
            return
        


    async def send_material_by_row(self,decode_row,context,reply_to_message_id,chat_id):
        #显示decode_row的资料型态
        # print((decode_row))
  
    
        encode_code = await self.encode(decode_row['file_unique_id'], decode_row['file_id'], decode_row['bot_name'], decode_row['file_type'])
        reply_message = f"Send to @{self.bot_username} to fetch content\r\n\r\n<code>{encode_code}</code>"
        
        # 暫停1秒
        await asyncio.sleep(1)  


        # 密文转资源
        if decode_row['file_type'] == 'u' or decode_row['file_type'] == 'url':
            print(f"URL: {decode_row['file_unique_id']}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"https://t.me/joinchat/{decode_row['file_unique_id']}",
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.HTML
            )
        elif decode_row['file_type'] == 'p' or decode_row['file_type'] == 'photo':
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=decode_row['file_id'],
                caption=reply_message,
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.HTML
            )
        elif decode_row['file_type'] == 'v' or decode_row['file_type'] == 'video':
            await context.bot.send_video(
                chat_id=chat_id,
                video=decode_row['file_id'],
                caption=reply_message,
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.HTML
            )
        elif decode_row['file_type'] == 'd' or decode_row['file_type'] == 'document':
            await context.bot.send_document(
                chat_id=chat_id,
                document=decode_row['file_id'],
                caption=reply_message,
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.HTML
            )
        elif decode_row['file_type'] == 'a' or decode_row['file_type'] == 'album':

            records = self.MediaGroup.select().where(self.MediaGroup.media_group_id == decode_row['file_unique_id'])
            
            media = []

            # 遍历记录，根据 file_type 动态生成对应的 InputMedia 对象
            for record in records:
                if record.file_type == "photo":
                    media.append(InputMediaPhoto(media=record.file_id,caption=reply_message,parse_mode=ParseMode.HTML))
                elif record.file_type == "video":
                    media.append(InputMediaVideo(media=record.file_id,caption=reply_message,parse_mode=ParseMode.HTML))
                elif record.file_type == "document":
                    media.append(InputMediaDocument(media=record.file_id,caption=reply_message,parse_mode=ParseMode.HTML))
                else:
                    print(f"未知的文件类型: {record.file_type}")
            
            # 发送相册
            await context.bot.send_media_group(
                chat_id=chat_id,
                media=media,
                reply_to_message_id=reply_to_message_id
            )
        # await self.get_resource_from_code(update, decode_dict)
    


    async def handle_album_completion(self,media_group_id: str, context) -> None:
        try:
            # 等待超时时间
            await asyncio.sleep(self.ALBUM_TIMEOUT)
            
            # 处理 Album 完成逻辑
            album_set = self.albums.pop(media_group_id, [])
            self.album_tasks.pop(media_group_id, None)

            # 轮询album_set
            first_message = album_set[0]
            for message in album_set:
                await self.upsert_file_info(message)
                await self.insert_media_group(message)
                await message.forward(chat_id=self.config['man_bot_id'])
                # print(f"Album {media_group_id} contains message: {message.message_id}")
                # print(f"Album {media_group_id} contains message: {message}")
            
            reply_code = await self.encode_message(first_message)
            reply_message = f"Send to @{self.bot_username} to fetch content\r\n\r\n<code>{reply_code}</code>"
            await context.bot.send_message(
                chat_id=first_message.chat.id,
                reply_to_message_id=first_message.message_id,
                text=reply_message,
                parse_mode=ParseMode.HTML
            )


            
            self.logger.info(f"Album {media_group_id} 完成，包含 {len(album_set)} 张照片")

            # 这里可以添加保存或处理 Album 的逻辑
        except asyncio.CancelledError:
            # 如果任务被取消，不做任何操作
            self.logger.debug(f"Album {media_group_id} 处理超时，已取消")
            
            pass
    
    async def upsert_file_info(self,message):
        try:
            
            if message.video:
                file_id = message.video.file_id
                file_unique_id = message.video.file_unique_id
                file_type = 'video'
            elif message.document:
                file_id = message.document.file_id
                file_unique_id = message.document.file_unique_id
                file_type = 'document'    
            elif message.photo:
                file_id = message.photo[-1].file_id
                file_unique_id = message.photo[-1].file_unique_id
                file_type = 'photo'


            
            bot_name = self.bot_username
            
            # 尝试更新
            file_info = self.FileInfo.get(self.FileInfo.file_unique_id == file_unique_id, self.FileInfo.bot_name == bot_name)
            file_info.file_id = file_id
            file_info.file_type = file_type
            file_info.save()
        except self.FileInfo.DoesNotExist:
            # 如果不存在则创建
            self.FileInfo.create(file_unique_id=file_unique_id, bot_name=bot_name, file_id=file_id, file_type=file_type)
        except Exception as e:
            print(f"Error upserting file info: {e}")
            traceback.print_exc()
        
    async def insert_media_group(self, message):
        media_group_id = message.media_group_id
        if message.video:
            file_id = message.video.file_id
            file_unique_id = message.video.file_unique_id
            file_type = 'video'
        elif message.document:
            file_id = message.document.file_id
            file_unique_id = message.document.file_unique_id
            file_type = 'document'    
        elif message.photo:
            file_id = message.photo[-1].file_id
            file_unique_id = message.photo[-1].file_unique_id
            file_type = 'photo'
        
        try:
            # 检查是否存在
            self.MediaGroup.get(self.MediaGroup.file_id == file_id, self.MediaGroup.media_group_id == media_group_id)
        except self.MediaGroup.DoesNotExist:
            # 如果不存在则插入
            self.MediaGroup.create(file_id=file_id, media_group_id=media_group_id,file_type=file_type)

    async def man_bot_loop(self, client):
        start_time = time.time()
        media_count = 0

        NEXT_CYCLE = False
        async for dialog in client.iter_dialogs():
            NEXT_DIALOGS = False
            entity = dialog.entity

            # 打印处理的实体名称（频道或群组的标题）
            if isinstance(entity, Channel) or isinstance(entity, Chat):
                entity_title = entity.title
            elif isinstance(entity, User):
                entity_title = f'{entity.first_name or ""} {entity.last_name or ""}'.strip()
            else:
                entity_title = f'Unknown entity {entity.id}'

            # 设一个黑名单列表，如果 entity.id 在黑名单列表中，则跳过
            blacklist = [777000,93372553]

            if entity.id in blacklist:
                NEXT_DIALOGS = True
                continue

            if dialog.unread_count > 0 and (dialog.is_user):
                time.sleep(0.5)  # 每次请求之间等待0.5秒
                
                # print(f">Reading messages from entity {entity.id} {entity_title} - U:{dialog.unread_count} \n", flush=True)
                self.logger.info(f">Reading messages from entity {entity.id} {entity_title} - U:{dialog.unread_count} \n")

                async for message in client.iter_messages(entity, min_id=0, limit=50, reverse=True, filter=InputMessagesFilterEmpty()):
                    time.sleep(1)  # 每次请求之间等待0.5秒
                    # for message in iter_messages:
            
                    ## 如果是 media 类型的消息
                    if message.media and not isinstance(message.media, MessageMediaWebPage):
                        if dialog.is_user:
                            try:

                                
                                send_result = await self.send_message_to_dye_vat(client, message)
                                if send_result:
                                    await client.delete_messages(entity.id, message.id)
                                    # print(f"Send result: {send_result}", flush=True)
                                else:
                                    print(f"Error forwarding message: {e}", flush=True)
                                    traceback.print_exc()
                                
                                #await self.forward_media_to_warehouse(client, message)
                            except Exception as e:
                                print(f"Error forwarding message: {e}", flush=True)
                                traceback.print_exc()
                            finally:
                                NEXT_MESSAGE = True
                        else:
                            continue
                    else:
                        
                        await client.delete_messages(entity.id, message.id)
                        
                    # print(f"Delete {message.id} ", flush=True)
                    #await client.delete_messages(entity.id, message.message_id)

    async def load_tg_setting(self, client,chat_id, message_thread_id=0):
        try:
            chat_entity = await client.get_entity(int(chat_id))
            # print(f"Chat entity found: {chat_entity}")
        except Exception as e:
            print(f"Invalid chat_id: {e}")
            print("Traceback:\r\n")
            traceback.print_exc()  # 打印完整的异常堆栈信息，包含行号
            return None  # 提前返回，避免后续逻辑报错

        # 获取指定聊天的消息，限制只获取一条最新消息
        # 使用 get_messages 获取指定 thread_id 的消息
        try:
            messages = await client.get_messages(chat_entity, limit=1, reply_to=message_thread_id)
            # print(f"Messages found: {messages}")
        except Exception as e:
            print(f"Error fetching messages: {e}")
            return
        
        if not messages or not messages[0].text:
            return "No messages found."

        # 确认 messages[0] 中否为 json , 若是则返回, 不是则返回 None
        if messages[0].text.startswith('{') and messages[0].text.endswith('}'):
            return json.loads(messages[0].text)
        else:
            return json.loads("{}")


    # show_caption = yes, no
    async def send_message_to_dye_vat(self, client, message):
        last_message_id = message.id
        # 构建 caption

        try:
            if hasattr(message, 'grouped_id') and message.grouped_id:
                
                # 获取相册中的所有消息
                # print(f"\r\nPeer ID: {message.peer_id}",flush=True)
                album_messages = await client.get_messages(message.peer_id, limit=100, min_id=message.id,reverse=True)
                # print(f"\r\nAlbum messages: {album_messages}",flush=True)

                album = [msg for msg in album_messages if msg.grouped_id == message.grouped_id]
                # print(f"\r\nAlbum: {album}",flush=True)
                if album:
                    await asyncio.sleep(0.5)  # 间隔80秒
                    last_message_id = max(row.id for row in album)
                    # await client.send_file(self.setting['warehouse_chat_id'], album, reply_to=message.id, caption=caption_text, parse_mode='html')
                    return await client.send_file(self.setting['warehouse_chat_id'], album, parse_mode='html')
                   

                    
            elif isinstance(message.media, types.MessageMediaDocument):
                mime_type = message.media.document.mime_type
                if mime_type.startswith('video/'):
                    # 处理视频
                    video = message.media.document
                    # await client.send_file(self.setting['warehouse_chat_id'], video, reply_to=message.id, caption=caption_text, parse_mode='html')
                    
                    return await client.send_file(self.setting['warehouse_chat_id'], video, parse_mode='html')
                    
                    
                    # 调用新的函数
                    #await self.send_video_to_filetobot_and_publish(client, video, message)
                else:
                    # 处理文档
                    document = message.media.document
                    # await client.send_file(self.setting['warehouse_chat_id'], document, reply_to=message.id, caption=caption_text, parse_mode='html')
                    return await client.send_file(self.setting['warehouse_chat_id'], document, parse_mode='html')
                  
            elif isinstance(message.media, types.MessageMediaPhoto):
                # 处理图片
                photo = message.media.photo
                return await client.send_file(self.setting['warehouse_chat_id'], photo, parse_mode='html')
                
               
            else:
                print("Received media, but not a document, video, photo, or album.")
        except WorkerBusyTooLongRetryError:
            print(f"WorkerBusyTooLongRetryError encountered. Skipping message {message.id}.")
        except Exception as e:
            print(f"An error occurred: {e}")
        



   
# tgbot = JJLode()     
# encode_text = tgbot.encode("AgADgwEAAorgCFY","BAACAgUAAxkBAAIJImR_62QHj9z8JBk9TfHEdzy9yx8hAAKDAQACiuAIVuRai5Vm89YVLwQ","test13182732bot","p","2312167403")
# print(encode_text)

# decode_text = tgbot.decode(encode_text)
# print(f"{decode_text}")

# # 测试案例：多行文字
# test_text = """
# p_didipanbot_abc§def§ghi§jkl§
# v_didipanbot_test123§456§789§end§
# D_didipanbot_A§B§C§D§
# A_didipanbot_1§2§3§4§
# x_didipanbot_abc§def§ghi§jkl§  # 不符合
# p_didipanbot_abc§def§ghi§jkl
# u_didipanbot_only_three§one§two§  # 不符合
# p_didipanbot_1BRàD¶ãÅbUFÁÎ§2Úë4-otdC_ríÛÙí9íjeëà×ßÈqý©ÃaÉäÌïUfçÇýß¤0ê®üØÐ¡äè·£Ç¶7¾oæ¢H§5Á¨DuT¦¡ÆËUÚê§0§
# p_didipanbot_2BRàD¶ãÅbUFÁÎ§2Úë4-otdC_ríÛÙí9íjeëà×ßÈqý©ÃaÉäÌïUfçÇýß¤0ê®üØÐ¡äè·£Ç¶7¾oæ¢H§5Á¨DuT¦¡ÆËUÚê§0§
# """

# decode_row = tgbot.find_encode_code(test_text)
# print(f"{decode_row}")
