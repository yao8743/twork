import os
import re
import json
import jieba
from dotenv import load_dotenv

if not os.getenv('GITHUB_ACTIONS'):
    load_dotenv()

from peewee import *
from model.mysql_models import (
    DB_MYSQL, Video, Document, SoraContent, FileTag, Tag, init_mysql
)

SYNC_TO_POSTGRES = os.getenv('SYNC_TO_POSTGRES', 'false').lower() == 'true'
BATCH_LIMIT = None
# 初始化 MySQL（必须先执行）
init_mysql()

# 如需 PostgreSQL，再导入并初始化
if SYNC_TO_POSTGRES:
    from model.pg_models import DB_PG, SoraContentPg, init_postgres
    from playhouse.shortcuts import model_to_dict
    init_postgres()

# 同义词字典
SYNONYM = {
    "滑鼠": "鼠标",
    "萤幕": "显示器",
    "笔电": "笔记本",
}

def clean_text(original_string):
    target_strings = ["- Advertisement - No Guarantee", "- 广告 - 无担保"]
    for target in target_strings:
        pos = original_string.find(target)
        if pos != -1:
            original_string = original_string[:pos]

    replace_texts = [
        "求打赏", "求赏", "可通过以下方式获取或分享文件",
        "私聊模式：将含有File ID的文本直接发送给机器人 @datapanbot 即可进行文件解析",
        "①私聊模式：将含有File ID的文本直接发送给机器人  即可进行文件解析",
        "单机复制：", "文件解码器:", "您的文件码已生成，点击复制：",
        "批量发送的媒体代码如下:", "此条媒体分享link:",
        "女侅搜索：@ seefilebot", "解码：@ MediaBK2bot",
        "如果您只是想备份，发送 /settings 可以设置关闭此条回复消息",
        "媒体包已创建！", "此媒体代码为:", "文件名称:", "分享链接:", "|_SendToBeach_|",
        "Forbidden: bot was kicked from the supergroup chat",
        "Bad Request: chat_id is empty"
    ]
    for text in replace_texts:
        original_string = original_string.replace(text, '')

    original_string = re.sub(r"分享至\d{4}-\d{2}-\d{2} \d{2}:\d{2} 到期后您仍可重新分享", '', original_string)

    json_pattern = r'\{[^{}]*?"text"\s*:\s*"[^"]+"[^{}]*?\}'
    matches = re.findall(json_pattern, original_string)
    for match in matches:
        try:
            data = json.loads(match)
            if 'content' in data and isinstance(data['content'], str):
                original_string += f"\n{data['content']}"
        except json.JSONDecodeError:
            pass
        original_string = original_string.replace(match, '')

    wp_patterns = [r'https://t\.me/[^\s]+']
    for pattern in wp_patterns:
        original_string = re.sub(pattern, '', original_string)

    for pat in [
        r'LINK\s*\n[^\n]+#C\d+\s*\nOriginal:[^\n]*\n?',
        r'LINK\s*\n[^\n]+#C\d+\s*\nForwarded from:[^\n]*\n?',
        r'LINK\s*\n[^\n]*#C\d+\s*',
        r'Original caption:[^\n]*\n?'
    ]:
        original_string = re.sub(pat, '', original_string)

    original_string = re.sub(r'^\s*$', '', original_string, flags=re.MULTILINE)
    lines = original_string.split('\n')
    unique_lines = list(dict.fromkeys(lines))
    result_string = "\n".join(lines)

    for symbol in ['🔑', '💎']:
        result_string = result_string.replace(symbol, '\r\n' + symbol)

    return result_string[:1500] if len(result_string) > 1500 else result_string

def replace_synonym(text):
    for k, v in SYNONYM.items():
        text = text.replace(k, v)
    return text

def segment_text(text):
    text = replace_synonym(text)
    return " ".join(jieba.cut(text))

def fetch_tag_cn_for_file(file_unique_id):
    return [
        t.tag_cn for t in Tag.select()
        .join(FileTag, on=(FileTag.tag == Tag.tag))
        .where(FileTag.file_unique_id == file_unique_id)
        if t.tag_cn
    ]

