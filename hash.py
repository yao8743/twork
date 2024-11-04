import hashlib
import re

class LicensePlateManager:
    def __init__(self):
        self.hash_table = {}
        self.city_list = [
            "京", "津", "沪", "渝", "冀", "豫", "云", "辽", "黑", "湘",
            "皖", "鲁", "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋",
            "蒙", "陕", "吉", "闽", "贵", "粤", "青", "藏", "川", "宁",
            "琼", "港", "澳", "台"
        ]

    def generate_short_hash(self, s):
        salt = "123"  # 简单的盐
        hashed_value = hashlib.md5((s + salt).encode()).hexdigest()[:6]  # 截取前6位
        self.hash_table[hashed_value] = s
        return hashed_value

    def decode_short_hash(self, short_hash):
        return self.hash_table.get(short_hash)

    def get_plate_number_caption(self, index):
        idx = index % (len(self.city_list))
        idx2 = index // (len(self.city_list))
        idx2 = chr(idx2 + 65)  # 转成英文大写字母
        result = f"{self.city_list[idx]}{idx2}"
        return result

    def parse_plate_number_caption(self, result_city):
        city_title = result_city[0]
        if city_title in self.city_list:
            index2 = self.city_list.index(city_title)
        letter = result_city[1]
        letter_num = ord(letter) - 65
        caption_idx = letter_num * len(self.city_list) + index2
        return caption_idx

    def get_plate_number(self, hex_str):
        while len(hex_str) < 6:
            hex_str = "0" + hex_str
        hex_result = int(bytes.fromhex(hex_str).hex(), 16)
        plate_number_tail = (hex_result % 100000)
        plate_number_header_idx = (hex_result // 100000)
        result = self.get_plate_number_caption(plate_number_header_idx) + "-" + str(plate_number_tail)
        return result

    def parse_plate_number(self, plate_number):
        city_title = plate_number[0]
        if city_title in self.city_list:
            index2 = self.city_list.index(city_title)
        letter = plate_number[1]
        letter_num = ord(letter) - 65
        plate_number_header_idx = letter_num * len(self.city_list) + index2
        plate_number_tail = plate_number.split("-")[1]
        plate_number_tail = int(plate_number_tail)
        plate_number_idx = plate_number_header_idx * 100000 + plate_number_tail
        plate_number = hex(plate_number_idx)[2:]    
        return plate_number

    def find_license_plates(self, text):
        pattern = r'[\u4e00-\u9fa5][A-Z]-\d{5}'
        license_plates = re.findall(pattern, text)
        return license_plates


# 示例用法
if __name__ == "__main__":
    urlkey = "2cPDOwJ4-zQ2NjM9"
    urlkey = "6HZvM8-mhnllZWY1"
    manager = LicensePlateManager()

    hex_str = manager.generate_short_hash(urlkey)
    print(f"生成的哈希: {hex_str}")

    plate_number = manager.get_plate_number(hex_str)
    print(f"车牌号: {plate_number}")


    hex_str2 = manager.parse_plate_number(plate_number)
    print(f"解析回的16进制字符串: {hex_str2}")

    hash2 = manager.decode_short_hash(hex_str2)
    print(f"解码的原始字符串: {hash2}\n")

    # 示例字符串
    text = "我的车牌是藏E-40334，朋友的车牌是琼A-31888，还有出租车牌湘E-504。"
    license_plates = manager.find_license_plates(text)

    #如果 license_plates 不是空列表，则使用 parse_plate_number 以 decode_short_hash 找出其原始字符串
    if license_plates:
        for plate in license_plates:
           
            hash2 = manager.decode_short_hash(manager.parse_plate_number(plate))
            print(f"解码的原始字符串: {plate} {hash2}\n")
    
