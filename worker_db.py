import aiomysql
from worker_config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, MYSQL_DB_PORT

class MySQLManager:
    def __init__(self):
        self.pool = None

    async def init_pool(self):
        self.pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            port=MYSQL_DB_PORT,
            charset="utf8mb4",
            autocommit=True,
            minsize=1,
            maxsize=5,
        )
        print("✅ MySQL 连接池已初始化")

    async def close_pool(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            print("✅ MySQL 连接池已关闭")

    async def fetch_bots_by_course_name(self, course_name):
        if not self.pool:
            raise Exception("MySQL pool 未初始化，请先调用 init_pool()")

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT bot_root FROM setting_member WHERE  course_name = %s", (course_name,))
                bot_roots = [row['bot_root'] for row in await cur.fetchall()]
                
                if not bot_roots:
                    return []

                format_strings = ','.join(['%s'] * len(bot_roots))
                await cur.execute(
                    f"SELECT bot_name FROM bot WHERE work_status = 'used' and bot_root IN ({format_strings})",
                    tuple(bot_roots)
                )
                return [row['bot_name'] for row in await cur.fetchall()]
