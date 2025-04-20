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

class KeywordContentPg(PgBaseModel):
    id = IntegerField(primary_key=True)  # ✅ 改成 IntegerField 显式指定 id
    source_id = CharField()
    type = CharField()
    content = TextField()
    content_seg = TextField()
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'keyword_content'