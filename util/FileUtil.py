# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import csv
import os
import platform
import re
import shutil
from typing import Optional, List, Type, TypeVar, Union, Dict

import numpy as np
import pandas as pd

from util.CommonUtil import CommonUtil

T = TypeVar('T')  # 泛型类型


class FileUtil(object):
    @staticmethod
    def rename(src: str, dst: str) -> bool:
        """
        重命名文件或目录
        :param src: 源文件或目录路径
        :param dst: 目标文件或目录路径
        :return: 是否重命名成功
        """
        if not FileUtil.isFileExist(src):
            CommonUtil.printLog(f'重命名失败: 源文件或目录不存在:{src}')
            return False

        try:
            os.rename(src, dst)
            return True
        except (OSError, EnvironmentError) as reason:
            CommonUtil.printLog(f'重命名失败: {reason} , 原目录为:{src}')
            return False

    @staticmethod
    def recookPath(path: str, forceEnableLongPath: bool = False, replaceBlank: str = None, replaceBackSlash: bool = True) -> str:
        """
        路径字符串处理: 替换 反斜杠 为 斜杠
        :param path: 路径字符串, 支持绝对路径和部分相对路径等特殊格式, 比如: './a.txt'  '../b.txt'  '~/c.txt'
        :param forceEnableLongPath: win下是否强制启用长目录路径格式
        :param replaceBlank: 回车空格字符要替换为指定的值, None表示不处理
        :param replaceBackSlash: 是否将反斜杠替换为斜杠
        :return: 处理后的路径,为避免空指针,返回值均为非None
        """
        if CommonUtil.isNoneOrBlank(path):
            return ''

        if path.startswith("~"):
            path = '%s%s' % (os.path.expanduser("~"), path[1:])
            return FileUtil.recookPath(path)

        # 以点开头的路径,扩展为实际路径,并恢复结尾可能存在的斜杠符号
        if path.startswith('.'):
            last_ele = path[-1]
            path = os.path.abspath(path)
            if not path.endswith('/') and last_ele in ['/', '\\']:
                path = path + last_ele

        if replaceBackSlash:
            path = path.replace('\\', '/')
        path = path.replace("//", "/")

        if replaceBlank is not None:
            path = path.replace(' ', replaceBlank).replace('\n', replaceBlank)

        # win最大文件长度: https://learn.microsoft.com/zh-cn/windows/win32/fileio/naming-a-file?redirectedfrom=MSDN#maxpath
        if forceEnableLongPath or len(path) >= 256:
            if platform.system() == 'Windows':
                path = '\\\\?\\' + os.path.abspath(path)
        return path

    @staticmethod
    def getParentPath(path: str, level: int = 1) -> str:
        """
        获取父目录路径
        如输入: /x/y/z.txt 则:
         level=1 时, 返回: /x/y/
         level=2 时, 返回: /x/
         level=3 时, 返回: /
         level>=4 时, 仍是返回: /
         :param path: 原路径
         :param level: 返回第几级父目录路径,如1表示返回上一级目录
        """
        pPath = FileUtil.recookPath(path).rstrip('/')
        for index in range(level):
            try:
                pPath = os.path.dirname(pPath)
            except Exception as e:
                CommonUtil.printLog('getParentPath error: %s' % e)
        return FileUtil.recookPath('%s/' % pPath)

    @staticmethod
    def getFileSize(filePath: str) -> tuple:
        """
        获取文件大小, 返回tuple(int,str) 依次表示字节数和带单位的字符串描述,如 1024,1K
        """
        fsize = os.path.getsize(filePath)  # 返回的是字节大小
        return fsize, FileUtil.format_size(fsize)

    @staticmethod
    def format_size(size_bytes) -> str:
        """将所给字节数转换为带单位的字符串, 支持B/K/M/G/T, 最多保留2位小数"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    @staticmethod
    def format_speed(speed_bps):
        """将每秒下载的直接数, 转为 B/s, KB/s 或 MB/S , 最多保留2位小数"""
        if speed_bps < 1024:
            return f"{speed_bps:.2f} B/s"
        speed_kbps = speed_bps / 1024
        if speed_kbps < 1024:
            return f"{speed_kbps:.2f} KB/s"
        else:
            return f"{speed_kbps / 1024:.2f} MB/s"

    @staticmethod
    def getDirSize(dirPath: str, depth: int = 10, includeDirSelf: bool = False) -> tuple:
        """
        统计目录大小(包括子目录文件)
        :param depth: 统计深度
        :param includeDirSelf:是否统计文件夹本身的大小,默认不统计
        :return: tuple(int,str) 依次表示字节数和带单位的可读结果, B/K/M/G
        """
        allSubFiles = FileUtil.listAllFilePath(dirPath, depth=depth, getAllDepthFileInfo=True)
        allByteSize = 0
        for subFilePath in allSubFiles:
            if not includeDirSelf and FileUtil.isDirFile(subFilePath):
                continue
            byteSize, _ = FileUtil.getFileSize(subFilePath)
            allByteSize = allByteSize + byteSize
        return allByteSize, FileUtil.format_size(allByteSize)

    @staticmethod
    def isFileExist(path: str) -> bool:
        """
        文件是否存在
        :param path: 文件路径
        :return: bool
        """
        path = FileUtil.recookPath(path)
        return not CommonUtil.isNoneOrBlank(path) and os.path.exists(path)

    @staticmethod
    def isDirFile(path: str) -> bool:
        """
        文件是否是目录
        :param path: 文件路径
        :return: False-若文件不存在或者非目录
        """
        path = FileUtil.recookPath(path)
        return FileUtil.isFileExist(path) and os.path.isdir(path)

    @staticmethod
    def isDirPath(path: str) -> bool:
        """
        判断指定路径是否表示一个目录, 以是否以文件分隔符结尾来判断
        不考虑文件是否存在
        :param path:
        :return:
        """
        path = FileUtil.recookPath(path)
        # return path.endswith(os.sep)
        return path.endswith("/") or path.endswith("\\")

    @staticmethod
    def copy(src: str, dst: str):
        """
        复制文件到指定位置
        :param src: 源文件, 要求文件存在, 若是目录, 则 dst 也必须是目录, 且目录本身不会复制
        :param dst: 目标位置
        """
        if not FileUtil.isFileExist(src):
            return

        src = FileUtil.recookPath(src)
        dst = FileUtil.recookPath(dst)

        if FileUtil.isDirFile(src):  # 目录, 递归复制
            # 由于 src 为目录时, dst也必须是目录
            # 且shutil复制目录要求dst不存在, 因此需要遍历进行普通文件复制
            if FileUtil.isFileExist(dst):
                for fileItem in FileUtil.listAllFilePath(src):
                    fileName, _, _ = FileUtil.getFileName(fileItem)
                    if FileUtil.isDirFile(fileItem):
                        FileUtil.copy(fileItem, FileUtil.recookPath('%s/%s/' % (dst, fileName)))
                    else:
                        shutil.copy(fileItem, FileUtil.recookPath('%s/%s' % (dst, fileName)))
            else:
                shutil.copytree(src, dst)  # dst目录不存在时, 直接使用copytree复制即可
            pass
        else:  # 普通文件, 直接复制
            shutil.copy(src, dst)

    @staticmethod
    def deleteFile(path: str, printLog: bool = False):
        """
        删除文件
        :param path: 文件路径
        :param printLog: 是否打印日志
        :return:
        """
        path = FileUtil.recookPath(path)
        if FileUtil.isFileExist(path):
            CommonUtil.printLog(f"deleteFile path={path}", printLog)
            if FileUtil.isDirFile(path):  # 目录
                try:
                    shutil.rmtree(path)
                    # os.rmdir(path) # 非空目录会报错: WindowsError：[Error 145]
                except WindowsError:
                    # 对于超长路径,会提示 FileNotFoundError: [WinError 3]
                    if len(path) >= 256:
                        path = FileUtil.recookPath(path, True)
                        shutil.rmtree(path)
            else:  # 文件
                os.remove(path)

    @staticmethod
    def moveFile(src: str, dst: str) -> bool:
        """
        移动文件到指定目录
        :param src: 源文件(或目录)路径
        :param dst: 目标位置目录路径
        :return: 是否移动成功
        """
        if not FileUtil.isFileExist(src):
            CommonUtil.printLog('移动文件失败：源文件不存在 %s' % src)
            return False
        try:
            shutil.move(src, dst)
            return True
        except (OSError, EnvironmentError) as reason:
            CommonUtil.printLog('移动文件失败：%s' % reason)
            return False

    @staticmethod
    def get_sub_file_names(folderPath: str, extensions: list) -> list:
        """
        获取指定目录下包含特定后缀的文件名
        :param folderPath: 目录路径
        :param extensions: 允许包含的扩展名,如: ['.xlsx', '.xls', '.txt']
        """
        # 获取目录下的所有文件
        all_files = os.listdir(folderPath)
        # 筛选出指定扩展名的文件
        return [file for file in all_files if any(file.endswith(ext) for ext in extensions)]

    @staticmethod
    def listAllFilePath(folderPath: str, depth: int = 1, curDepth: int = 0,
                        getAllDepthFileInfo: bool = False, *path_filters) -> list:
        """
        获取指定层级目录下所有文件的绝对路径
        若目录不存在,则返回空数据
        :param folderPath: 目录路径
        :param depth: 递归遍历的深度,默认为一级, 即只获取 folderPath 的下一级子文件
        :param curDepth: 当前目录(folderPath)所在层级
        :param getAllDepthFileInfo: 是否返回所有层级的文件路径, 默认False
                True表示只要不大于depth指定的层级文件均要添加到结果列表中
                False表示仅返回curDepth=depth的文件
        :param path_filters 文件路径过滤函数,可多个
        :return: 结果列表
        """
        folderPath = FileUtil.recookPath(folderPath)
        result = list()
        if FileUtil.isDirFile(folderPath):
            subFiles = os.listdir(folderPath)  # 返回的是子文件的相对路径
            curDepth = curDepth + 1
            for sub in subFiles:
                subPath = FileUtil.recookPath(os.path.join(folderPath, sub))  # 子文件路径
                if FileUtil.isDirFile(subPath) and curDepth < depth:  # 子文件是目录, 则递归遍历
                    if getAllDepthFileInfo:
                        result.append(subPath)
                    subList = FileUtil.listAllFilePath(subPath, depth, curDepth, getAllDepthFileInfo, *path_filters)
                    for reSubFile in subList:
                        result.append(reSubFile)
                else:  # 文件,则记录绝对路径
                    result.append(subPath)
        if path_filters is not None:
            for path_filter in path_filters:
                result = list(filter(path_filter, result))
        return result

    @staticmethod
    def isDirEmpty(path: str) -> bool:
        """判断目录是否为空(目录不存在或者path表示普通文件时,也都返回True)"""
        return CommonUtil.isNoneOrBlank(FileUtil.listAllFilePath(path))

    @staticmethod
    def getFileName(path: str, autoRecookPath: bool = True) -> tuple:
        """
        根据所给文件名或者文件路径,去除目录信息后, 得到文件名和扩展名, 如输入 a.txt 返回 ("a.txt","a","txt")
        若当前就以斜杠结尾,则先删除斜杠
        :param path: 文件名或者路径
        :param autoRecookPath: 是否需要对路径进行格式化(反斜杠转为斜杠等),默认true
        :return: tuple (fileName+ext, fileName, ext)
        """
        if autoRecookPath:
            path = FileUtil.recookPath(path)
        if path.endswith('/'):  # 目录路径则提取目录名信息
            # CommonUtil.printLog("getFileName oriPath=%s, curPath=%s" % (path, path[:-1]))
            path = path[:-1]
        fileName = os.path.basename(path)
        arr = os.path.splitext(fileName)
        return fileName, arr[0], arr[1][1:]  # 剔除掉扩展名中的点符号

    @staticmethod
    def makeDir(folder_path: str):
        """
        若指定的目录不存在,则递归创建
        :param folder_path: 要创建的目录路径
        """
        folder_path = FileUtil.recookPath(folder_path)
        if os.path.exists(folder_path) and not os.path.isdir(folder_path):
            CommonUtil.printLog("makeDir() 文件已存在但并非目录, 进行删除: %s" % folder_path)
            os.remove(folder_path)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

    @staticmethod
    def createFile(path: str, recreateIfExist: bool = False) -> bool:
        """
        创建文件
        :param path: 文件路径,若为"/" 或 "\\" 结尾,则表示目录
        :param recreateIfExist: 若目标文件已存在, 是否要删除重建,默认false
        :return:
        """
        path = FileUtil.recookPath(path)
        # 创建文件, 若文件存在,但为目录,则先删除
        if FileUtil.isDirFile(path) and recreateIfExist:
            FileUtil.deleteFile(path)

        if FileUtil.isDirPath(path):  # 创建目录
            if not FileUtil.isDirFile(path):
                os.makedirs(path)
                return True
        else:
            # 按需创建父目录
            parentPath = FileUtil.recookPath('%s/' % os.path.dirname(path))
            if not FileUtil.isDirFile(parentPath):
                os.makedirs(parentPath)

            # 创建文件
            try:
                with open(path, "w" if recreateIfExist else "a") as f:
                    f.close()
                return True
            except Exception as e:
                CommonUtil.printLog(f"createFile fail path={path}, err:${e}")
                return False

    @staticmethod
    def write2File(path: str, msg: str, encoding='utf-8',
                   autoAppendLineBreak: bool = True,
                   enableEmptyMsg: bool = False) -> bool:
        """
        写入信息到指定文件中,若文件不存在则自动创建,若文件已存在,则覆盖内容
        :param path: 文件路径
        :param msg: 要写入的信息
        :param encoding: 编码, 默认:utf-8
        :param autoAppendLineBreak: msg行尾不包含换行符时, 是否自动在行尾追加一个换行符
        :param enableEmptyMsg: 是否允许msg为空白内容
        :return: 是否写入成功
        """
        path = FileUtil.recookPath(path)
        return FileUtil.__wirte2FileInnner(path, msg, False, encoding, autoAppendLineBreak,
                                           enableEmptyMsg=enableEmptyMsg)

    @staticmethod
    def append2File(path: str, msg: str, encoding='utf-8',
                    autoAppendLineBreak: bool = True,
                    enableEmptyMsg: bool = False) -> bool:
        """
        写入信息到指定文件中,若文件不存在则自动创建,若文件已存在,则覆盖内容
        :param path: 文件路径
        :param msg: 要写入的信息
        :param encoding: 编码
        :param autoAppendLineBreak: msg行尾不包含换行符时, 是否自动在追加一个换行符
        :return: 是否写入成功
        """
        path = FileUtil.recookPath(path)
        return FileUtil.__wirte2FileInnner(path, msg, True, encoding, autoAppendLineBreak,
                                           enableEmptyMsg=enableEmptyMsg)

    @staticmethod
    def __wirte2FileInnner(path: str, msg: str, append: bool, encoding='utf-8',
                           autoAppendLineBreak: bool = True,
                           enableEmptyMsg: bool = False) -> bool:
        """
        :param enableEmptyMsg: 是否允许写入空白内容,默认 False
        """
        path = FileUtil.recookPath(path)
        if not enableEmptyMsg and CommonUtil.isNoneOrBlank(msg):
            return False

        if autoAppendLineBreak and not msg.endswith("\n"):
            msg = '%s\n' % msg

        FileUtil.createFile(path, recreateIfExist=False)
        if FileUtil.isDirFile(path):
            CommonUtil.printLog("append2File fail as %s is a folder" % path)
            return False

        with open(path, "a" if append else "w", encoding=encoding) as f:
            f.write(msg)
            f.close()
        return True

    @staticmethod
    def readFile(path: str, encoding='utf-8') -> list:
        """
        读取给定路径的文件,返回所有放信息
        :param path: 文件路径(目录无效)
        :param encoding: 读取时使用的编码,默认为: utf-8
        :return: list
        """
        path = FileUtil.recookPath(path)
        lines = []
        if not FileUtil.isFileExist(path) \
                or FileUtil.isDirFile(path):
            return lines

        with open(path, "r", encoding=encoding) as f:
            lines = f.readlines()
        return lines

    @staticmethod
    def openDir(path: str):
        system = platform.system()
        if system == 'Windows':
            # cmd = CommonUtil.changeSep('start %s' % picFolder)
            cmd = CommonUtil.changeSep('explorer.exe %s' % path)
        else:
            cmd = CommonUtil.changeSep('open %s' % path)
        CommonUtil.exeCmd(cmd, printCmdInfo=False)

    @staticmethod
    def absPath(path: str) -> str:
        return os.path.abspath(path)

    @staticmethod
    def deleteEmptyDirsRecursively(path: str):
        """
        递归删除所有空白目录
        :param path: 要删除的空白目录的根路径
        """
        path = FileUtil.recookPath(path)
        if not FileUtil.isDirFile(path):
            return
        elif FileUtil.isDirEmpty(path):
            FileUtil.deleteFile(path, True)
            return

        # 递归地删除其下的空白子目录
        for subDir in os.listdir(path):
            subDirFullPath = os.path.join(path, subDir)

            # 如果是一个子目录，递归调用自身
            if FileUtil.isDirFile(subDirFullPath):
                FileUtil.deleteEmptyDirsRecursively(subDirFullPath)

        # 在确认所有子目录都被处理之后，再次检查当前目录是否空白, 若是,则删除
        if FileUtil.isDirEmpty(path):
            FileUtil.deleteFile(path, True)

    @staticmethod
    def copyImage(image_path: str):
        """将图片保存到系统剪贴板的函数"""
        # pip install pillow pywin32
        if not CommonUtil.is_library_installed(["PIL"]):
            CommonUtil.printLog("copyImage fail: 请先安装 pillow 库")
            return
        import subprocess
        from io import BytesIO
        from PIL import Image
        image = Image.open(image_path)

        if CommonUtil.isWindows():
            if not CommonUtil.is_library_installed("win32clipboard"):
                CommonUtil.printLog("copyImage fail: 请先安装 pywin32 库")
                return

            try:
                import win32clipboard
            except ImportError:
                return

            # Windows 系统
            output = BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
        elif CommonUtil.isMacOS():
            # macOS 系统
            image.save("temp_image.png", "PNG")
            subprocess.run(['pbcopy', '-Prefer', 'png'], input=open('temp_image.png', 'rb').read())
        elif CommonUtil.isLinux():
            # Linux 系统  sudo apt-get install xclip
            CommonUtil.printLog("copyImage请自行安装xclip库:sudo apt-get install xclip")
            image.save("temp_image.png", "PNG")
            subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', 'temp_image.png'])
        else:
            CommonUtil.printLog("copyImage fail: 不支持的操作系统")

    @staticmethod
    def delete_files(dir_path: str, patterns: list):
        """
        批量删除指定目录下包含特定内容的普通文件

        :param dir_path: 指定目录的路径
        :param patterns: 要匹配的正则表达式模式列表，例如 [r'^file\d+\.txt$', r'image.*\.jpg$']
        """
        if not FileUtil.isDirFile(dir_path):
            return

        # 获取目录下所有文件和文件夹
        all_entries = os.listdir(dir_path)

        # 遍历并删除符合正则表达式模式的文件
        for entry in all_entries:
            file_path = os.path.join(dir_path, entry)
            if FileUtil.isDirFile(file_path):
                continue  # 跳过目录

            for pattern in patterns:
                if re.match(pattern, entry):
                    FileUtil.deleteFile(file_path)
                    break

    @staticmethod
    def create_cache_dir(parent_dir: Optional[str], file_like: Union[str, os.PathLike] = None,
                         clear: bool = False, name: str = 'cache') -> str:
        """
        在指定目录下创建一个缓存子目录, 子目录名默认为:'cache', 会自动在里面添加 .gitignore 文件, 忽略所有文件
        :param parent_dir: 要在哪个目录下创建缓存目录, 若为空,则请传入 file_like = __file__
        :param file_like: 若 parent_dir 为空, 则以 file_like 所在目录为父目录
        :param clear: 若目录已存在, 是否先清空目录
        :param name: 缓存目录名, 默认: caches
        :return: 缓存目录路径
        """
        # 创建缓存目录路径
        if CommonUtil.isNoneOrBlank(parent_dir):
            current_file = os.path.abspath(file_like)  # 获取当前文件的绝对路径
            parent_dir = os.path.dirname(current_file)  # 获取文件所在目录

        cacheDir = os.path.join(parent_dir, f'{name}/')  # 构建缓存目录路径
        cacheDir = FileUtil.recookPath(cacheDir)
        if not clear and FileUtil.isDirFile(cacheDir):
            return cacheDir

        FileUtil.createFile(cacheDir, clear)
        gitignore_file = os.path.join(cacheDir, '.gitignore')  # 构建.gitignore文件路径
        FileUtil.write2File(gitignore_file, "*")  # 忽略所有文件

        return cacheDir

    @staticmethod
    def read_csv_to_objects(
            file_path: str,
            object_class: Type[T],
            skip_rows: int = 0,
            delimiter: str = ',',
            encoding: str = 'utf-8',
            skip_empty_line: bool = True,
            replace_dict: Optional[Dict[str, str]] = None
    ) -> List[T]:
        """
        读取CSV文件并转换为对象列表
        会跳过以 # 或 ; 开头的行
        skip_empty_line=True时, 还会跳过空白行
        泛型对象T中必须包含有一个函数:

        @classmethod
        def by_csv_row(cls, row: List[str]):
            pass

        参数:
        - file_path: CSV文件路径
        - object_class: 目标对象类（需实现 by_csv_row 方法）
        - skip_rows: 跳过的行数（默认为1，跳过标题行）
        - delimiter: 分隔符（默认为逗号）
        - encoding: 文件编码（默认为utf-8）
        - skip_empty_line: 是否跳过空行
        - replace_dict: 将指定的字符串替换为其他字符串的字典, 如: {'#': '#', ' ': ''}

        返回:
        - 对象列表
        """
        objects = []
        file_path = FileUtil.recookPath(file_path)
        if not FileUtil.isFileExist(file_path):
            return objects

        with open(file_path, 'r', encoding=encoding) as file:
            reader = csv.reader(file, delimiter=delimiter)

            # 跳过指定行数
            for _ in range(skip_rows):
                next(reader, None)

            # 逐行解析并转换为对象
            for row_num, row in enumerate(reader, start=skip_rows):
                if skip_empty_line and (not row or all(not cell.strip() for cell in row)):  # 跳过空行
                    continue

                if row[0].startswith('#') or row[0].startswith(';'):  # 跳过以 # 或 ; 开头的行
                    continue

                # 按需去除等号和空格, 将等号转为逗号,避免原内容中包含冒号时, 冒号会被识别为 key-value 的分隔符
                row_str = delimiter.join(row)
                ori_row_str = row_str
                if replace_dict:
                    for k, v in replace_dict.items():
                        row_str = row_str.replace(k, v)
                row = row_str.split(delimiter)

                try:
                    if '搜索历史记录' in row[0]:
                        print(f'搜索历史记录')
                    obj = object_class.by_csv_row(row)

                    obj.config_path = file_path
                    obj.row_number = row_num
                    obj.row_str = ori_row_str

                    objects.append(obj)
                except Exception as e:
                    print(f"警告: 第{row_num}行解析失败 - {e}. 行内容: {row},oriRowStr={row_str}")
                    # 可选择记录错误或跳过该行，此处选择跳过

        return objects

    @staticmethod
    def is_absolute_path(path: str) -> bool:
        """
        判断给定路径字符串是否为绝对路径
        :param path: 路径字符串
        :return: 如果是绝对路径返回True，相对路径返回False
        """
        return os.path.isabs(path)

    @staticmethod
    def extract_lines(src_path: str, line_ranges: List[Union[int, tuple]], encoding: str = 'utf-8', skip_empty_lines: bool = True) -> str:
        """
        从指定源文件中提取指定区域行的内容,并拼接成一个新字符串
        @param src_path: 源文件路径, 通常是txt或者csv文件, 默认使用utf-8编码
        @param line_ranges: 行范围列表，每个元素是一个元组 (start_line(含), end_line(含)  或单个行号, 行号从0开始
        @param encoding: 源文件编码
        @param skip_empty_lines: 是否在处理前跳过文件中的所有空白行, 默认为 True
        @return str: 提取出的内容
        """
        if not FileUtil.isFileExist(src_path):
            CommonUtil.printLog(f'extract_lines fail: 源文件不存在:{FileUtil.recookPath(src_path)}')
            return ""

        lines = FileUtil.readFile(src_path, encoding=encoding)
        # 根据参数决定是否过滤空白行
        if skip_empty_lines:
            # 使用列表推导式过滤掉只包含空白字符（如空格、制表符、换行符）的行
            lines = [line for line in lines if line.strip()]

        # 提取指定行范围的内容
        extracted_lines = []
        for line_range in line_ranges:
            if isinstance(line_range, int):
                # 单行提取
                line_index = line_range  # 转换为0基索引
                if 0 <= line_index < len(lines):
                    extracted_lines.append(lines[line_index])
            elif isinstance(line_range, tuple) and len(line_range) == 2:
                # 范围提取
                start_line, end_line = line_range
                start_index = start_line
                end_index = end_line

                # 确保索引在有效范围内
                start_index = max(0, start_index)
                end_index = min(len(lines) - 1, end_index)

                # 提取范围内的行
                if start_index <= end_index:
                    extracted_lines.extend(lines[start_index:end_index + 1])
            else:
                CommonUtil.printLog(f"无效的行范围格式: {line_range}")
                return ""
        return "".join(extracted_lines)

    @staticmethod
    def extract_csv(src_path: str, column_name: str, row_ranges: List[Union[int, tuple]] = None,
                    output_path: str = None, encoding: str = 'utf-8-sig',
                    remove_empty_row: bool = True,
                    process_func: Optional[callable] = None,
                    keyword: Optional[str] = None) -> pd.DataFrame:
        """
        从指定CSV文件中提取指定列的部分数据，并可选择保存为新的CSV文件
        参考 extract_lines() 方法实现
        兼容单个数据跨多行存储的情况(带有\n换行符), 能正确识别为str数据

        @param src_path: 源CSV文件路径
        @param column_name: 要提取的列名，例如 'query'
        @param row_ranges: 行范围列表，每个元素是一个元组 (start_row(含), end_row(含)) 或单个行号，行号从0开始(不包括column行)
                          默认为None，表示处理全部数据范围
        @param output_path: 输出CSV文件路径，如果提供则保存为新的CSV文件，默认为None不保存
        @param encoding: 源文件编码，默认为 'utf-8-sig'
        @param remove_empty_row: 是否删除空白行，默认为True
        @param process_func: 可选的处理函数，用于对每个row数据进行处理，函数签名应为 func(data: str) -> str
        @param keyword: 待提取列数据中需包含的关键字，默认为None，不进行过滤
        @return pd.DataFrame: 提取后的DataFrame
        """
        if not FileUtil.isFileExist(src_path):
            CommonUtil.printLog(f'extract_csv fail: 源文件不存在:{FileUtil.recookPath(src_path)}')
            return pd.DataFrame()

        try:
            # 读取CSV文件，使用 dtype=str 确保所有数据都作为字符串处理
            # keep_default_na=False 和 na_values=[''] 确保空值也被当作字符串处理
            # df = pd.read_csv(src_path, encoding=encoding, dtype=str, keep_default_na=False, na_values=[''])
            df = pd.read_csv(src_path, encoding=encoding, dtype=str)

            # 确保所有NaN值都被替换为空字符串
            df = df.fillna('')

            # 检查列是否存在
            if column_name not in df.columns:
                CommonUtil.printLog(f'extract_csv fail: 列 "{column_name}" 不存在于文件中')
                return pd.DataFrame()

            # 提取指定列
            extracted_df = df[[column_name]].copy()

            # 处理行范围筛选
            if row_ranges is None:
                # 如果row_ranges为None，则处理全部数据范围
                final_df = extracted_df.reset_index(drop=True)
            else:
                # 根据行范围筛选数据
                selected_indices = []
                for row_range in row_ranges:
                    if isinstance(row_range, int):
                        # 单行提取
                        if 0 <= row_range < len(extracted_df):
                            selected_indices.append(row_range)
                    elif isinstance(row_range, tuple) and len(row_range) == 2:
                        # 范围提取
                        start_row, end_row = row_range
                        # 确保索引在有效范围内
                        start_row = max(0, start_row)
                        end_row = min(len(extracted_df) - 1, end_row)

                        # 提取范围内的行
                        if start_row <= end_row:
                            selected_indices.extend(range(start_row, end_row + 1))
                    else:
                        CommonUtil.printLog(f"extract_csv fail: 无效的行范围格式 {row_range}")
                        continue

                # 索引去重并排序索引
                selected_indices = sorted(list(set(selected_indices)))

                # 根据选定的索引提取数据
                final_df = extracted_df.iloc[selected_indices].reset_index(drop=True)

            # 添加keyword过滤条件
            if keyword is not None:
                # 过滤出指定列包含keyword的数据
                final_df = final_df[final_df[column_name].astype(str).str.contains(keyword, na=False)].reset_index(drop=True)

            # 如果提供了处理函数，则对数据进行处理
            if process_func is not None and callable(process_func):
                final_df[column_name] = final_df[column_name].apply(process_func)

            # 删除空白行
            if remove_empty_row:
                final_df = final_df[final_df[column_name].str.strip() != '']

            # 如果提供了输出路径，则保存为新的CSV文件
            if output_path:
                FileUtil.createFile(output_path, False)
                final_df.to_csv(output_path, index=False, encoding=encoding, lineterminator='\n')
                CommonUtil.printLog(f'extract_csv 保存提取的数据到: {output_path}')
            return final_df
        except Exception as e:
            CommonUtil.printLog(f'extract_csv_columns fail: {e}')
            return pd.DataFrame()

    @staticmethod
    def merge_dataframe(df_left: pd.DataFrame, df_right: pd.DataFrame, on_column: str, priority_left: bool = True, keep_both: bool = True):
        """
        合并两个DataFrame，去重并解决冲突
        对于 'on_column' 列值相同的记录, 只会保留一行, 若其他column值存在冲突, 则以 'priority' 指定的数据为准

        :param df_left: 左侧DataFrame
        :param df_right: 右侧DataFrame
        :param on_column: 用于去重和合并的公共列名
        :param priority_left: 左侧 DataFrame的值在冲突时优先, 若为False, 则右侧 DataFrame的值优先
        :param keep_both: 是否保留两个DataFrame中的所有行(True: 保留所有行; False: 只保留优先级高的DataFrame中的行)
        :return: 合并并去重后的最终 DataFrame
        """
        if keep_both:
            # 保留两个DataFrame的所有行（原有逻辑）
            if not priority_left:
                df_left, df_right = df_right, df_left  # 交换位置，统一按左优先处理

            # 1. 合并
            merged_df = pd.merge(df_left, df_right, on=on_column, how='outer', suffixes=('_left', '_right'))

            # 2. 解决冲突
            right_columns = [col for col in merged_df.columns if col.endswith('_right')]
            for right_col in right_columns:
                left_col = right_col.replace('_right', '_left')
                merged_df[right_col] = np.where(merged_df[left_col].notna(), merged_df[left_col], merged_df[right_col])
                merged_df.drop(columns=[left_col], inplace=True)
                merged_df.rename(columns={right_col: right_col.replace('_right', '')}, inplace=True)

            return merged_df
        else:
            # 只保留优先级高的DataFrame中的行
            if priority_left:
                # 保留左侧DataFrame中的行，如果有冲突则使用左侧的值
                merged_df = pd.merge(df_left, df_right, on=on_column, how='left', suffixes=('_left', '_right'))

                # 解决冲突，优先使用左侧的值
                right_columns = [col for col in merged_df.columns if col.endswith('_right')]
                for right_col in right_columns:
                    left_col = right_col.replace('_right', '_left')
                    # 优先使用左侧的值，如果左侧为空则使用右侧的值
                    merged_df[left_col] = np.where(merged_df[left_col].notna(), merged_df[left_col], merged_df[right_col])
                    merged_df.drop(columns=[right_col], inplace=True)
                    merged_df.rename(columns={left_col: left_col.replace('_left', '')}, inplace=True)

                return merged_df
            else:
                # 保留右侧DataFrame中的行，如果有冲突则使用右侧的值
                merged_df = pd.merge(df_left, df_right, on=on_column, how='right', suffixes=('_left', '_right'))

                # 解决冲突，优先使用右侧的值
                right_columns = [col for col in merged_df.columns if col.endswith('_right')]
                for right_col in right_columns:
                    left_col = right_col.replace('_right', '_left')
                    # 优先使用右侧的值，如果右侧为空则使用左侧的值
                    merged_df[right_col] = np.where(merged_df[right_col].notna(), merged_df[right_col], merged_df[left_col])
                    merged_df.drop(columns=[left_col], inplace=True)
                    merged_df.rename(columns={right_col: right_col.replace('_right', '')}, inplace=True)

                return merged_df

    @staticmethod
    def merge_csv(csv1: str, csv2: str, on_column: str,
                  priority_left: bool = True,
                  encoding: str = 'utf-8-sig',
                  output_csv: Optional[str] = None,
                  keep_both: bool = True
                  ) -> pd.DataFrame:
        """
        合并两个CSV文件，并可以指定以哪个文件为准

        :param csv1: 第一个CSV文件路径 (作为 'left')
        :param csv2: 第二个CSV文件路径 (作为 'right')
        :param on_column: 用于合并的公共列名
        :param priority_left: 左侧 DataFrame的值在冲突时优先, 若为False, 则右侧 DataFrame的值优先
        :param output_csv: 将合并后的结果写入的输出CSV文件路径 (可选), None表示不输出
        :param encoding: CSV文件的编码
        :param keep_both: 是否保留两个DataFrame中的所有行(True: 保留所有行; False: 只保留优先级高的DataFrame中的行)
        :return: 合并后的 DataFrame
        """
        df1 = pd.read_csv(csv1, encoding=encoding)
        df2 = pd.read_csv(csv2, encoding=encoding)

        merged_df = FileUtil.merge_dataframe(df1, df2, on_column, priority_left, keep_both)
        if output_csv:
            merged_df.to_csv(output_csv, encoding=encoding, index=False)
        return merged_df

    @staticmethod
    def calc_dataframe_accuracy(df: pd.DataFrame, column_base: str, column_compare: str, keyword: Optional[str] = None, keyword_col: Optional[str] = None) -> dict:
        """
        计算指定列的准确率统计信息:
        1. 过滤 column_base 和 column_compare 均有值的数据
            会生成一个dataFrame, 记为: valid_df
            对应的数据量, 记为: valid_cnt  即: len(valid_df)
        2. 计算 valid_df 中 column_base 和 column_compare 相同值的数量
            会生成一个dataFrame, 记为: same_df
            对应的数据量, 记为: same_cnt  即: len(same_df)
        3. 计算准确率, 记为: accuracy = same_cnt / valid_cnt

        Args:
            df (pandas.DataFrame): 数据框
            column_base (str): 基准数据列名, 此为真值列
            column_compare (str): 待统计准确率的列名, 此为预测值列
            keyword (str, optional): 关键字过滤条件，如果提供且keyword_col不为空，则 keyword_col 列的值必须包含该关键字才被视为有效数据
            keyword_col (str, optional): 关键字所在的列名，用于判断是否满足条件。如果为None，则默认是: column_compare

        Returns:
            dict: 包含统计信息的字典，各key含义如下：
                - total_cnt (int): 总数据数，即数据框的总行数
                - valid_cnt (int): 有效数据数，即两个列均有值的行数
                - same_cnt (int): 匹配数据数，即两个列值相等的行数
                - accuracy (float): 准确率，计算公式为 same_cnt/valid_cnt
                - valid_df (pandas.DataFrame): 有效数据的DataFrame，即两个列均有值的数据子集
                - same_df (pandas.DataFrame): 匹配数据的DataFrame，即两个列值相等的数据子集
        """
        # 1. 总数据数
        total_cnt = len(df)

        # 2. column_base 和 column_compare 均有值的数据量
        valid_df = df[df[column_base].notna() & df[column_compare].notna()]

        # 3. 如果提供了keyword和keyword_col参数，则进一步过滤keyword_col包含关键字的数据
        keyword_col = column_compare if keyword_col is None else keyword_col
        if keyword is not None and keyword_col is not None and keyword_col in df.columns:
            valid_df = valid_df[valid_df[keyword_col].astype(str).str.contains(keyword, na=False)]

        valid_cnt = len(valid_df)

        # 4. column_base 和 column_compare 值相等的数据量及对应DataFrame
        same_df = valid_df[valid_df[column_base] == valid_df[column_compare]]
        same_cnt = len(same_df)

        # 5. 准确率计算
        accuracy = same_cnt / valid_cnt if valid_cnt > 0 else 0

        return {
            'total_cnt': total_cnt,  # 总数据数
            'valid_cnt': valid_cnt,  # 有效数据数（两列均有值，且满足keyword条件）
            'same_cnt': same_cnt,  # 匹配数据数（两列值相等）
            'accuracy': accuracy,  # 准确率（匹配数/有效数）
            'valid_df': valid_df,  # 有效数据DataFrame
            'same_df': same_df  # 匹配数据DataFrame
        }

    @staticmethod
    def calc_csv_accuracy(csv_path: str, column_base: str, column_compare: str,
                          keyword: Optional[str] = None, keyword_col: Optional[str] = None, encoding: str = 'utf-8-sig'):
        """
        计算CSV文件指定列的准确率

        Args:
            csv_path (str): CSV文件路径
            column_base (str): 基准数据列名, 此为真值列
            column_compare (str): 待统计准确率的列名, 此为预测值列
            keyword (str, optional): 关键字过滤条件，如果提供且keyword_col不为空，则 keyword_col 列的值必须包含该关键字才被视为有效数据
            keyword_col (str, optional): 关键字所在的列名，用于判断是否满足条件。如果为None，则默认是: column_compare
            encoding (str): CSV文件的编码，默认为 'utf-8-sig'

        Returns:
            dict: 统计信息字典，包含准确率、有效数据数、匹配数据数、总数据数等信息
        """
        df = pd.read_csv(csv_path, encoding=encoding)
        return FileUtil.calc_dataframe_accuracy(df, column_base, column_compare, keyword, keyword_col)


if __name__ == '__main__':
    # tPath = "/Users/lynxz/temp/a.txt"
    # CommonUtil.printLog(FileUtil.getParentPath(tPath, 1))
    # CommonUtil.printLog(FileUtil.getParentPath(tPath, 2))
    # CommonUtil.printLog(FileUtil.getParentPath(tPath, 3))
    # CommonUtil.printLog(FileUtil.getParentPath(tPath, 4))
    # CommonUtil.printLog(FileUtil.getParentPath(tPath, 30))
    # FileUtil.createFile(tPath, True)
    # FileUtil.write2File(tPath, "hello")
    # lines = FileUtil.readFile(tPath)
    # for line in lines:
    #     CommonUtil.printLog(line)
    #
    #
    # def filterLog(path: str) -> bool:
    #     pattern = 'log_*'
    #     return re.search(r'%s' % pattern, path) is not None
    #
    #
    # CommonUtil.printLog(FileUtil.listAllFilePath('/Users/lynxz/temp/', 1, 0, filterLog))
    b, info = FileUtil.getFileSize('H:/Workspace/Python/wool/temp.air/tpl1682432948047.png')
    CommonUtil.printLog('file size=%s,size1=%s' % (b, info))
    # b, info = FileUtil.getDirSize('H:/Workspace/Python/wool/temp.air/')
    b, info = FileUtil.getDirSize('D:/Downloads/Tencent/斗破苍穹666')

    CommonUtil.printLog('dir size=%s,size1=%s' % (b, info))
