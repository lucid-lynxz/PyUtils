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

    def __init__(self, sevenZipPath: str = None):
        """
        :param sevenZipPath: 7z.exe 可自行执行路径
        """
        # 由于在windows下,软件经常装在 C:/Program Files/ 目录下, 目录名带有空格可能导致执行命令出错,因此包装一层
        self.sevenZipPath = '\"%s\"' % CommonUtil.checkThirdToolPath(FileUtil.recookPath(sevenZipPath), "7z")

    def compress(self, src: str, dst: str = None, pwd: str = None,
                 excludeDirName: str = None, sizeLimit: str = None,
                 printCmdInfo: bool = True) -> str:
        """
        压缩指定文件成zip
        :param pwd: 密码
        :param src: 待压缩的目录/文件路径
        :param dst: 生成的压缩文件路径,包括目录路径和文件名,若为空,则默认生成在源文件所在目录
                            会自动提取文件名后缀作为压缩格式,若为空,则使用默认 .zip 格式压缩
                            支持的后缀主要包括:  .7z .zip .gzip .bzip2 .tar 等
        :param excludeDirName: 不进行压缩的子目录/文件名信息, 支持通配符,支持多个,使用逗号分隔
        :param sizeLimit: 压缩包大小限制, 支持的单位: b/k/m/g, 如: 100m 表示压缩后单文件最大100M
        :param printCmdInfo:执行命令时是否打印命令内容
        :return: 最终压缩文件路径, 若压缩失败,则返回 ""
        """
        if CommonUtil.isNoneOrBlank(src):
            print("压缩失败:参数异常,请确认源文件路径正确")
            return ""

        if not os.path.exists(src):
            print("压缩失败:源文件不存在,请检查后再试")
            return ""

        if CommonUtil.isNoneOrBlank(dst):
            if src.endswith('/') or src.endswith('\\'):
                dst = '%s.zip' % src[:-1]
            else:
                dst = '%s.zip' % src

        _, _, ext = FileUtil.getFileName(dst)
        pCmd = ""
        if pwd is not None and len(pwd) > 0:
            pCmd = "-p%s -mhe" % pwd

        # 需要剔除子文件
        excludeCmd = ""
        if excludeDirName is not None and len(excludeDirName) > 0:
            arr = excludeDirName.split(',')
            if CommonUtil.isWindows():
                excludeCmd = ' -xr^!'.join(arr)
                excludeCmd = ' -xr^!%s' % excludeCmd
            else:
                for item in arr:
                    excludeCmd = '%s \'-xr!%s\'' % (excludeCmd, item)

        # 分包压缩大小
        sizeLimitCmd = ''
        if sizeLimit is not None and len(sizeLimit) > 0:
            sizeLimitCmd = '-v%s' % sizeLimit

        # 原路径和压缩包路径增加双引号,兼容路径中带空格的情形
        cmd = "%s a -t%s -r \"%s\" %s \"%s\" %s %s" % (self.sevenZipPath, ext, dst, pCmd, src, excludeCmd, sizeLimitCmd)
        CommonUtil.exeCmd(cmd, printCmdInfo=printCmdInfo)
        return dst

    def unzip(self, src7zFile: str, dest: str = None, pwd: str = None, printCmdInfo: bool = False) -> tuple:
        """
        解压缩指定7z文件
        :param pwd: 密码
        :param src7zFile: 要解压的7z文件
        :param dest: 解压目录路径, 若为空,则解压到源压缩文件同级目录下
        :param printCmdInfo:是否打印日志
        :return: (bool,str) 前者表示是否解压成功, 后者表示解压目录路径,若失败,则返回 None
        """
        if not os.path.exists(src7zFile):
            print("压缩文件不存在,请检查后重试: ", src7zFile)
            return False, dest

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
        if not CommonUtil.isNoneOrBlank(pwd):
            pCmd = "-p%s -mhe" % pwd
        # 注意 -o 与后面的解压目录之间不要有空格
        result = CommonUtil.exeCmd(
            "echo %s | %s x %s -y -aos -o%s %s" % (pCmd, self.sevenZipPath, src7zFile, dest, pCmd), printCmdInfo)
        print('result=%s' % result)
        success = "Can't open as archive" not in result
        return success, dest


if __name__ == '__main__':
    p = 'D:/temp/log_123456.7z'
    dest = CompressUtil().unzip(p, pwd='123')
    print('dest=%s' % dest)
