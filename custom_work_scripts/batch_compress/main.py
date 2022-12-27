# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re
from base.BaseConfig import BaseConfig
from util.CompressUtil import CompressUtil
from util.FileUtil import FileUtil

"""
主要功能: 使用7zip 批量压缩指定父目录下所有子目录
假设文件结构如下:
p/
   a/
     b/
        bb0.txt
        bb1.txt
     c/cc.txt
   d/
   e/
   f.txt
则在 config.ini 中进行如下配置 parentDirPath 为 p/ 目录的绝对路径后:
会对 a/  d/  e/ 三个子目录进行压缩,并在 p/ 目录下生成 a.zip,d.zip,e.zip

若要求对 a/ 目录压缩时, 不对其子目录 b/ 进行压缩, 则:
1. 在 config.ini 中配置 excludeDirName 为: b
2. 脚本执行时, a/b/目录 或者 a/b 文件均不会添加到压缩包中

若要求剔除 b/ 目录之前, 保留 b/bb1.txt 则:
1. 在 config.ini 中的 [copy] 中增加一行: b/bb1.txt$ 
   P.S. 支持正则, 如上符号'$'表示结`尾
2. 脚本执行时, 会复制 a/b/bb1.txt --> a/bb1.txt

若要求压缩完成后删除源目录, 则:
1. 在 config.ini 中配置: deleteSrcFileAfterCompress=True
"""


class BathCompressImpl(BaseConfig):
    def compressDir(self, srcPath: str,
                    compressUtil: CompressUtil,
                    excludeDirName: str = '',
                    copyItems: list = None,
                    deleteSrcFileAfterCompress: bool = False, maxDepth: int = 3):
        if not FileUtil.isDirFile(srcPath) or compressUtil is None:
            print('compressDir fail:%s' % srcPath)
            return
        srcPath = FileUtil.recookPath('%s/' % srcPath)

        # 拷贝需要保留的文件到根目录
        if copyItems is not None and len(copyItems) > 0:
            subFiles = FileUtil.listAllFilePath(srcPath, depth=maxDepth, getAllDepthFileInfo=True)
            for subFilePath in subFiles:
                subPath = FileUtil.recookPath(subFilePath)
                for pattern in copyItems:
                    pushResult = re.search(pattern, subPath, re.I)  # 忽略大小写比较
                    if pushResult is not None:  # 匹配成功
                        print('匹配成功,正在复制 %s' % subPath)
                        FileUtil.copy(subPath, '%s/%s' % (srcPath, FileUtil.getFileName(subPath)[0]))

        # 执行压缩操作
        compressPath = compressUtil.compress(src=srcPath, excludeDirName=excludeDirName)
        if FileUtil.isFileExist(compressPath):
            print('压缩成功, 文件路径:%s' % srcPath)
            if deleteSrcFileAfterCompress:
                print('删除源文件: %s' % srcPath)
                FileUtil.deleteFile(srcPath)
        else:
            print('压缩失败, 请手动重试, 源文件路径: %s' % srcPath)

    def onRun(self):
        parentDirPath = FileUtil.recookPath(self.configParser.get('config', 'parentDirPath'))  # 父目录路径
        excludeDirName = FileUtil.recookPath(self.configParser.get('config', 'excludeDirName'))  # 不进行压缩的子文件名
        sevenZipPath = FileUtil.recookPath(self.configParser.get('config', 'sevenZipPath'))  # 7z.exe文件路径
        deleteSrcFileAfterCompress: bool = self.configParser.get('config', 'deleteSrcFileAfterCompress') == 'True'
        maxCopyDepth: int = int(self.configParser.get('config', 'maxCopyDepth'))
        copyItemsDict = self.configParser.getSectionItems('copy')
        copyItemList = list()

        if copyItemsDict is not None and len(copyItemsDict) > 0:
            for key in copyItemsDict:
                copyItemList.append(FileUtil.recookPath(key))

        subFiles = FileUtil.listAllFilePath(parentDirPath)
        compressUtil = CompressUtil(sevenZipPath)
        for subFilePath in subFiles:
            self.compressDir(subFilePath, compressUtil, excludeDirName,
                             copyItemList, deleteSrcFileAfterCompress,
                             maxCopyDepth)

        print('执行完成, 打开目录: %s' % parentDirPath)
        FileUtil.openDir(parentDirPath)


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    BathCompressImpl(configPath, optFirst=True).run()
