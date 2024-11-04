from vendor.class_lycode import LYCode  # 导入 LYClass

lycode = LYCode()

row = {
    'file_unique_id': 'AQADaasxG5DaiUd-',
    'file_id': 'AgACAgEAAx0Ce204aAADUmcd23cD8-vfl1q4UkQX4pQhHYxvAAJpqzEbkNqJRwXXoPx8L0iOAQADAgADeQADNgQ',
    'bot': 'SalaiZTDBOT',
    'file_type': 'photo'
}

text = lycode.encode(row['file_unique_id'], row['file_id'], row['bot'], row['file_type'])
print(text)
row2 = lycode.decode(text)
print(row2)
