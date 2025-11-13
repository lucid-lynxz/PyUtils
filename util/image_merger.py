import os
from PIL import Image


def merge_images(image_dir, rows=1, cols=None, single_column=False, bg_color="white", keep_original_size=True):
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
    # 使用 RGBA 模式来正确处理透明度
    result = Image.new('RGBA', (total_width, total_height), color=bg_color)

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
                # 正确处理透明度：如果图片有透明度信息则使用 alpha 通道
                if img.mode == 'RGBA' or 'transparency' in img.info:
                    result.paste(img, (x_offset, y_offset), img)
                else:
                    result.paste(img, (x_offset, y_offset))
            current_x += col_widths[c]
        current_y += row_heights[r]

    # 转换为 RGB 模式（如果需要的话）并返回
    return result.convert('RGB')


if __name__ == '__main__':
    cur_dir_path = os.path.dirname(os.path.abspath(__file__))
    image_dir = input('请输入图片所在目录路径(默认是本脚本所在目录): ') or cur_dir_path

    # 询问是否使用单列模式
    single_col_input = input('是否使用单列模式（将所有图片合并成一列）？(y/n, 默认n): ').strip().lower()
    single_column = single_col_input == 'y'

    # 询问是否保持原始尺寸
    keep_original_size_input = input('是否保持图片原始尺寸？(y/n, 默认n): ').strip().lower()
    keep_original_size = keep_original_size_input == 'y'  # 默认保持原始尺寸

    # 若启用单列模式，无需输入行数；否则按原逻辑获取行数
    if not single_column:
        try:
            rows = int(input('请输入拼图行数(默认1): ') or 1)
        except ValueError:
            rows = 1
    else:
        rows = 0  # 单列模式下行数由图片数量决定，此处仅占位

    # 调用 merge_images 时传入单列模式参数
    merged_image = merge_images(image_dir, rows=rows, single_column=single_column, keep_original_size=keep_original_size)

    if merged_image:
        try:
            merged_image.save(f'{image_dir}/merged_image.png')
            print('Image merging completed. The merged image has been saved as merged_image.jpg.')
        except Exception as e:
            print(f'An error occurred while saving the image: {e}')
    else:
        print('Image merging failed.')