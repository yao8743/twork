# lz_db.py
import asyncpg
from lz_config import POSTGRES_DSN
from lz_memory_cache import MemoryCache
from datetime import datetime
import lz_var

class DB:
    def __init__(self):
        self.dsn = POSTGRES_DSN
        self.pool = None
        self.cache = MemoryCache()

    async def connect(self):
        self.pool = await asyncpg.create_pool(dsn=self.dsn)

    def _normalize_query(self, keyword_str: str) -> str:
        return " ".join(keyword_str.strip().lower().split())

    async def search_keyword_page_highlighted(self, keyword_str: str, last_id: int = 0, limit: int = 10):
        query = self._normalize_query(keyword_str)
        cache_key = f"highlighted:{query}:{last_id}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT id, source_id, file_type,
                       ts_headline('simple', content, plainto_tsquery('simple', $1)) AS highlighted_content
                FROM sora_content
                WHERE content_seg_tsv @@ plainto_tsquery('simple', $1)
                  AND id > $2
                ORDER BY id ASC
                LIMIT $3
                ''',
                query, last_id, limit
            )
            result = [dict(r) for r in rows]
            self.cache.set(cache_key, result, ttl=60)  # 缓存 60 秒
            return result

    async def search_keyword_page_plain(self, keyword_str: str, last_id: int = 0, limit: int = None):
        query = self._normalize_query(keyword_str)
        cache_key = f"plain:{query}:{last_id}:{limit}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT id, source_id, file_type, content 
                FROM sora_content
                WHERE content_seg_tsv @@ plainto_tsquery('simple', $1)
                AND id > $2
                ORDER BY id DESC
                LIMIT $3
                ''',
                query, last_id, limit
            )
            result = [dict(r) for r in rows]
            self.cache.set(cache_key, result, ttl=60)
            return result


    # async def upsert_file_extension(self,
    #     file_type: str,
    #     file_unique_id: str,
    #     file_id: str,
    #     bot: str,
    #     user_id: str = None
    # ):
    #     sql = """
    #         INSERT INTO file_extension (
    #             file_type, file_unique_id, file_id, bot, user_id, create_time
    #         ) VALUES ($1, $2, $3, $4, $5, $6)
    #         ON CONFLICT (file_unique_id, bot)
    #         DO UPDATE SET
    #             file_id = EXCLUDED.file_id,
    #             create_time = EXCLUDED.create_time
    #     """
    #     print(f"Executing SQL:\n{sql.strip()}")
    #     print(f"With params: {file_type}, {file_unique_id}, {file_id}, {bot}, {user_id}, {datetime.utcnow()}")

    #     async with self.pool.acquire() as conn:
    #         await conn.execute(sql, file_type, file_unique_id, file_id, bot, user_id, datetime.utcnow())


    async def upsert_file_extension(self,
        file_type: str,
        file_unique_id: str,
        file_id: str,
        bot: str,
        user_id: str = None
    ):
        now = datetime.utcnow()

        sql = """
            INSERT INTO file_extension (
                file_type, file_unique_id, file_id, bot, user_id, create_time
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (file_unique_id, bot)
            DO UPDATE SET
                file_id = EXCLUDED.file_id,
                create_time = EXCLUDED.create_time
            
        """

        # print(f"Executing SQL:\n{sql.strip()}")
        # print(f"With params: {file_type}, {file_unique_id}, {file_id}, {bot}, {user_id}, {now}")

        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(sql, file_type, file_unique_id, file_id, bot, user_id, now)

        # print("DB result:", dict(result) if result else "No rows returned")


    async def search_sora_content_by_id(self, content_id: int):
        cache_key = f"sora_content_id:{content_id}"
        cached = self.cache.get(cache_key)
        if cached:
            print(f"Cache hit for {cache_key}")
            return cached
    
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                '''
                SELECT s.id, s.source_id, s.file_type, s.content, s.file_size, s.duration, s.tag,
                     m.file_id, m.thumb_file_id
                FROM sora_content s
                LEFT JOIN sora_media m ON s.id = m.content_id AND m.source_bot_name = $2
                WHERE s.id = $1
                ''',
                content_id, lz_var.bot_username
            )
            # 只缓存存在的记录
            if row:
                self.cache.set(cache_key, row, ttl=3600)  # 例如缓存 1 小时
            return row
            # 返回 asyncpg Record 或 None


    async def get_file_id_by_file_unique_id(self, unique_ids: list[str]) -> list[str]:
        """
        根据多个 file_unique_id 取得对应的 file_id 列表。
        """
        if not unique_ids:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT file_id
                FROM file_extension
                WHERE file_unique_id = ANY($1::text[])
                AND bot = $2
                ''',
                unique_ids, lz_var.bot_username
            )
            print(f"Fetched {len(rows)} rows for unique_ids: {unique_ids} {rows}")
            return [r['file_id'] for r in rows if r['file_id']]

db = DB()