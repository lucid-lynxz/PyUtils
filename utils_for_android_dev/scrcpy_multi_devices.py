# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import os
import platform
import sys

# 把当前文件所在文件夹的父文件夹路径加入到 PYTHONPATH,否则在shell中运行会提示找不到util包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base.BaseConfig import BaseConfig
from util.AdbUtil import AdbUtil
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
scrcpy: https://github.com/Genymobile/scrcpy
多设备连接到电脑时,scrcpy无法直接启动投屏,需要指定设备号, 本脚本对此进行兼容
需要指定配置文件 --config xxx,其中需包含 scrcpy.scrcpy_dir_path 信息,用于设置scrcpy软件的安装目录
"""


class ScrcpyMultiDevicesImpl(BaseConfig):
    def run(self):
        # 当前只支持windows
        if platform.system() != 'Windows':
            print('当前只支持windows系统')
            return

        # 若同时连接了多台设备,则让用户确认全部投屏还是投屏某一部设备
        adbUtil: AdbUtil = AdbUtil()
        ids, names = adbUtil.getAllDeviceId()
        length = len(ids)
        if length <= 0:
            print('本机未连接任何Android设备, 请检查后重试')
            return

        onlyChooseOneDevices = length <= 1
        if length > 1:
            index_input = input("\n检测到又多台设备在线,请选择(默认0):"
                                "\n0: 全部投屏"
                                "\n1: 只投屏其中一台设备\n")
            index_choose = 0
            if index_input is not None and len(index_input.strip()) > 0:
                index_choose = int(index_input)
            onlyChooseOneDevices = index_choose != 0

            # 用户选择要操作的手机设备id
            if onlyChooseOneDevices:
                ids = [adbUtil.choosePhone()]

        # 获取当前文件路径,并拼接出临时 vbs 脚本存储路径
        # current_path = os.path.abspath(__file__)
        # vbsFilePath = "%s%stemp.vbs" % (os.path.dirname(current_path), os.path.sep)
        # 根据配置文件提取 scrcpy.exe 所在目录
        scrypy_dir_path = self.configParser.get('scrcpy', 'scrcpy_dir_path')

        # 在 scrcpy 目录下创建最终的 vbs 脚本
        vbsFilePath = "%stemp.vbs" % scrypy_dir_path
        FileUtil.deleteFile(vbsFilePath)

        vbsCmd = "Set WshShell=Wscript.CreateObject(\"Wscript.Shell\")\n"
        print(vbsCmd)
        FileUtil.append2File(vbsFilePath, vbsCmd)
        for devId in ids:
            # 方法1: 通过vbs创建无console框的投屏
            # 先写入到文件,然后执行, 执行后删除该文件即可
            # vbsCmd = "CreateObject(\"Wscript.Shell\").Run \"cmd /c scrcpy.exe -s %s\", 0, false\n" % devId
            vbsCmd = "WshShell.Run \"cmd /c scrcpy.exe -s %s\", 0, false\n" % devId
            print(vbsCmd)
            FileUtil.append2File(vbsFilePath, vbsCmd)

            # 方法2: 通过subProocess开启子进程执行多投屏命令,但会存在console框
            # print(common_util.convert_string_as_gbk("正在尝试投屏设备: %s" % devId))
            # # command = "scrcpy -s %s" % target_device_id
            # common_util.exe_cmd_by_subprocess(["scrcpy", "-s", devId])

        # 执行vbs脚本
        # vbsContent = file_util.readFile(vbsFilePath)
        # print(vbsContent)
        CommonUtil.exeCmd("cd %s && %s" % (scrypy_dir_path, vbsFilePath))
        # file_util.deleteFile(vbsFilePath)


if __name__ == '__main__':
    curDir = FileUtil.getParentPath(os.path.abspath(__file__))
    configPath = FileUtil.recookPath('%s/config.ini' % curDir)
    ScrcpyMultiDevicesImpl(configPath, optFirst=True).run()
