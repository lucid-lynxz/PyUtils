# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
from typing import Tuple, Union, List, Optional

from PIL import Image, ImageDraw, ImageFont
from typing_extensions import Self

from util.CommonUtil import CommonUtil


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

        self._font_path: str = None  # 绘制文字时的字体路径
        self._font: ImageFont = None  # 绘制文字时的字体对象

        if image_path and os.path.exists(image_path):
            self.open_image(image_path)

    def new(self, size: Union[Tuple[int, int], List[int]], bg_color: Union[float, Tuple[float, ...], str] = 'white', mode: str = 'RGB') -> Self:
        """
        创建一张新图片, 并在图片上进行各种操作
        :param size: 图像大小, 如: (400, 800) 表示宽400, 高800像素
        :param bg_color: 背景颜色,如: 'white'   '#ff0000'
        :param mode: 图像模式, 默认RGB模式
        """
        self.image = Image.new(mode, size, bg_color)
        return self

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
            CommonUtil.printLog(f"open_image fail:{e}")
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
            self.new((width, height))
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
            CommonUtil.printLog(f"resize fail:{e}")
            return self

    def resize_rect(self, rect: list, width: float, height: float) -> list:
        """
        根据图像的实际大小和目标大小缩放矩形框, 使得 rect 坐标满足实际图像大小

        :param rect: 矩形框坐标, 支持两种含义: (left, top, right, bottom) 或者 (left,top,width,height)
        :param width: 目标宽度, 正数有效
        :param height: 目标高度, 正数有效
        """
        if not self.image:
            CommonUtil.printLog("resize_rect fail:未加载图像")
            return rect

        if width <= 0 or height <= 0:
            return rect

        img_width = self.image.width
        img_height = self.image.height
        scale_x = img_width / width
        scale_y = img_height / height
        left = rect[0] * scale_x
        top = rect[1] * scale_y

        right_or_width = rect[2] * scale_x  # 若为ltrb模式, 则rect[2]表示right 否则表示width
        bottom_or_height = rect[3] * scale_y  # 若为ltrb模式, 则rect[3]表示bottom 否则表示height

        result_rect = [left, top, right_or_width, bottom_or_height]
        CommonUtil.printLog(
            f'resize_rect image_w,h={img_width},{img_height}, target_w,h={width},{height}'
            f',scale_x,y={scale_x:.2f},{scale_y:.2f}'
            f',rect={rect} -> {result_rect}')
        return result_rect

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
            CommonUtil.printLog("crop fail:未加载图像")
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
                CommonUtil.printLog("crop fail:裁剪坐标无效")
                return self
        except Exception as e:
            CommonUtil.printLog(f"crop fail:{e}")
            return self

    def draw_text(self, text, position: Tuple[float, float], font_path=None, font_size=20, color=(0, 0, 0),
                  align='left', vertical_align='top') -> Self:
        """
        在图像上绘制文字，支持水平和垂直对齐

        Args:
            text (str): 要绘制的文字
            position (tuple): 文字参考位置 (x, y)
            font_path (str, optional): 字体文件路径
            font_size (int, optional): 字体大小，默认20
            color (tuple, optional): 文字颜色，默认黑色
            align (str): 水平对齐方式 ('left', 'middle','center', 'right'), 默认 'left'
            vertical_align (str): 垂直对齐方式 ('top', 'middle','center', 'bottom'), 默认 'top'

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            CommonUtil.printLog("draw_text fail:未加载图像")
            return self

        try:
            draw = ImageDraw.Draw(self.image)
            font = self.load_font(font_path, font_size)
            # 获取文字的包围盒
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # 计算最终的文字位置
            final_x = position[0]
            final_y = position[1]

            # 水平对齐处理
            if align == 'center' or align == 'middle':
                final_x -= text_width // 2
            elif align == 'right':
                final_x -= text_width

            # 垂直对齐处理
            if vertical_align == 'center' or vertical_align == 'middle':
                final_y -= text_height // 2
            elif vertical_align == 'bottom':
                final_y -= text_height

            draw.text((final_x, final_y), text, font=font, fill=color)
            return self
        except Exception as e:
            CommonUtil.printLog(f"draw_text fail:{e}")
            return self

    def load_font(self, font_path: str = None, font_size: int = 20) -> ImageFont:
        if self._font_path == font_path and self._font is not None:
            return self._font

        # 尝试加载指定字体，失败则尝试查找系统中文字体
        try:
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                # 尝试自动查找系统中的中文字体
                system_font = CommonUtil.find_system_chinese_font()
                if system_font:
                    font = ImageFont.truetype(system_font, font_size)
                else:
                    # 如果找不到中文字体，使用默认字体并给出警告
                    CommonUtil.printLog("警告: 未找到支持中文的字体，可能会出现乱码")
                    font = ImageFont.load_default()
        except Exception as e:
            CommonUtil.printLog(f"load_font fail:{e}")
            font = ImageFont.load_default()

        self._font_path = font_path
        self._font = font
        return font

    def draw_multi_rectangle(self, multi_rect: list, ltrb: bool = True,
                             width: float = 0, height: float = 0,
                             outline_color=(255, 0, 0),
                             fill_color=None,
                             border_width=3) -> Self:
        """
        一次性绘制多个矩形框
        :param multi_rect: 多个矩形框坐标, 每个元素也是个列表, 支持两种含义: (left, top, right, bottom) 或者 (left,top,width,height), 但所有元素必须是同一种含义
        :param ltrb:  元素是否表示左上右下坐标  若为false,则表示: left,top,width,height
        :pram width: 目标宽度, 正数有效. 会根据实际图像大小对矩形框坐标进行缩放
        :param height: 目标高度, 正数有效
        """
        for rect in multi_rect:
            self.draw_rectangle(self.resize_rect(rect, width, height), ltrb, outline_color, fill_color, border_width)
        return self

    def draw_rectangle(self, position: list, ltrb: bool = True, outline_color=(255, 0, 0), fill_color=None, border_width=3) -> Self:
        """
        在图像上绘制矩形框

        Args:
            position (list): 矩形位置 (left, top, right, bottom) 或者 (left,top,width,height)
            ltrb(bool): position是否表示左上右下坐标  若为false,则表示: left,top,width,height
            outline_color (tuple, optional): 边框颜色，默认红色
            fill_color (tuple, optional): 填充颜色，默认无填充
            border_width (int, optional): 边框宽度，默认2

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            CommonUtil.printLog("draw_rectangle fail:未加载图像")
            return self

        if ltrb:
            pos = tuple(position)
        else:
            pos = (position[0], position[1], position[0] + position[2], position[1] + position[3])

        try:
            draw = ImageDraw.Draw(self.image)
            draw.rectangle(pos, outline=outline_color, fill=fill_color, width=border_width)
            return self
        except Exception as e:
            CommonUtil.printLog(f"draw_rectangle fail:{e}")
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
            CommonUtil.printLog("draw_circle fail:未加载图像")
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
            CommonUtil.printLog(f"draw_circle fail:{e}")
            return self

    def save(self, output_path) -> Self:
        """
        保存处理后的图像

        Args:
            output_path (str): 输出文件路径

        Returns:
            bool: 保存成功返回True，失败返回False
        """
        ImageUtil.save_img(output_path, self.image)
        return self

    def show(self) -> Self:
        """
        显示处理后的图像

        Returns:
            self: 返回实例本身以支持链式调用
        """
        if not self.image:
            CommonUtil.printLog("save fail:未加载图像")
            return self

        try:
            self.image.show()
            return self
        except Exception as e:
            CommonUtil.printLog(f"save fail:{e}")
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
            CommonUtil.printLog("reset fail:没有原始图像可供重置")
            return self

    @staticmethod
    def merge_images(image_dir: str, rows: int = 1, cols=None, single_column: bool = False, bg_color: str = "white", keep_original_size: bool = True) -> Optional[Image.Image]:
        """
        将指定目录下的所有图片,合并成一张大图
        Args:
            image_dir (str): 图片目录路径
            rows (int): 行数，默认为1
            cols (int): 列数，默认为None（根据行数自动计算）
        """
        # 获取目录下所有图片文件
        image_files = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if
                       f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            print('No images found in the directory.')
            return None

        # 提取文件名并排序（按字典顺序升序）
        image_files.sort(key=lambda x: os.path.basename(x))
        images = [Image.open(f) for f in image_files]

        # 处理单列模式：强制1列，行数等于图片数量
        if single_column:
            cols = 1
            rows = len(images)
        else:
            # 如果未指定列数，则根据行数计算
            if cols is None:
                cols = len(images) // rows if len(images) % rows == 0 else len(images) // rows + 1

        # 如果不需要保持原始尺寸，则将所有图片缩放到相同大小
        if not keep_original_size:
            # 计算所有图片的平均宽度和高度，作为统一大小
            avg_width = sum(img.width for img in images) // len(images)
            avg_height = sum(img.height for img in images) // len(images)

            # 缩放所有图片
            scaled_images = []
            for img in images:
                scaled_img = img.resize((avg_width, avg_height))
                scaled_images.append(scaled_img)
            images = scaled_images

            # 设置列宽和行高为统一大小
            col_widths = [avg_width] * cols
            row_heights = [avg_height] * rows
        else:
            # 计算每一行和每一列的最大宽度和高度
            # 为每行每列创建列表存储宽高
            row_heights = [0] * rows
            col_widths = [0] * cols

            # 计算每行每列的最大宽高
            for i, img in enumerate(images):
                r = i // cols
                c = i % cols
                row_heights[r] = max(row_heights[r], img.height)
                col_widths[c] = max(col_widths[c], img.width)

        # 计算结果图片的总宽度和总高度
        total_width = sum(col_widths)
        total_height = sum(row_heights)

        # 创建结果图片，背景色为指定颜色
        result = Image.new('RGB', (total_width, total_height), color=bg_color)

        # 拼接图片，保持原始尺寸，并在需要时填充空白
        current_y = 0
        for r in range(rows):
            current_x = 0
            for c in range(cols):
                img_index = r * cols + c
                if img_index < len(images):
                    img = images[img_index]
                    # 计算居中位置（可选，如果需要居中的话）
                    # x_offset = current_x + (col_widths[c] - img.width) // 2
                    # y_offset = current_y + (row_heights[r] - img.height) // 2
                    # 使用左上角对齐（不居中）
                    x_offset = current_x
                    y_offset = current_y
                    result.paste(img, (x_offset, y_offset))
                current_x += col_widths[c]
            current_y += row_heights[r]
        return result

    @staticmethod
    def save_img(output_path, image: Image = None) -> bool:
        """
        保存处理后的图像

        Args:
            output_path (str): 输出文件路径
            image (Image, optional): 要保存的图像对象，如果未提供则保存当前图像

        Returns:
            bool: 保存成功返回True，失败返回False
        """
        if not image:
            CommonUtil.printLog("save fail:未加载图像")
            return False

        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            image.save(output_path)
            CommonUtil.printLog(f"save success,path={output_path}")
            return True
        except Exception as e:
            CommonUtil.printLog(f"save fail:{e}")
            return False


# 使用示例
if __name__ == "__main__":
    # 创建处理器实例
    img_path = r"H:\Pictures\拯救姬.jpg"
    processor = ImageUtil()
    width = 800
    height = 600

    # 示例操作：打开图像、缩放、裁剪、绘制内容、保存和显示
    (processor.open_image(img_path)
     .resize(width, height)
     .crop(100, 100, 700, 500)
     .draw_text("示例文字", (50, 50), font_size=30, color=(255, 0, 0))
     .draw_rectangle([150, 150, 450, 350], outline_color=(0, 255, 0), border_width=3)
     # .draw_multi_rectangle([[300, 300, 380, 380], [400, 400, 450, 450]],
     #                       ltrb=True, width=width, height=height, outline_color=(255, 0, 0))
     .draw_circle((400, 200), 50, outline_color=(0, 0, 255), width=2)
     # .crop(100, 100, 700, 500)
     .show()
     .save(f'H:\Pictures\拯救姬_1111.jpg')
     )
