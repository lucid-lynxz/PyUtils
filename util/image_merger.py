import os
from PIL import Image


def merge_images(image_dir, rows=1, cols=None):
    # 获取目录下所有图片文件
    image_files = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if
                   f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not image_files:
        print('No images found in the directory.')
        return None
    images = [Image.open(f) for f in image_files]

    # 计算最大宽度和高度
    max_width = max(img.width for img in images)
    max_height = max(img.height for img in images)

    # 缩放所有图片
    scaled_images = []
    for img in images:
        scaled_img = img.resize((max_width, max_height))
        scaled_images.append(scaled_img)

    # 如果未指定列数，则根据行数计算
    if cols is None:
        cols = len(scaled_images) // rows if len(scaled_images) % rows == 0 else len(scaled_images) // rows + 1

    # 创建拼接后的图片
    result_width = cols * max_width
    result_height = rows * max_height
    result = Image.new('RGB', (result_width, result_height))

    # 拼接图片
    for i in range(len(scaled_images)):
        x = (i % cols) * max_width
        y = (i // cols) * max_height
        result.paste(scaled_images[i], (x, y))

    return result


if __name__ == '__main__':
    cur_dir_path = os.path.dirname(os.path.abspath(__file__))
    image_dir = input('请输入图片所在目录路径(默认是本脚本所在目录): ') or cur_dir_path
    try:
        rows = int(input('请输入拼图行数(默认1): ') or 1)
    except ValueError:
        rows = 1
    merged_image = merge_images(image_dir, rows)
    if merged_image:
        try:
            merged_image.save(f'{image_dir}/merged_image.jpg')
            print('Image merging completed. The merged image has been saved as merged_image.jpg.')
        except Exception as e:
            print(f'An error occurred while saving the image: {e}')
    else:
        print('Image merging failed.')
