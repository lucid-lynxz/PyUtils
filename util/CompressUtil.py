# -*- coding: utf-8 -*-

import os
import time

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
通过7z进行目录/文件压缩/解压缩
使用:
1. 压缩指定文件: compress(src, dest)
2. 解压文件: unzip(src7zFile, dest)
"""


class CompressUtil(object):

    def __init__(self, sevenZipPath: str):
        """
        :param sevenZipPath: 7z.exe 可自行执行路径
        """
        # 由于在windows下,软件经常装在 C:/Program Files/ 目录下, 目录名带有空格可能导致执行命令出错,因此包装一层
        self.sevenZipPath = '\"%s\"' % FileUtil.recookPath(sevenZipPath)

    def compress(self, src: str, dest: str = None, pwd: str = None, excludeDirName: str = None):
        """
        压缩指定文件成zip
        :param pwd: 密码
        :param src: 待压缩的目录/文件路径
        :param dest: 生成的压缩文件路径,包括目录路径和文件名,若为空,则默认生成在源文件所在目录
                            会自动提取文件名后缀作为压缩格式,若为空,则使用默认 .zip 格式压缩
                            支持的后缀主要包括:  .7z .zip .gzip .bzip2 .tar 等
        :param excludeDirName: 不进行压缩的子目录/文件名信息, 支持通配符,支持多个,使用逗号分隔
        :return: 压缩文件路径, 若压缩失败,则返回 ""
        """
        if CommonUtil.isNoneOrBlank(src):
            print("压缩失败:参数异常,请确认源文件路径正确")
            return ""

        if not os.path.exists(src):
            print("压缩失败:源文件不存在,请检查后再试")
            return ""

        if CommonUtil.isNoneOrBlank(dest):
            if src.endswith('/') or src.endswith('\\'):
                dest = '%s.zip' % src[:-1]
            else:
                dest = '%s.zip' % src

        _, _, ext = FileUtil.getFileName(dest)
        pCmd = ""
        if pwd is not None and len(pwd) > 0:
            pCmd = "-p%s -mhe" % pwd

        # 需要剔除子文件
        excludeCmd = ""
        if excludeDirName is not None and len(excludeDirName) > 0:
            arr = excludeDirName.split(',')
            excludeCmd = ' -xr^!'.join(arr)
            excludeCmd = ' -xr^!%s' % excludeCmd

        cmd = "%s a -t%s -r %s %s %s %s" % (self.sevenZipPath, ext, dest, pCmd, src, excludeCmd)
        CommonUtil.exeCmd(cmd)
        return dest

    def unzip(self, src7zFile: str, dest: str = None, pwd: str = None):
        """
        解压缩指定7z文件
        :param pwd: 密码
        :param src7zFile: 要解压的7z文件
        :param dest: 解压目录路径, 若为空,则解压到源压缩文件同级目录下
        :return: 解压目录路径,若失败,则返回 None
        """
        if not os.path.exists(src7zFile):
            print("压缩文件不存在,请检查后重试: ", src7zFile)
            return

        src7zFile = src7zFile.replace("\\", "/")
        if CommonUtil.isNoneOrBlank(dest):
            _, srcFileName, _ = FileUtil.getFileName(src7zFile)
            dest = os.path.join(os.path.dirname(src7zFile), srcFileName)

        if os.path.exists(dest):
            localtime = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            dest = "%s_%s" % (dest, localtime)

        dest = dest.replace("\\", "/")
        FileUtil.makeDir(dest)

        pCmd = ""
        if pwd is not None and len(pwd) > 0:
            pCmd = "-p%s -mhe" % pwd
        # 注意 -o 与后面的解压目录之间不要有空格
        CommonUtil.exeCmd("%s x %s -y -aos -o%s %s" % (
            self.sevenZipPath, src7zFile, dest, pCmd))
        return dest
