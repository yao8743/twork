# models/photo.py
from peewee import CharField, DateTimeField, AutoField, IntegerField, BigIntegerField, SQL
from model.base import BaseModel

# 定义 Scrap 模型
class ScrapProgress(BaseModel):
    id = AutoField(primary_key=True)
    chat_id = BigIntegerField()  # 将 chat_id 设置为主键
    message_id = BigIntegerField()
    update_datetime = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    api_id = IntegerField(null=True)

    class Meta:
        table_name = 'scrap_progress'



