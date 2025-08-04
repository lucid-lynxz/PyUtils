# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import traceback
import fnmatch  # 用于路径通配符匹配

import requests
from bs4 import BeautifulSoup  # 需要安装: pip install beautifulsoup4


class HTTPUtil(object):
    """
    通过HTTP协议下载Nginx映射的目录内容
    依赖: requests, beautifulsoup4
    安装依赖: pip install requests beautifulsoup4
    """

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip('/') + '/'  # 确保URL以/结尾
        self.timeout = timeout
        self.session = requests.Session()
        # 可以添加headers模拟浏览器请求
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def _parse_directory_index(self, url: str) -> tuple[list[str], list[str]]:
        """解析目录索引页面，返回(文件列表, 子目录列表)"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()  # 检查HTTP错误状态

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')  # 获取所有链接

            files = []
            dirs = []

            for link in links:
                href = link.get('href', '').strip()
                if not href or href.startswith(('?', '#', '/')):  # 过滤无效链接和绝对路径
                    continue

                # Nginx通常会在目录链接后加/，文件链接则不会
                if href.endswith('/'):
                    dirs.append(href.rstrip('/'))
                else:
                    files.append(href)

            return files, dirs

        except Exception as e:
            raise RuntimeError(f"解析目录失败 {url}: {str(e)}")

    def _download_file(self, remote_url: str, local_path: str):
        """下载单个文件"""
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            with self.session.get(remote_url, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            self.progress_callback(downloaded_size, total_size)
            print(f"\n✅ 下载完成: {local_path}")

        except Exception as e:
            raise RuntimeError(f"下载文件失败 {remote_url}: {str(e)}")

    @staticmethod
    def progress_callback(transferred: int, total: int):
        """传输进度回调函数"""
        if total == 0:
            return
        progress = (transferred / total) * 100
        print(f"\r下载进度: {transferred}/{total} bytes ({progress:.2f}%)", end="")

    def download_directory(self, remote_dir: str = '', local_dir: str = '.', path_pattern: str = None) -> bool:
        """
        下载远程目录到本地
        :param remote_dir: 远程目录路径(相对于base_url)
        :param local_dir: 本地保存目录
        :param path_pattern: 文件路径匹配模式(如'*/demolog/*.txt')，使用Unix风格通配符，为None时下载所有文件
        """
        try:
            current_url = f"{self.base_url}{remote_dir.lstrip('/')}"
            if not current_url.endswith('/'):
                current_url += '/'

            print(f"正在解析目录: {current_url}")
            files, dirs = self._parse_directory_index(current_url)

            # 下载当前目录文件（添加路径过滤）
            for file in files:
                # 构建相对路径并标准化分隔符为'/'（统一URL风格）
                relative_file_path = os.path.join(remote_dir, file).replace(os.sep, '/')

                # 路径模式过滤（如匹配任意层级demolog目录下的txt文件）
                if path_pattern and not fnmatch.fnmatch(relative_file_path, path_pattern):
                    continue

                file_url = f"{current_url}{file}"
                local_path = os.path.join(local_dir, remote_dir, file)
                print(f"\n开始下载: {file_url}")
                self._download_file(file_url, local_path)

            # 递归下载子目录（传递路径过滤参数）
            for dir_name in dirs:
                sub_remote_dir = f"{remote_dir}/{dir_name}".lstrip('/')
                self.download_directory(sub_remote_dir, local_dir, path_pattern)  # 传递path_pattern参数

            print(f"📂 目录下载完成: {os.path.join(local_dir, remote_dir)}")
            return True

        except Exception as e:
            print(f"❌ 目录下载失败: {str(e)}")
            traceback.print_exc()
            return False

    def close(self):
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # HTTP下载示例
    HTTP_BASE_URL = "http://example.com/nginx-mapped-directory/"  # 替换为实际的目录URL
    LOCAL_SAVE_DIR = "D:/http_downloads"  # 本地保存路径

    with HTTPUtil(base_url=HTTP_BASE_URL) as http:
        # 下载任意层级下demolog目录中的所有txt文件
        # */demolog/*.txt 表示: 任意目录/ demolog目录/ 任意名称.txt
        http.download_directory(local_dir=LOCAL_SAVE_DIR, path_pattern="*/demolog/*.txt")