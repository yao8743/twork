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
    file_unique_id = CharField(primary_key=True)
    caption = TextField(null=True)
    file_name = CharField(null=True)
    kc_id = IntegerField(null=True)
    kc_status = CharField(null=True)

    class Meta:
        table_name = 'document'

class KeywordContent(BaseModel):
    id = AutoField()
    source_id = CharField()
    type = CharField()
    content = TextField()
    content_seg = TextField()

    class Meta:
        table_name = 'keyword_content'

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
