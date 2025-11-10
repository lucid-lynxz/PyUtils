# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from base.BaseConfig import BaseConfig
from util.CompressUtil import CompressUtil
from util.FileUtil import FileUtil
from util.CommonUtil import CommonUtil

"""
主要功能: 使用7zip 批量压缩指定父目录下所有下一级的压缩包
假设文件结构如下:
p/
   a/
     b/
        bb0.zip
        bb1.7z
     c/cc.rar
   d/
   e/e.zip
   f.tar.gz
则在 config.ini 中进行如下配置 parentDirPath 为 p/ 目录的绝对路径后:
1. maxUncompressDepth=1,则仅解压缩 f.tar.gz
2. maxUncompressDepth=2,则解压缩:
    f.tar.gz
    e/e.zip
3. maxUncompressDepth=3,则解压缩:
    f.tar.gz
    e/e.zip
    a/b/bb0.zip
    a/b/bb1.7z
    a/c/cc.rar
若要求对 a/ 目录压缩时, 不对其子目录 b/ 进行压缩, 则:
1. 在 config.ini 中配置 excludeDirName 为: b
2. 脚本执行时, a/b/目录 或者 a/b 文件均不会添加到压缩包中

若要求解压缩完成后删除源文件, 则:
1. 在 config.ini 中配置: deleteSrcFileAfterUncompress=True
"""


class BathUncompressImpl(BaseConfig):
    def uncompress(self, srcPath: str,
                   compressUtil: CompressUtil,
                   pwds: list = None,  # 可能的解压密码列表, 会优先尝试无密码解压
                   minRatio: float = 0.5,  # 解压后的文件总大小至少得是源文件的几倍才算解压成功,默认0.5倍
                   deleteSrcFileAfterCompress: bool = False) -> bool:
        if CommonUtil.isNoneOrBlank(srcPath) or compressUtil is None:
            print('uncompress fail:%s' % srcPath)
            return False

        srcPath = FileUtil.recookPath('%s' % srcPath)
        srcSize, _ = FileUtil.getFileSize(srcPath)  # 获取压缩包文件大小,单位:byte
        print('正在准备解压 %s' % srcPath)

        if pwds is None:
            pwds = list()
        pwds.insert(0, '')  # 空白表示无密码解压

        tSuccess = False
        for pwd in pwds:
            success, dest = compressUtil.unzip(srcPath, pwd=pwd, printCmdInfo=True)
            if success and not FileUtil.isDirEmpty(dest):  # 解压成功: 未报错并且目录非空
                allSize, _ = FileUtil.getDirSize(dest)  # 获取解压后的文件总大小,单位:byte
                if allSize > 0 and allSize >= srcSize * minRatio:
                    tSuccess = True
                    print('解压成功 pwd=%s, srcFile=%s,dest=%s' % (pwd, srcPath, dest))
                    break
            if not tSuccess:
                # print('解压失败,尝试删除目录:%s' % dest)
                FileUtil.deleteFile(dest)  # 解压失败时,删除解压目录

        if tSuccess:
            if deleteSrcFileAfterCompress:  # 删除源文件
                print('删除源文件: %s' % srcPath)
                FileUtil.deleteFile(srcPath)
        else:
            print('解压失败 srcPath=%s' % srcPath)
        return tSuccess

    def onRun(self):
        parentDirPath = FileUtil.recookPath(self.configParser.get('config', 'parentDirPath'))  # 父目录路径
        excludePath = FileUtil.recookPath(self.configParser.get('config', 'excludePath'))  # 不进行解压缩的子文件名
        sevenZipPath = FileUtil.recookPath(self.configParser.get('config', 'sevenZipPath'))  # 7z.exe文件路径
        deleteSrcFileAfterCompress: bool = self.configParser.get('config', 'deleteSrcFileAfterUncompress') == 'True'
        maxDepth: int = int(self.configParser.get('config', 'maxDepth'))  # 最大递归解压层级
        minRatio: float = float(self.configParser.get('config', 'minRatio'))  # 解压后的文件总大小至少得是源压缩包的几倍大才算解压成功
        supportExtType = self.configParser.get('config', 'supportExtType')  # 压缩文件后缀
        supportExtTypeList = list() if CommonUtil.isNoneOrBlank(supportExtType) else supportExtType.split(',')
        relaceDict = self.configParser.getSectionItems('replace')
        CommonUtil.printLog(f'pending replaceItems: {relaceDict}')

        # 提取待剔除的路径信息
        excludePathList: list = list()
        if not CommonUtil.isNoneOrBlank(excludePath):
            arr = excludePath.split(',')
            for item in arr:
                item = FileUtil.recookPath(item)
                if not CommonUtil.isNoneOrBlank(item):
                    excludePathList.append(item)

        # 提取候选密码列表
        pwdItemList = self.configParser.getSectionKeyList('password')  # 候选解压密码列表

        # 过滤不支持的后缀
        def filterExt(path: str) -> bool:
            if CommonUtil.isNoneOrBlank(path):
                return False

            # 删除文件名中无用字符
            if not CommonUtil.isNoneOrBlank(relaceDict):
                for key in relaceDict:
                    value = relaceDict.get(key, '')
                    value = '' if CommonUtil.isNoneOrBlank(value) else value
                    path = path.replace(key, value)

            hit = False
            for item in supportExtTypeList:
                if path.endswith(item.strip()):
                    hit = True
                    break
            return hit

        # 过滤用户指定的不解压的其他文件
        def filterExcludeFiles(path: str) -> bool:
            for item in excludePathList:
                if item in path:
                    return False
            return True

        subFiles = FileUtil.listAllFilePath(parentDirPath, maxDepth, 0, True, filterExt, filterExcludeFiles)
        if CommonUtil.isNoneOrBlank(subFiles):
            print('解压失败:未找到符合条件的带解压文件')
            return
        print('待解压的文件:%s' % subFiles)

        successList = list()
        failList = list()
        compressUtil = CompressUtil(sevenZipPath)
        for subFilePath in subFiles:
            success = self.uncompress(subFilePath, compressUtil=compressUtil, pwds=pwdItemList, minRatio=minRatio,
                                      deleteSrcFileAfterCompress=deleteSrcFileAfterCompress)
            if success:
                successList.append(subFilePath)
            else:
                failList.append(subFilePath)

        if not CommonUtil.isNoneOrBlank(successList):
            print('解压成功的文件:%s' % successList)

        if not CommonUtil.isNoneOrBlank(failList):
            print('解压失败的文件:%s' % failList)

        print('执行完成, 打开目录: %s' % parentDirPath)
        FileUtil.openDir(parentDirPath)


if __name__ == '__main__':
    # 根据配置文件, 提取指定位置的文件
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    BathUncompressImpl(configPath, optFirst=True).run()
