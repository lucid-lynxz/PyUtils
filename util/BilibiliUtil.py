import os
import sys
import json
import requests
import you_get
from you_get import common, extractors

from util.FileUtil import FileUtil


class BilibiliUtil:
    """
    B站工具类
    [you-get](https://github.com/soimort/you-get)
    pip install you_get

    也可以直接使用命令行录制:
    you-get -o D:/bilibili_rec -f flv --quality best https://live.bilibili.com/123456
    """

    @staticmethod
    def set_you_get_cookies(cookies_dict):
        """适配所有you-get版本的Cookie设置方法"""
        # 1. 创建原生requests会话，设置Cookie
        sess = requests.Session()
        sess.cookies.clear()
        sess.cookies.update(cookies_dict)

        # 2. 找到you-get真正使用requests的地方（适配新旧版本）
        # 方案A：覆盖extractors的requests（新版本优先）
        try:
            from you_get.extractors import common as extractor_common
            extractor_common.requests = sess
        except ImportError:
            # 方案B：覆盖根目录common的requests（旧版本兼容）
            from you_get import common as root_common
            root_common.requests = sess

    @staticmethod
    def convert_cookie_format(raw_cookie_file: str, target_cookie_file: str = None) -> dict:
        """
        转换Cookie格式（数组→键值对）, 以便you-get工具使用
        把原始的 [{"name":"xxx","value":"xxx"}] 格式转成 {"xxx":"xxx"} 格式
        原始的cookie可以通过 Edge 浏览器插件:https://microsoftedge.microsoft.com/addons/detail/cookieeditor/neaplmfkghagebokkhpjpoebhdledlfi
        打开任意B站视频, 点击Edge浏览器右上角的插件图标, 选择"Export", 选择"Export as"  JSON 或者 Netscape, 会拷贝到剪贴板, 保存为cookie.json文件
        本方法支持转换json的cookie, Netscape格式的不支持
        :param raw_cookie_file: 原始的cookie.json文件路径
        :param target_cookie_file: 转换后的cookie.json文件路径, 默认为原始文件路径
        :return: 转换后的Cookie字典
        """
        if target_cookie_file is None:
            target_cookie_file = raw_cookie_file

        with open(raw_cookie_file, "r", encoding="utf-8") as f:
            raw_cookies = json.load(f)

        # 转换格式
        cookies_dict = {}
        for cookie in raw_cookies:
            if "name" in cookie and "value" in cookie:
                cookies_dict[cookie["name"]] = cookie["value"]

        if len(cookies_dict) > 0:
            # 保存转换后的Cookie
            target_cookie_file = FileUtil.recookPath(target_cookie_file)
            FileUtil.createFile(target_cookie_file)
            with open(target_cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies_dict, f, ensure_ascii=False)
        else:
            cookies_dict = raw_cookies
        return cookies_dict

    @staticmethod
    def download(url, save_dir):
        """
        使用you-get工具录制B站直播
        :param url: B站链接
        :param save_dir: 保存的目录路径

        调用示例：录制B站123456号直播间，保存到D盘
        record_bilibili_live('https://live.bilibili.com/123456', 'D:/bilibili_rec')
        """
        # 构建下载参数
        download_args = {
            'url': url,
            'output_dir': save_dir,
            'merge': True,
            'info_only': False
        }
        common.any_download(**download_args)

    @staticmethod
    def download_with_cookie(url, save_dir, netscape_cookies_path: str = None):
        """
        获取B站直播的直播间地址
        :param url: B站链接, 可以是直播链接也可以是普通视频链接
        :param save_dir: 保存的目录路径
        :param netscape_cookies_path: cookies文件路径, 下载720p及以上需要登录, 请导出 netscape 格式的cookie
        :return:
        """
        # 执行录制
        original_argv = sys.argv
        try:
            netscape_cookies_path = FileUtil.recookPath(netscape_cookies_path)
            if netscape_cookies_path and os.path.exists(netscape_cookies_path):
                # BilibiliUtil.convert_cookie_format(cookies_path)
                sys.argv = ['you-get', url, '-o', save_dir, '--cookies', netscape_cookies_path]
            else:
                sys.argv = ['you-get', url, '-o', save_dir]
            you_get.main()
        finally:
            sys.argv = original_argv


if __name__ == '__main__':
    cache_dir = FileUtil.create_cache_dir(None, __file__)
    cache_bilibili = f'{cache_dir}/bilibili'
    b_netscape_cookie = f'{cache_bilibili}/b_netscape_cookie.txt'
    url = 'https://www.bilibili.com/video/BV1aZzaB3EzT'
    BilibiliUtil.download(url, 'D:/')
    # BilibiliUtil.download_with_cookie(url, 'D:/', b_netscape_cookie)

    # raw_json_cookie = f'{cache_bilibili}/b_cookie.json'
    # target_cookie_file = f'{cache_bilibili}/target_cookie.json'
    # BilibiliUtil.convert_cookie_format(raw_json_cookie, target_cookie_file)
