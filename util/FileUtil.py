# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import platform
import re
import shutil

from util.CommonUtil import CommonUtil


class FileUtil(object):
    @staticmethod
    def recookPath(path: str) -> str:
        """
        路径字符串处理: 替换 反斜杠 为 斜杠
        :param path: 路径字符串
        :return: 处理后的路径
        """
        if CommonUtil.isNoneOrBlank(path):
            return path
        return path.replace("\\", "/").replace("//", "/")

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
        pPath = path
        for index in range(level):
            try:
                pPath = os.path.dirname(pPath)
            except Exception as e:
                print('getParentPath error: %s' % e)
        return FileUtil.recookPath('%s/' % pPath)

    @staticmethod
    def isFileExist(path: str) -> bool:
        """
        文件是否存在
        :param path: 文件路径
        :return: bool
        """
        path = FileUtil.recookPath(path)
        if path is None or len(path) == 0:
            return False
        return os.path.exists(path)

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

        if FileUtil.isDirFile(src):  # 目录, 递归复制
            # 由于 src 为目录时, dst也必须是目录
            # 且shutil复制目录要求dst不存在, 因此需要遍历进行普通文件复制
            if FileUtil.isFileExist(dst):
                for fileItem in FileUtil.listAllFilePath(src):
                    fileName, _, _ = FileUtil.getFileName(fileItem)
                    if FileUtil.isDirFile(fileItem):
                        FileUtil.copy(fileItem, '%s/%s/' % (dst, fileName))
                    else:
                        shutil.copy(fileItem, '%s/%s' % (dst, fileName))
            else:
                shutil.copytree(src, dst)  # dst目录不存在时, 直接使用copytree复制即可
            pass
        else:  # 普通文件, 直接复制
            shutil.copy(src, dst)

    @staticmethod
    def deleteFile(path: str):
        """
        删除文件
        :param path: 文件路径
        :return:
        """
        path = FileUtil.recookPath(path)
        if FileUtil.isFileExist(path):
            if FileUtil.isDirFile(path):  # 目录
                shutil.rmtree(path)
                # os.rmdir(path) # 非空目录会报错: WindowsError：[Error 145]
            else:  # 文件
                os.remove(path)

    @staticmethod
    def listAllFilePath(folderPath: str, depth: int = 1, curDepth: int = 0, *path_filters) -> list:
        """
        获取指定目录下所有文件的绝对路径
        若目录不存在,则返回空数据
        :param folderPath: 目录路径
        :param depth: 递归遍历的深度,默认为一级, 即只获取 folderPath 的下一级子文件
        :param curDepth: 当前目录(folderPath)所在层级
        :param path_filters 文件路径过滤函数,可多个
        :return:
        """
        folderPath = FileUtil.recookPath(folderPath)
        result = list()
        if FileUtil.isDirFile(folderPath):
            subFiles = os.listdir(folderPath)  # 返回的是子文件的相对路径
            curDepth = curDepth + 1
            for sub in subFiles:
                subPath = os.path.join(folderPath, sub)  # 子文件路径
                if FileUtil.isDirFile(subPath) and curDepth < depth:  # 子文件是目录, 则递归遍历
                    subList = FileUtil.listAllFilePath(subPath, curDepth, *path_filters)
                    for reSubFile in subList:
                        result.append(reSubFile)
                else:  # 文件,则记录绝对路径
                    result.append(subPath)
        if path_filters is not None:
            for path_filter in path_filters:
                result = list(filter(path_filter, result))
        return result

    @staticmethod
    def getFileName(path: str) -> tuple:
        """
        根据所给文件名或者文件路径,去除目录信息后, 得到文件名和扩展名, 如输入 a.txt 返回 ("a.txt","a","txt")
        若当前就以斜杠结尾,则先删除斜杠
        :param path: 文件名或者路径
        :return: tuple (fileName+ext, fileName, ext)
        """
        path = FileUtil.recookPath(path)
        if path.endswith('/'):  # 目录路径则提取目录名信息
            # print("getFileName oriPath=%s, curPath=%s" % (path, path[:-1]))
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
            print("makeDir() 文件已存在但并非目录, 进行删除: %s" % folder_path)
            os.remove(folder_path)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

    @staticmethod
    def createFile(path: str, recreateIfExist: bool = False):
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
        else:
            # 按需创建父目录
            parentPath = os.path.dirname(path) + os.sep
            if not FileUtil.isDirFile(parentPath):
                os.makedirs(parentPath)

            # 创建文件
            try:
                with open(path, "w" if recreateIfExist else "a") as f:
                    f.close()
            except Exception as e:
                pass

    @staticmethod
    def write2File(path: str, msg: str, encoding='utf-8') -> bool:
        """
        写入信息到指定文件中,若文件不存在则自动创建,若文件已存在,则覆盖内容
        :param path: 文件路径
        :param msg: 要写入的信息
        :param encoding: 编码, 默认:utf-8
        :return: 是否写入成功
        """
        path = FileUtil.recookPath(path)
        return FileUtil.__wirte2FileInnner(path, msg, False, encoding)

    @staticmethod
    def append2File(path: str, msg: str, encoding='utf-8') -> bool:
        """
        写入信息到指定文件中,若文件不存在则自动创建,若文件已存在,则覆盖内容
        :param path: 文件路径
        :param msg: 要写入的信息
        :param encoding: 编码
        :return: 是否写入成功
        """
        path = FileUtil.recookPath(path)
        return FileUtil.__wirte2FileInnner(path, msg, True, encoding)

    @staticmethod
    def __wirte2FileInnner(path: str, msg: str, append: bool, encoding='utf-8') -> bool:
        path = FileUtil.recookPath(path)
        if msg is None or len(msg) == 0:
            return False

        if not msg.endswith("\n"):
            msg = "%s\n" % msg

        FileUtil.createFile(path, recreateIfExist=False)
        if FileUtil.isDirFile(path):
            print("append2File fail as %s is a folder" % path)
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
        CommonUtil.exeCmd(cmd)


if __name__ == '__main__':
    tPath = "/Users/lynxz/temp/a.txt"
    print(FileUtil.getParentPath(tPath, 1))
    print(FileUtil.getParentPath(tPath, 2))
    print(FileUtil.getParentPath(tPath, 3))
    print(FileUtil.getParentPath(tPath, 4))
    print(FileUtil.getParentPath(tPath, 30))
    FileUtil.createFile(tPath, True)
    FileUtil.write2File(tPath, "hello")
    lines = FileUtil.readFile(tPath)
    for line in lines:
        print(line)


    def filterLog(path: str) -> bool:
        pattern = 'log_*'
        return re.search(r'%s' % pattern, path) is not None


    print(FileUtil.listAllFilePath('/Users/lynxz/temp/', 1, 0, filterLog))