def sync_to_postgres(record):
    if not SYNC_TO_POSTGRES:
        return

    from playhouse.shortcuts import model_to_dict
    model_data = model_to_dict(record, recurse=False)
    model_data["id"] = record.id  # ✅ 主键显式带入

    # ✅ 强制带入 id，确保主键一致
    with DB_PG.atomic():
        try:
            existing = SoraContentPg.get(SoraContentPg.id == record.id)
            for k, v in model_data.items():
                setattr(existing, k, v)
            existing.save()
        except SoraContentPg.DoesNotExist:
            SoraContentPg.create(**model_data)


def process_documents():
    DB_MYSQL.connect()
    if SYNC_TO_POSTGRES:
        DB_PG.connect()

    for doc in Document.select().where((Document.kc_status.is_null(True)) | (Document.kc_status != 'updated')).limit(BATCH_LIMIT):
        if not doc.file_name and not doc.caption:
            doc.kc_status = 'updated'
            doc.save()
            continue

        content = clean_text(f"{doc.file_name or ''}\n{doc.caption or ''}")
        content_seg = segment_text(content)
        tag_cn_list = fetch_tag_cn_for_file(doc.file_unique_id)
        if tag_cn_list:
            content_seg += " " + " ".join(tag_cn_list)

        print(f"Processing {doc.file_unique_id}: {content_seg}")

        if doc.kc_id:
            try:
                kw = SoraContent.get_by_id(doc.kc_id)
                kw.source_id = doc.file_unique_id
                kw.content = content
                kw.content_seg = content_seg
                kw.file_size = doc.file_size
                kw.save()
            except SoraContent.DoesNotExist:
                kw = SoraContent.create(
                    source_id=doc.file_unique_id, 
                    type='d', 
                    content=content, 
                    content_seg=content_seg,
                    file_size = doc.file_size
                    )
                doc.kc_id = kw.id
        else:
            kw = SoraContent.create(
                source_id=doc.file_unique_id, type='d', content=content, content_seg=content_seg,file_size = doc.file_size)
            doc.kc_id = kw.id

        doc.kc_status = 'updated'
        doc.save()

       
        if SYNC_TO_POSTGRES and kw.id:     
            sync_to_postgres(kw)

    DB_MYSQL.close()
    if SYNC_TO_POSTGRES:
        DB_PG.close()


def process_videos():
    DB_MYSQL.connect()
    if SYNC_TO_POSTGRES:
        DB_PG.connect()

    for doc in Video.select().where((Video.kc_status.is_null(True)) | (Video.kc_status != 'updated')).limit(BATCH_LIMIT):
        if not doc.file_name and not doc.caption:
            doc.kc_status = 'updated'
            doc.save()
            continue

        content = clean_text(f"{doc.file_name or ''}\n{doc.caption or ''}")
        content_seg = segment_text(content)
        tag_cn_list = fetch_tag_cn_for_file(doc.file_unique_id)
        if tag_cn_list:
            content_seg += " " + " ".join(tag_cn_list)

        print(f"Processing {doc.file_unique_id}: {content_seg}")

        if doc.kc_id:
            try:
                kw = SoraContent.get_by_id(doc.kc_id)
                kw.source_id = doc.file_unique_id
                kw.content = content
                kw.content_seg = content_seg
                kw.file_size = doc.file_size
                kw.duration = doc.duration
                kw.save()
            except SoraContent.DoesNotExist:
                kw = SoraContent.create(
                    source_id=doc.file_unique_id, 
                    type='v', 
                    content=content, 
                    content_seg=content_seg,
                    file_size = doc.file_size,
                    duration = doc.duration
                    )
                doc.kc_id = kw.id
        else:
            kw = SoraContent.create(
                source_id=doc.file_unique_id, 
                type='v', 
                content=content, 
                content_seg=content_seg,
                file_size = doc.file_size,
                duration = doc.duration
                )
            doc.kc_id = kw.id

        doc.kc_status = 'updated'
        doc.save()

       
        if SYNC_TO_POSTGRES and kw.id:     
            sync_to_postgres(kw)

    DB_MYSQL.close()
    if SYNC_TO_POSTGRES:
        DB_PG.close()

if __name__ == "__main__":
    process_documents()
    process_videos()
