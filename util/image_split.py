import os
from PIL import Image

from util.FileUtil import FileUtil

"""
裁剪图片为指定行数和列数的小图片
"""


def crop_image(image_path: str, rows: int, cols: int) -> list:
    """
    裁剪图片为指定行数和列数的小图片
    :param image_path: 图片路径
    :param rows: 行数
    :param cols: 列数
    :return: 裁剪后的小图片列表
    """
    # 打开图片
    img = Image.open(image_path)
    width, height = img.size

    # 计算每个小图片的宽度和高度
    piece_width = width // cols
    piece_height = height // rows

    # 裁剪图片
    _pieces = []
    for i in range(rows):
        for j in range(cols):
            left = j * piece_width
            upper = i * piece_height
            right = left + piece_width
            lower = upper + piece_height
            _piece = img.crop((left, upper, right, lower))
            _pieces.append(_piece)
    return _pieces


if __name__ == '__main__':
    cur_dir_path = os.path.dirname(os.path.abspath(__file__))
    image_path = input('请输入要裁剪的图片路径(默认会列出脚本所在目录下的图片): ')
    if not image_path:
        image_path = cur_dir_path

    if FileUtil.isDirFile(image_path):
        # 若用户未输入路径，列出脚本所在目录下的所有图片供用户选择
        image_files = [f for f in os.listdir(image_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            print('未在默认目录找到图片文件，请重新输入有效路径')
            exit(1)

        for i, file in enumerate(image_files, start=1):
            print(f"{i}. {file}")

        while True:
            try:
                choice = int(input("请输入要选择的图片序号: "))
                if 1 <= choice <= len(image_files):
                    image_path = os.path.join(image_path, image_files[choice - 1])
                    break
                else:
                    print("输入的序号无效，请输入有效的序号")
            except ValueError:
                print("输入不是有效的整数，请输入有效的序号")

    try:
        rows = int(input('请输入要裁剪的行数(默认2): ') or '2')
        cols = int(input('请输入要裁剪的列数(默认2): ') or '2')
    except ValueError:
        print('输入的行数或列数不是有效的整数，请重新运行并输入正确的值')
        exit(1)

    img_name = os.path.basename(image_path)
    arr = os.path.splitext(img_name)
    img_name = arr[0]  # 不带后缀名的图片名称
    print(f'img_name={img_name}')
    print(f'image_path={image_path}')

    # 创建保存裁剪后图片的目录
    output_dir_name = f'cropped_{img_name}'
    output_dir = os.path.join(os.path.dirname(image_path), output_dir_name)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 保存裁剪后的小图片
    pieces = crop_image(image_path, rows, cols)
    for i, piece in enumerate(pieces):
        piece.save(os.path.join(output_dir, f'piece_{i}.png'))
    print(f'图片裁剪完成，裁剪后的小图片已保存到 {output_dir_name} 目录')
