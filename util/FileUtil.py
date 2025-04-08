# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import platform
import shutil

from util.CommonUtil import CommonUtil


class FileUtil(object):
    @staticmethod
    def recookPath(path: str, forceEnableLongPath: bool = False, replaceBlank: str = '') -> str:
        """
        路径字符串处理: 替换 反斜杠 为 斜杠
        :param path: 路径字符串
        :param forceEnableLongPath: win下是否强制启用长目录路径格式
        :param replaceBlank: 回车空格字符要替换为指定的值, None表示不处理
        :return: 处理后的路径,为避免空指针,返回值均为非None
        """
        if CommonUtil.isNoneOrBlank(path):
            return ''

        if path.startswith("~"):
            path = '%s%s' % (os.path.expanduser("~"), path[1:])
            return FileUtil.recookPath(path)

        path = path.replace("\\", "/").replace("//", "/")
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
        pPath = path
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
        return fsize, FileUtil._formatByteSize(fsize)

    @staticmethod
    def _formatByteSize(fsize: int) -> str:
        """将所给字节数转换为带单位的字符串, 支持B/K/M/G"""
        if fsize < 1024:
            return '%sB' % fsize
        else:
            KBX = fsize / 1024
            if KBX < 1024:
                return '%sK' % round(KBX, 2)
            else:
                MBX = KBX / 1024
                if MBX < 1024:
                    return '%sM' % round(MBX, 2)
                else:
                    return '%sG' % round(MBX / 1024)

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
        return allByteSize, FileUtil._formatByteSize(allByteSize)

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
