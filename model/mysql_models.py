import os
from peewee import *

DB_MYSQL = MySQLDatabase(None)

def init_mysql():
    DB_MYSQL.init(
        os.getenv('MYSQL_DB_NAME'),
        host=os.getenv('MYSQL_DB_HOST'),
        port=int(os.getenv('MYSQL_DB_PORT', 3306)),
        user=os.getenv('MYSQL_DB_USER'),
        password=os.getenv('MYSQL_DB_PASSWORD'),
        charset='utf8mb4'
    )

class BaseModel(Model):
    class Meta:
        database = DB_MYSQL

class Document(BaseModel):
    file_unique_id = CharField(primary_key=True, max_length=100)
    file_size = IntegerField(constraints=[SQL('UNSIGNED')])
    file_name = CharField(max_length=100, null=True)
    mime_type = CharField(max_length=100, null=True)
    caption = TextField(null=True)
    create_time = DateTimeField()
    files_drive = CharField(max_length=100, null=True)
    file_password = CharField(max_length=150, null=True)
    kc_id = IntegerField(null=True, constraints=[SQL('UNSIGNED')])
    kc_status = CharField(  # 或使用 Peewee 的 EnumField
        max_length=10,
        null=True,
        constraints=[SQL("CHECK(kc_status IN ('', 'pending', 'updated'))")]
    )

    class Meta:
        table_name = 'document'

from peewee import (
    Model, CharField, IntegerField, TextField, DateTimeField,
    SQL
)
from model.base import BaseModel  # 假设你的 BaseModel 统一管理连接等设置

class Video(BaseModel):
    file_unique_id = CharField(primary_key=True, max_length=100)
    file_size = IntegerField(constraints=[SQL('UNSIGNED')])
    duration = IntegerField()
    width = IntegerField()
    height = IntegerField()
    file_name = CharField(max_length=100, null=True)
    mime_type = CharField(max_length=100, default='video/mp4')
    caption = TextField(null=True)
    create_time = DateTimeField()
    update_time = DateTimeField(null=True)
    tag_count = IntegerField(default=0)
    kind = CharField(max_length=2, null=True)
    credit = IntegerField(default=0)
    files_drive = CharField(max_length=100, null=True)
    root = CharField(max_length=50, null=True)
    kc_id = IntegerField(null=True, constraints=[SQL('UNSIGNED')])
    kc_status = CharField(
        max_length=10,
        null=True,
        constraints=[SQL("CHECK(kc_status IN ('', 'pending', 'updated'))")]
    )

    class Meta:
        table_name = 'video'
        indexes = (
            (('file_size', 'width', 'height', 'mime_type'), False),
        )




class SoraContent(BaseModel):  
    id = AutoField()
    source_id = CharField(max_length=100)
    type = CharField(max_length=10)
    content = TextField()
    content_seg = TextField(null=True)
    file_size = BigIntegerField(null=True)
    duration = IntegerField(null=True)
    tag = CharField(max_length=200, null=True)
    thumb_file_unique_id = CharField(max_length=100, null=True)

    class Meta:
        table_name = 'sora_content'


class SoraMedia(BaseModel):
    id = AutoField()
    content_id = ForeignKeyField(SoraContent, backref='media', on_delete='CASCADE')
    source_bot_name = CharField(max_length=30)
    file_id = CharField(max_length=150, null=True)
    thumb_file_id = CharField(max_length=150, null=True)

    class Meta:
        table_name = 'sora_media'
        indexes = (
            (('content_id', 'source_bot_name'), True),  # UNIQUE
        )

class FileTag(BaseModel):
    id = AutoField()
    file_unique_id = CharField()
    tag = CharField()
    count = IntegerField(default=0)

    class Meta:
        table_name = 'file_tag'

class Tag(BaseModel):
    tag = CharField()
    tag_cn = CharField(null=True)

    class Meta:
        primary_key = False
        table_name = 'tag'
