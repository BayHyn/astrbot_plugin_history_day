import json
import os
from datetime import date
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform import AstrMessageEvent


PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

FONT_PATH = os.path.join(PLUGIN_DIR, "resource", "华文新魏.ttf")
BACKGROUND_PATH = os.path.join(PLUGIN_DIR, "resource", "background.png")
TEMP_DIR = os.path.join(PLUGIN_DIR, "temp")

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


@register("历史上的今天", "Zhalslar", "饰乐插件", "1.0.0", "https://github.com/Zhalslar/astrbot_plugin_today_in_history")
class HistoryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.month = date.today().strftime("%m")
        self.day = date.today().strftime("%d")
        self.today_date_str = date.today().strftime("%Y_%m_%d")
        self.temp_path = os.path.join(TEMP_DIR, f"{self.today_date_str}.png")
        self.is_temp_image = config.get('is_temp_image', True)
        self.auto_clear_temp = config.get('auto_clear_temp', True)
        self.red_depth = config.get('red_depth', 40)



    @filter.command("历史上的今天")
    async def handle_history_today(self, event: AstrMessageEvent):
        if self.is_temp_image and os.path.exists(self.temp_path) :
            yield event.image_result(self.temp_path)
            return

        text = await self.get_events_on_history(self.month)

        data = self.html_to_json_func(text)

        today = f"{self.month}{self.day}"
        f_today = f"{self.month.lstrip('0') or '0'}月{self.day.lstrip('0') or '0'}日"
        reply = f"【历史上的今天-{f_today}】\n"
        len_max = len(data[self.month][today])
        for i in range(len_max):
            str_year = data[self.month][today][i]["year"]
            str_title = data[self.month][today][i]["title"]
            reply += f"{str_year} {str_title}" + ("\n" if i < len_max - 1 else "")

        image_path = self.text_to_image_path(reply)
        yield event.image_result(image_path)

        if not self.is_temp_image:
            os.remove(self.temp_path)

        if self.auto_clear_temp:
            for file_path in (os.path.join(TEMP_DIR, f) for f in os.listdir(TEMP_DIR)):
                if file_path != self.temp_path:
                    os.unlink(file_path)


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

    def text_to_image_path(self, text: str) -> str:
        """将给定文本转换为图像，并返回图像的保存路径"""

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
            line_color = (random.randint(0, self.red_depth), random.randint(0, 16), random.randint(0, 32))
            draw.text((MARGIN_LEFT, y_text), line, fill=line_color, font=font)
            y_text += LINE_HEIGHT

        # 将图片保存
        img_byte_arr = BytesIO()
        background_img.save(img_byte_arr, format='PNG')
        with open(self.temp_path, 'wb') as f:
            f.write(img_byte_arr.getvalue())
        return self.temp_path








