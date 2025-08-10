# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import stat
import traceback
from pathlib import Path
from util.FileUtil import FileUtil
from util.CommonUtil import CommonUtil


class SSHUtil(object):
    """
    通过ssh库连接远程服务器并进行目录的上传和下载
    pip install paramiko
    上传: upload_directory_to_server()
    下载: download_files_from_server()
    关闭连接: close()
    使用实例:
    with SSHUtil(host='...', username='...', password='...') as ssh:
        ssh.upload_directory_to_server(local_dir, remote_dir)
        # 离开with块后自动调用close()
    """

    def __init__(self, host: str, username: str, password: str, port: int = 22, timeout: int = 10):
        self.host = host  # 服务器主机名或IP地址
        self.port = port  # SSH端口,默认22
        self.username = username  # 用户名
        self.password = password  # 密码
        self.timeout = timeout  # 连接超时时间(秒)
        self.ssh_client = None  # SSH客户端实例
        self.sftp_client = None  # SFTP客户端实例
        if not self._connect():  # 初始化时建立连接
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port}")

    def create_remote_directory(self, remote_dir: str):
        """递归创建远程目录"""
        try:
            remote_dir = FileUtil.recookPath(remote_dir)
            self.sftp_client.stat(remote_dir)  # 检查目录是否存在
        except FileNotFoundError:
            parent_dir = FileUtil.getParentPath(remote_dir, 1)

            if parent_dir and parent_dir != '/':
                self.create_remote_directory(parent_dir)
            try:
                self.sftp_client.mkdir(remote_dir)
            except PermissionError:
                raise PermissionError(f"无权限创建目录: {remote_dir}")
            except Exception as e:
                raise RuntimeError(f"创建目录失败 {remote_dir}: {str(e)}")

    def check_path_exists(self, path: str) -> bool:
        """检查远程路径(文件或目录)是否存在"""
        try:
            self.sftp_client.stat(path)
            return True
        except FileNotFoundError:
            return False

    def check_is_file(self, path: str) -> bool:
        """检查远程路径是否为文件(非目录)"""
        try:
            return not stat.S_ISDIR(self.sftp_client.stat(path).st_mode)
        except FileNotFoundError:
            return False

    @staticmethod
    def progress_callback(transferred: int, total: int):
        """传输进度回调函数"""
        if total == 0:  # 避免除零错误
            return
        print(f"\rTransferred: {transferred}/{total} bytes ({(transferred / total * 100):.2f}%)", end="")
        if transferred >= total:
            print("\n")  # 传输完成后换行

    def _connect(self) -> bool:
        """建立SSH和SFTP连接"""
        if CommonUtil.is_library_installed('paramiko'):
            import paramiko
        else:
            return False
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.load_system_host_keys()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            # 添加超时参数，避免无限阻塞
            self.ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout
            )
            self.sftp_client = self.ssh_client.open_sftp()
            return True
        except Exception as e:
            print(f"连接失败: {str(e)}")
            traceback.print_exc()
            self.close()  # 清理未成功的连接
            return False

    def _is_connected(self) -> bool:
        """检查连接是否存活"""
        if not self.ssh_client or not self.sftp_client:
            return False
        try:
            # 通过执行简单命令检查SSH连接
            stdin, stdout, stderr = self.ssh_client.exec_command('echo ok', timeout=5)
            return stdout.read().strip() == b'ok'
        except Exception:
            return False

    def _reconnect(self) -> bool:
        """尝试重新建立连接"""
        if self._is_connected():
            return True
        print("连接已断开，尝试重新连接...")
        self.close()
        return self._connect()

    def close(self):
        """关闭所有连接资源"""
        if self.sftp_client:
            try:
                self.sftp_client.close()
            except Exception as e:
                print(f"关闭SFTP失败: {str(e)}")
            self.sftp_client = None
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception as e:
                print(f"关闭SSH失败: {str(e)}")
            self.ssh_client = None

    def upload_directory_to_server(self, local_dir: str, remote_dir: str, overwrite: bool = True) -> bool:
        """上传本地目录到远程服务器(支持递归子目录)"""
        try:
            if not self._reconnect():  # 传输前确保连接有效
                raise ConnectionError("上传前无法建立有效连接")

            local_dir = os.path.abspath(local_dir)
            if not os.path.isdir(local_dir):
                raise NotADirectoryError(f"本地目录不存在: {local_dir}")

            remote_dir = Path(remote_dir).as_posix()  # 统一转为POSIX路径格式
            self.create_remote_directory(remote_dir)

            for root, _, files in os.walk(local_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    # 计算相对路径，保持目录结构
                    rel_path = os.path.relpath(local_path, local_dir)
                    remote_file_path = Path(remote_dir) / rel_path
                    remote_file_path = remote_file_path.as_posix()  # 转为远程路径格式

                    # 跳过已存在且不覆盖的文件
                    if not overwrite and self.check_path_exists(remote_file_path) and self.check_is_file(
                            remote_file_path):
                        print(f"Skipping existing file: {remote_file_path}")
                        continue

                    # 确保远程父目录存在
                    remote_parent_dir = str(Path(remote_file_path).parent)
                    self.create_remote_directory(remote_parent_dir)

                    print(f"Uploading {local_path} -> {remote_file_path}")
                    self.sftp_client.put(local_path, remote_file_path, callback=self.progress_callback)
            print("✅ 目录上传完成")
            return True
        except Exception as e:
            print(f"❌ 上传失败: {str(e)}")
            traceback.print_exc()
            return False

    def download_files_from_server(self, remote_dir: str, local_dir: str, file_types: list = None) -> bool:
        """从远程服务器下载指定类型文件(支持递归子目录)"""
        try:
            if not self._reconnect():  # 传输前确保连接有效
                raise ConnectionError("下载前无法建立有效连接")

            remote_dir = Path(remote_dir).as_posix()
            if not self.check_path_exists(remote_dir):
                raise FileNotFoundError(f"远程目录不存在: {remote_dir}")

            local_dir = os.path.abspath(local_dir)
            os.makedirs(local_dir, exist_ok=True)

            for entry in self.sftp_client.listdir_attr(remote_dir):
                remote_entry_path = Path(remote_dir) / entry.filename
                remote_entry_path = remote_entry_path.as_posix()

                # 递归处理子目录
                if stat.S_ISDIR(entry.st_mode):
                    sub_local_dir = os.path.join(local_dir, entry.filename)
                    self.download_files_from_server(remote_entry_path, sub_local_dir, file_types)
                else:
                    # 过滤文件类型
                    if file_types and not any(entry.filename.endswith(ext) for ext in file_types):
                        continue

                    local_file_path = FileUtil.recookPath(os.path.join(local_dir, entry.filename))
                    print(f"Downloading {remote_entry_path} -> {local_file_path}")
                    self.sftp_client.get(remote_entry_path, local_file_path, callback=self.progress_callback)
            print(f"✅ 目录下载完成: {remote_dir}")
            return True
        except Exception as e:
            print(f"❌ 下载失败: {str(e)}")
            traceback.print_exc()
            return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()  # 上下文管理器自动释放连接


if __name__ == "__main__":
    # 示例配置(根据实际环境修改)
    SSH_CONFIG = {
        "host": "140.82.x.y",  # 服务器ip
        "username": "root",  # 用户名
        "password": "",  # 密码
        "port": 22  # 端口号
    }
    LOCAL_DIR = 'D:/log/local'  # 本地目录路径
    REMOTE_DIR = '/root/remote/'  # 远程目录路径

    # 使用上下文管理器自动管理连接
    with SSHUtil(**SSH_CONFIG) as ssh:
        # 上传目录(不覆盖已存在文件)
        ssh.upload_directory_to_server(LOCAL_DIR, REMOTE_DIR, overwrite=False)

        # 下载文件(.txt/.png/.jpg)
        ssh.download_files_from_server(REMOTE_DIR, LOCAL_DIR, file_types=['.txt', '.jpg', '.png'])
