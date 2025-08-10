import os
from PIL import Image


def merge_images(image_dir, rows=1, cols=None, single_column=False):  # 新增 single_column 参数
    # 获取目录下所有图片文件
    image_files = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if
                   f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not image_files:
        print('No images found in the directory.')
        return None
    
    # 提取文件名并排序（按字典顺序升序）
    image_files.sort(key=lambda x: os.path.basename(x))
    images = [Image.open(f) for f in image_files]

    # 计算最大宽度和高度
    max_width = max(img.width for img in images)
    max_height = max(img.height for img in images)

    # 缩放所有图片
    scaled_images = []
    for img in images:
        scaled_img = img.resize((max_width, max_height))
        scaled_images.append(scaled_img)

    # 处理单列模式：强制1列，行数等于图片数量
    if single_column:
        cols = 1
        rows = len(scaled_images)
    else:
        # 如果未指定列数，则根据行数计算
        if cols is None:
            cols = len(scaled_images) // rows if len(scaled_images) % rows == 0 else len(scaled_images) // rows + 1

    # 创建拼接后的图片
    result_width = cols * max_width
    result_height = rows * max_height
    result = Image.new('RGB', (result_width, result_height), color="white") # 背景为白色

    # 拼接图片
    for i in range(len(scaled_images)):
        x = (i % cols) * max_width
        y = (i // cols) * max_height
        result.paste(scaled_images[i], (x, y))

    return result


if __name__ == '__main__':
    cur_dir_path = os.path.dirname(os.path.abspath(__file__))
    image_dir = input('请输入图片所在目录路径(默认是本脚本所在目录): ') or cur_dir_path

    # 新增：询问是否使用单列模式
    single_col_input = input('是否使用单列模式（将所有图片合并成一列）？(y/n, 默认n): ').strip().lower()
    single_column = single_col_input == 'y'

    # 若启用单列模式，无需输入行数；否则按原逻辑获取行数
    if not single_column:
        try:
            rows = int(input('请输入拼图行数(默认1): ') or 1)
        except ValueError:
            rows = 1
    else:
        rows = 0  # 单列模式下行数由图片数量决定，此处仅占位

    # 调用 merge_images 时传入单列模式参数
    merged_image = merge_images(image_dir, rows=rows, single_column=single_column)

    if merged_image:
        try:
            merged_image.save(f'{image_dir}/merged_image.jpg')
            print('Image merging completed. The merged image has been saved as merged_image.jpg.')
        except Exception as e:
            print(f'An error occurred while saving the image: {e}')
    else:
        print('Image merging failed.')
