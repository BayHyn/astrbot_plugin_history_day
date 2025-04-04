import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.platform import AstrMessageEvent
import astrbot.core.message.components  as Comp

RESOURCE_DIR = Path("data/plugins/astrbot_plugin_history_day/resource")
FONT_PATH = RESOURCE_DIR / "华文新魏.ttf"
BACKGROUND_PATH = RESOURCE_DIR / "background.png"

TEMP_DIR = Path("data/plugins_data/astrbot_plugin_history_day")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


@register("astrbot_plugin_history_day", "Zhalslar", "查看历史上的某天发生的大事", "1.0.0", "https://github.com/Zhalslar/astrbot_plugin_history_day")
class HistoryPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.month = date.today().strftime("%m")
        self.day = date.today().strftime("%d")


    @filter.regex(r'^历史上的.*')
    async def on_regex(self, event: AstrMessageEvent):
        """/历史上的{今天、昨天、明天、3月12日、3月12号、3.12}"""
        date_str: str = event.get_message_str().lstrip("历史上的").strip()
        today: date = datetime.now().date()
        if date_str in {"今天", "昨天", "明天"}:
            date_map = {
                "今天": today,
                "昨天": today - timedelta(days=1),
                "明天": today + timedelta(days=1),
            }
            self.month = f"{date_map[date_str].month:02d}"  # 保持两位数格式
            self.day = f"{date_map[date_str].day:02d}"  # 保持两位数格式
        else:
            patterns = [
                r"^(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号]$",  # %m月%d日 或 %m月%d号
                r"^(?P<month>\d{1,2})\.(?P<day>\d{1,2})$",  # %m.%d
            ]
            for pattern in patterns:
                if match := re.match(pattern, date_str):
                    month = int(match.group("month"))
                    day = int(match.group("day"))
                    self.month = f"{month:02d}"  # 保持两位数格式
                    self.day = f"{day:02d}"  # 保持两位数格式
                    try:
                        datetime(year=today.year, month=month, day=day)  # 验证日期是否有效
                    except ValueError:
                        return
                    break
            else:
                return
        image_name = f"{self.month}月{self.day}日.png"
        image_path = TEMP_DIR / image_name
        if image_path.exists():
            yield event.image_result(str(image_path))
            return

        text = await self.get_events_on_history(self.month)
        data = self.html_to_json_func(text)

        today_ = f"{self.month}{self.day}"
        f_today = f"{self.month.lstrip('0') or '0'}月{self.day.lstrip('0') or '0'}日"
        reply = f"【历史上的今天-{f_today}】\n"
        len_max = len(data[self.month][today_])
        for i in range(len_max):
            str_year = data[self.month][today_][i]["year"]
            str_title = data[self.month][today_][i]["title"]
            reply += f"{str_year} {str_title}" + ("\n" if i < len_max - 1 else "")

        image_bytes = self.text_to_image_bytes(reply)
        image = Image.open(BytesIO(image_bytes))
        image.save(image_path)

        chain=[Comp.Image.fromBytes(image_bytes)]
        yield event.chain_result(chain)



    @staticmethod
    async def get_events_on_history(month: str) -> str:
        try:
            async with aiohttp.ClientSession() as client:
                url = f"https://baike.baidu.com/cms/home/eventsOnHistory/{month}.json"
                response = await client.get(url)
                response.encoding = "utf-8"
                return await response.text()
        except Exception as e:
            logger.error(f"任务处理失败: {e}")
            return ""

    @staticmethod
    def html_to_json_func(text: str) -> json:
        """处理返回的HTML内容，转换为JSON格式"""
        text = text.replace("<\/a>", "").replace("\n", "")

        while True:
            address_head = text.find("<a target=")
            address_end = text.find(">", address_head)
            if address_head == -1 or address_end == -1:
                break
            text_middle = text[address_head:address_end + 1]
            text = text.replace(text_middle, "")

        address_head = 0
        while True:
            address_head = text.find('"desc":', address_head)
            address_end = text.find('"cover":', address_head)
            if address_head == -1 or address_end == -1:
                break
            text_middle = text[address_head + 8:address_end - 2]
            address_head = address_end
            text = text.replace(text_middle, "")

        address_head = 0
        while True:
            address_head = text.find('"title":', address_head)
            address_end = text.find('"festival"', address_head)
            if address_head == -1 or address_end == -1:
                break
            text_middle = text[address_head + 9:address_end - 2]
            if '"' in text_middle:
                text_middle = text_middle.replace('"', " ")
                text = text[:address_head + 9] + text_middle + text[address_end - 2:]
            address_head = address_end

        return json.loads(text)

    @staticmethod
    def text_to_image_bytes(text: str) -> bytes:
        """将给定文本转换为图像"""

        FONT_SIZE = 20  # 字体大小
        LINE_HEIGHT = 30  # 行高
        MARGIN_LEFT = 40  # 左边距
        MARGIN_RIGHT = 10  # 右边距
        TOP_MARGIN = 10  # 上边距
        BOTTOM_MARGIN = 10  # 下边距

        font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
        draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))

        lines = text.split('\n')
        max_width = 0
        total_height = 0

        # 计算整个文本的高度和每一行的最大宽度
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width, line_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
            max_width = max(max_width, line_width)
            total_height += LINE_HEIGHT

        # 加载背景图片
        background_img = Image.open(BACKGROUND_PATH).resize(
            (max_width + MARGIN_RIGHT + 80, total_height + BOTTOM_MARGIN)
        )
        draw = ImageDraw.Draw(background_img)

        y_text = TOP_MARGIN
        for line in lines:
            line_color = (random.randint(0, 40), random.randint(0, 16), random.randint(0, 32))
            draw.text((MARGIN_LEFT, y_text), line, fill=line_color, font=font)
            y_text += LINE_HEIGHT

        img_byte_arr = BytesIO()
        background_img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()






