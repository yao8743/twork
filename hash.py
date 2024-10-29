import hashlib

# 初始化哈希表
hash_table = {}

# 示例
city_list = [
    "京", "津", "沪", "渝", "冀", "豫", "云", "辽", "黑", "湘",
    "皖", "鲁", "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋",
    "蒙", "陕", "吉", "闽", "贵", "粤", "青", "藏", "川", "宁",
    "琼", "港", "澳", "台"
]

# 生成带盐的哈希
def generate_short_hash(s):
    salt = "123"  # 简单的盐
    hashed_value = hashlib.md5((s + salt).encode()).hexdigest()[:6]  # 截取前6位
    hash_table[hashed_value] = s
    return hashed_value

# 解码函数
def decode_short_hash(short_hash):
    return hash_table.get(short_hash)

def get_plate_number_caption(index):

    idx = index%(len(city_list))
    idx2 = index//(len(city_list))
    #将 idx2 转成英文大写字母，A-Z 对应 0-25
    idx2 = chr(idx2 + 65)
    result = f"{city_list[idx]}{idx2}"
    return result

def parse_plate_number_caption(result_city):
    city_title = result_city[0]
    
    if city_title in city_list:
        index2 = city_list.index(city_title)   # +1 使其从 1 开始计数
    letter = result_city[1]
    #将 letter 转成数字, A-Z 对应 0-25
    letter_num = ord(letter) - 65
    caption_idx = letter_num * len(city_list) + index2
    return caption_idx

# 16进制字符串转车牌号
def get_plate_number(hex_str):
    #如何 hex_str 的长度未达到 6 位，则在前面补 0, 使其长度达到 6 位
    while len(hex_str) < 6:
        hex_str = "0" + hex_str

    hex_result = int(bytes.fromhex(hex_str).hex(),16)

    #将 hex_result 的万分位数值输出
    plate_number_tail = (hex_result % 100000)

    #将 hex_result 的十万分位以上数值输出
    plate_number_header_idx = (hex_result // 100000)

    result = get_plate_number_caption(plate_number_header_idx)+"-"+str(plate_number_tail)
    return result

# 车牌号转16进制字符串
def parse_plat_numer(plate_number):
    city_title = plate_number[0]
    
    if city_title in city_list:
        index2 = city_list.index(city_title)   # +1 使其从 1 开始计数
    letter = plate_number[1]
    #将 letter 转成数字, A-Z 对应 0-25
    letter_num = ord(letter) - 65
    plate_number_header_idx = letter_num * len(city_list) + index2

    #将 plate_number 的尾数输出
    plate_number_tail = plate_number.split("-")[1]
    plate_number_tail = int(plate_number_tail)
    #将 plate_number 的头数输出
    plate_number_idx = plate_number_header_idx * 100000 + plate_number_tail
    #将 plate_number_idx 转成 16 进制输出, 并去掉前面的 0x
    plate_number = hex(plate_number_idx)[2:]    
    return plate_number

urlkey = "ffffff"
print(f"{urlkey}")

hex_str = generate_short_hash(urlkey)
print(f"{hex_str}")

plate_number = get_plate_number(hex_str)
print(f"{plate_number}")

hex_str2 =  parse_plat_numer(plate_number)
print(f"{hex_str2}")

hash2 = decode_short_hash(hex_str2)
print(f"{hash2}")





