import os
from peewee import *
from playhouse.postgres_ext import PostgresqlExtDatabase
import datetime
# 判断是否启用 PostgreSQL 同步


# 延迟初始化 Postgres 数据库
DB_PG = PostgresqlDatabase(None)

def init_postgres():
    DB_PG.init(
        os.getenv('PG_DB_NAME'),
        host=os.getenv('PG_DB_HOST'),
        port=int(os.getenv('PG_DB_PORT', 5432)),
        user=os.getenv('PG_DB_USER'),
        password=os.getenv('PG_DB_PASSWORD')
    )


class PgBaseModel(Model):
    class Meta:
        database = DB_PG

class SoraContentPg(PgBaseModel):  
    id = IntegerField(primary_key=True)  # 显式指定主键，用于同步 kc_id
    source_id = CharField(max_length=100)
    type = CharField(max_length=10)
    content = TextField()
    content_seg = TextField(null=True)
    content_seg_tsv = TSVectorField(null=True)  # GENERATED COLUMN
    file_size = BigIntegerField(null=True)
    duration = IntegerField(null=True)
    tag = CharField(max_length=200, null=True)
    thumb_file_unique_id = CharField(max_length=100, null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'sora_content'

class SoraMediaPg(PgBaseModel):
    id = AutoField()
    content_id = ForeignKeyField(SoraContentPg, backref='media', on_delete='CASCADE')
    source_bot_name = CharField(max_length=30)
    file_id = CharField(max_length=150, null=True)
    thumb_file_id = CharField(max_length=150, null=True)

    class Meta:
        table_name = 'sora_media'
        indexes = (
            (('content_id', 'source_bot_name'), True),  # UNIQUE
        )        