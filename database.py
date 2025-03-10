from peewee import MySQLDatabase
import os

# 检查是否在本地开发环境中运行
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    load_dotenv()


db_config = {
    'db_name': os.getenv('DB_NAME'),
    'db_user': os.getenv('DB_USER'),
    'db_password': os.getenv('DB_PASSWORD'),
    'db_host': os.getenv('DB_HOST'),
    'db_sslmode': os.getenv('DB_SSLMODE','require'),
    'db_port': int(os.getenv('DB_PORT',3306)),
}

# 数据库配置
db = MySQLDatabase(
    db_config['db_name'],
    user=db_config['db_user'],
    password=db_config['db_password'],
    host=db_config['db_host'],
    port=db_config['db_port'],
    charset='utf8mb4'
)

def initialize_db():
    db.connect()
   
