# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import platform
from typing_extensions import Self
from PIL import Image, ImageDraw, ImageFont


class ImageUtil:
    """
    基于Pillow的图像处理工具类
    支持图像的非等比例尺缩放, 裁剪, 绘制文字, 矩形框, 圆形框, 以及保存和查看功能
    """

    def __init__(self, image_path=None):
        """
        初始化

        Args:
            image_path (str, optional): 图像文件路径
        """
        self.image = None
        self.original_image = None
        if image_path and os.path.exists(image_path):
            self.open_image(image_path)

    def open_image(self, image_path) -> Self:
        """
        打开图像文件

        Args:
            image_path (str): 图像文件路径

        Returns:
            self: 返回实例本身以支持链式调用
        """
        try:
            self.image = Image.open(image_path)
            # 保存原始图像以便后续操作
            self.original_image = self.image.copy()
            return self
        except Exception as e:
            print(f"打开图像失败: {e}")
            return self

    def resize(self, width=None, height=None, keep_aspect_ratio=False) -> Self:
        """
        非等比例尺缩放图像

        Args:
            width (int, optional): 目标宽度
            height (int, optional): 目标高度
            keep_aspect_ratio (bool, optional): 是否保持宽高比

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            print("未加载图像")
            return self

        try:
            if keep_aspect_ratio:
                # 保持宽高比缩放
                if width and not height:
                    ratio = width / self.image.width
                    height = int(self.image.height * ratio)
                elif height and not width:
                    ratio = height / self.image.height
                    width = int(self.image.width * ratio)
                else:
                    # 如果同时提供了width和height，使用较小的缩放比例
                    ratio = min(width / self.image.width, height / self.image.height)
                    width = int(self.image.width * ratio)
                    height = int(self.image.height * ratio)

            self.image = self.image.resize((width, height), Image.LANCZOS)
            return self
        except Exception as e:
            print(f"缩放图像失败: {e}")
            return self

    def crop(self, left, top, right, bottom) -> Self:
        """
        裁剪图像

        Args:
            left (int): 左边界坐标
            top (int): 上边界坐标
            right (int): 右边界坐标
            bottom (int): 下边界坐标

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            print("未加载图像")
            return self

        try:
            # 确保坐标有效
            left = max(0, left)
            top = max(0, top)
            right = min(self.image.width, right)
            bottom = min(self.image.height, bottom)

            if left < right and top < bottom:
                self.image = self.image.crop((left, top, right, bottom))
                return self
            else:
                print("裁剪坐标无效")
                return self
        except Exception as e:
            print(f"裁剪图像失败: {e}")
            return self

    def draw_text(self, text, position, font_path=None, font_size=20, color=(0, 0, 0)) -> Self:
        """
        在图像上绘制文字

        Args:
            text (str): 要绘制的文字
            position (tuple): 文字起始位置 (x, y)
            font_path (str, optional): 字体文件路径
            font_size (int, optional): 字体大小，默认20
            color (tuple, optional): 文字颜色，默认黑色

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            print("未加载图像")
            return self

        try:
            draw = ImageDraw.Draw(self.image)

            # 尝试加载指定字体，失败则尝试查找系统中文字体
            try:
                if font_path and os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                else:
                    # 尝试自动查找系统中的中文字体
                    system_font = self._find_system_chinese_font()
                    if system_font:
                        font = ImageFont.truetype(system_font, font_size)
                    else:
                        # 如果找不到中文字体，使用默认字体并给出警告
                        print("警告: 未找到支持中文的字体，可能会出现乱码")
                        font = ImageFont.load_default()
            except Exception as e:
                print(f"加载字体时出错: {e}")
                font = ImageFont.load_default()

            draw.text(position, text, font=font, fill=color)
            return self
        except Exception as e:
            print(f"绘制文字失败: {e}")
            return self

    def draw_rectangle(self, position, outline_color=(255, 0, 0), fill_color=None, width=2) -> Self:
        """
        在图像上绘制矩形框

        Args:
            position (tuple): 矩形位置 (left, top, right, bottom)
            outline_color (tuple, optional): 边框颜色，默认红色
            fill_color (tuple, optional): 填充颜色，默认无填充
            width (int, optional): 边框宽度，默认2

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            print("未加载图像")
            return self

        try:
            draw = ImageDraw.Draw(self.image)
            draw.rectangle(position, outline=outline_color, fill=fill_color, width=width)
            return self
        except Exception as e:
            print(f"绘制矩形失败: {e}")
            return self

    def draw_circle(self, center, radius, outline_color=(255, 0, 0), fill_color=None, width=2) -> Self:
        """
        在图像上绘制圆形框

        Args:
            center (tuple): 圆心位置 (x, y)
            radius (int): 圆的半径
            outline_color (tuple, optional): 边框颜色，默认红色
            fill_color (tuple, optional): 填充颜色，默认无填充
            width (int, optional): 边框宽度，默认2

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            print("未加载图像")
            return self

        try:
            draw = ImageDraw.Draw(self.image)
            # 计算圆形的边界框
            left = center[0] - radius
            top = center[1] - radius
            right = center[0] + radius
            bottom = center[1] + radius

            draw.ellipse((left, top, right, bottom), outline=outline_color, fill=fill_color, width=width)
            return self
        except Exception as e:
            print(f"绘制圆形失败: {e}")
            return self

    def save(self, output_path) -> bool:
        """
        保存处理后的图像

        Args:
            output_path (str): 输出文件路径

        Returns:
            bool: 保存成功返回True，失败返回False
        """
        if not self.image:
            print("未加载图像")
            return False

        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            self.image.save(output_path)
            print(f"图像已保存至: {output_path}")
            return True
        except Exception as e:
            print(f"保存图像失败: {e}")
            return False

    def show(self) -> Self:
        """
        显示处理后的图像

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            print("未加载图像")
            return self

        try:
            self.image.show()
            return self
        except Exception as e:
            print(f"显示图像失败: {e}")
            return self

    def reset(self) -> Self:
        """
        重置图像为原始状态

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if self.original_image:
            self.image = self.original_image.copy()
            return self
        else:
            print("没有原始图像可供重置")
            return self

    def _find_system_chinese_font(self):
        """
        自动查找系统中支持中文的字体

        Returns:
            str: 找到的字体文件路径，找不到则返回None
        """
        # 根据不同操作系统查找可能的中文字体
        system = platform.system()

        if system == "Windows":
            # Windows系统常见中文字体路径
            font_paths = [
                r"C:\Windows\Fonts\simsun.ttc",  # 宋体
                r"C:\Windows\Fonts\simhei.ttf",  # 黑体
                r"C:\Windows\Fonts\msyh.ttc",  # 微软雅黑
                r"C:\Windows\Fonts\msyhbd.ttc",  # 微软雅黑加粗
                r"C:\Windows\Fonts\simkai.ttf",  # 楷体
                r"C:\Windows\Fonts\simfang.ttf"  # 仿宋
            ]
        elif system == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/PingFang.ttc",  # 苹方
                "/System/Library/Fonts/SFNS.ttc",  # San Francisco
                "/Library/Fonts/Arial Unicode.ttf"
            ]
        else:  # Linux等其他系统
            font_paths = [
                "/usr/share/fonts/wqy/wqy-microhei.ttc",  # 文泉驿微米黑
                "/usr/share/fonts/wqy/wqy-zenhei.ttc",  # 文泉驿正黑
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
            ]

        # 检查是否存在这些字体文件
        for font_path in font_paths:
            if os.path.exists(font_path):
                return font_path

        return None


# 使用示例
if __name__ == "__main__":
    # 创建处理器实例
    img_path = r"H:\Pictures\拯救姬.jpg"
    processor = ImageUtil()

    # 示例操作：打开图像、缩放、裁剪、绘制内容、保存和显示
    (processor.open_image(img_path)
     .resize(800, 600)
     .crop(100, 100, 700, 500)
     .draw_text("示例文字", (50, 50), font_size=30, color=(255, 0, 0))
     .draw_rectangle((150, 150, 450, 350), outline_color=(0, 255, 0), width=3)
     .draw_circle((400, 200), 50, outline_color=(0, 0, 255), width=2)
     .show()
     .save(f'H:\Pictures\拯救姬_1111.jpg')
     )
