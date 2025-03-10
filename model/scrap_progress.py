# models/photo.py
from peewee import CharField, DateTimeField, AutoField, IntegerField, BigIntegerField, SQL
from model.base import BaseModel

# 定义 Scrap 模型
class ScrapProgress(BaseModel):
    chat_id = BigIntegerField(primary_key=True)  # 将 chat_id 设置为主键
    message_id = BigIntegerField()
    update_datetime = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])


    class Meta:
        table_name = 'scrap_progress'



