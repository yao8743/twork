# models/photo.py
from peewee import CharField, DateTimeField, AutoField, IntegerField, BigIntegerField, PrimaryKeyField
from model.base import BaseModel

# 定义 Scrap 模型
class Scrap(BaseModel):
    id = BigIntegerField(primary_key=True)
    content = CharField(null=True, max_length=200)
    enc_user_id = CharField(null=True, max_length=10)
    user_id = BigIntegerField(null=True)
    user_fullname = CharField(null=True, max_length=30)
    fee = IntegerField(null=True)
    start_key = CharField(max_length=30)
    source_bot_id = BigIntegerField(null=True)
    source_chat_id = BigIntegerField(null=True)
    source_message_id = BigIntegerField(null=True)
    thumb_file_id = CharField(null=True, max_length=100)
    thumb_file_unique_id = CharField(null=True, max_length=30)
    estimated_file_size = BigIntegerField(null=True)
    duration = IntegerField(null=True)
    number_of_times_sold = IntegerField(null=True)
    tag = CharField(null=True, max_length=100)

    class Meta:
        table_name = 'scrap'


