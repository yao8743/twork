import random
from datetime import datetime

class Nonsense:
    def __init__(self):
        self.time_greetings = {
            "morning": [
                "早", "早啊", "早上好", "早安", "起了", "醒啦", "上班啦", "新的一天", "群友们好", "刚睡醒"
            ],
            "noon": [
                "中午好", "吃了吗", "午安", "午饭呢", "休息下", "别太累", "该吃饭了", "群友们好","666"
            ],
            "afternoon": [
                "下午好", "还行吗", "继续吧", "醒着呢", "喝口水", "坚持住", "加把劲", "群友们好","看看"
            ],
            "evening": [
                "晚上好", "下班啦", "回来了", "吃晚饭了", "放松下", "群友们好","来色色了","总算忙完了"
            ],
            "late_night": [
                "别熬了", "快睡", "晚安", "困又不想睡", "早点休息", "早点休息", "群友们好","😁","今天好忙"
            ]
        }

    def get_time_period(self, hour=None):
        if hour is None:
            hour = datetime.now().hour
        if 5 <= hour < 11:
            return "morning"
        elif 11 <= hour < 14:
            return "noon"
        elif 14 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "late_night"

    def generate_greeting(self, hour=None):
        period = self.get_time_period(hour)
        greetings = self.time_greetings[period]
        weights = [random.uniform(0.8, 1.2) for _ in greetings]  # 模拟偏好但保持浮动
        return random.choices(greetings, weights=weights, k=1)[0]

# 示例用法
if __name__ == "__main__":
    bot = Nonsense()
    for _ in range(5):
        print(bot.generate_greeting())
