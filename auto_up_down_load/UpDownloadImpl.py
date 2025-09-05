# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动上传/下载目录文件
具体以 config.ini 文件配置信息为准
"""

import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from util.CommonUtil import CommonUtil
from util.NetUtil import NetUtil
from base.BaseConfig import BaseConfig
from util.SSHUtil import SSHUtil
from util.FileUtil import FileUtil


class UpDownloadImpl(BaseConfig):
    # def __init__(self):
    #     super().__init__(delimiters='=')

    def onRun(self):
        self.update_delimiters('=')
        settings = self.configParser.getSectionItems('settings')
        enable_upload: bool = settings.get('enable_upload', True)
        enable_download: bool = settings.get('enable_download', True)
        overwrite: bool = settings.get('overwrite', True)
        upload_info_name: bool = settings.get('upload_info_name', '')

        upload_items: dict = self.configParser.getSectionItems('upload')
        download_items: dict = self.configParser.getSectionItems('download')

        NetUtil.robot_dict = self.configParser.getSectionItems('robot')

        # 示例配置(根据实际环境修改)
        SSH_CONFIG = {
            "host": settings.get('host'),  # 服务器ip
            "username": settings.get('username', 'root'),  # 用户名
            "password": settings.get('password'),  # 密码
            "port": settings.get('port', 22)  # 端口号
        }

        # 使用上下文管理器自动管理连接
        with SSHUtil(**SSH_CONFIG) as ssh:
            NetUtil.push_to_robot(f'开始执行服务器 {SSH_CONFIG["host"]} 的上传下载任务')

            # 上传目录(不覆盖已存在文件)
            if enable_upload:
                progress = 0
                total = len(upload_items)
                for local_dir, remote_dir in upload_items.items():
                    success = ssh.upload_directory_to_server(local_dir, remote_dir, overwrite=overwrite)
                    progress += 1
                    result = '成功' if success else '失败'

                    info_msg = ''
                    if not CommonUtil.isNoneOrBlank(upload_info_name):
                        info_file_path = FileUtil.recookPath(f'{local_dir}/{upload_info_name}')
                        info_msg = ''.join(FileUtil.readFile(info_file_path)).strip()
                        if not CommonUtil.isNoneOrBlank(info_msg):
                            info_msg = f'\n\n{upload_info_name}\n{info_msg}'
                    NetUtil.push_to_robot(f'上传{result} ({progress}/{total}) : {local_dir} -> {remote_dir}{info_msg}')

            # 下载文件(.txt/.png/.jpg)
            if enable_download:
                progress = 0
                total = len(download_items)
                for remote_dir, local_dir in download_items.items():
                    success = ssh.download_files_from_server(remote_dir, local_dir)
                    progress += 1
                    result = '成功' if success else '失败'
                    NetUtil.push_to_robot(f'下载{result} ({progress}/{total}) : {remote_dir} -> {local_dir}')

            NetUtil.push_to_robot(f'上传下载任务执行完成')
