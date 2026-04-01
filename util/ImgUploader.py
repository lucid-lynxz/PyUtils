"""
图床统一上传工具
统一入口：ImgUploader().upload_local_img(local_path) -> Optional[str]

支持多种图床，按需启用、更换：
  - ImgBB（默认，已验证可用，国内可访问, 需注册: https://imgbb.com/）

扩展方式：在 upload_local_img 中新增图床实现即可，
          upload_local_img 会自动按顺序尝试，成功即返回
"""
import os
import sys
import time
import base64
import requests
from dotenv import load_dotenv
from typing import Optional, Dict

# 让同级的 util.CommonUtil 可以被找到（直接运行时需要）
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.KVCache import KVCache


class ImgUploader:
    key_imgbb = 'IMGBB_KEY'

    # ─────────────────────────────────────────────────────────
    # 公开入口
    # ─────────────────────────────────────────────────────────

    def __init__(self, env_path: str = None, key_dict: Dict[str, str] = None):
        """
        :param env_path: .env 文件路径, 若为空,则从 ./.env 中读取, 需包含: IMGBB_KEY
        :param key_dict: 也支持外部直接传图床的key信息, 优先级高于 env_path
        """
        local_env = os.path.join(os.getcwd(), ".env")
        env_path = env_path or local_env
        if FileUtil.isFileExist(env_path):
            load_dotenv(env_path)

        self.imgbb_key: str = ''

        # 优先从 key_dict 中读取各图床的key
        if not CommonUtil.isNoneOrBlank(key_dict):
            self.imgbb_key = key_dict.get(ImgUploader.key_imgbb)

        # 然后才读取环境变量中的 key
        self.imgbb_key = self.imgbb_key or os.environ.get(ImgUploader.key_imgbb, "")

        # 创建上传结果缓存: key=图片绝对路径，value={'md5': str, 'url': str}
        cache_dir = FileUtil.create_cache_dir(None, __file__, )
        cache_file = f'{cache_dir}/img_uploader_cache.json'
        self.cache: KVCache[Dict[str, str]] = KVCache(cache_file, save_batch=10)

    def upload_local_img(self, local_path: str, max_retry_cnt: int = 3,
                         use_cache: bool = True) -> Optional[str]:
        """
        将本地图片上传到图床，返回图片 URL。

        上传顺序：ImgBB（需 imgbb_key）

        :param local_path: 本地图片绝对路径
        :param max_retry_cnt: 上传失败时最大重试次数，默认 3 次
        :param use_cache: 是否使用缓存，默认 True
        :return: 图片 URL；所有图床均失败返回 None
        """
        if not os.path.isfile(local_path):
            CommonUtil.printLog(f"[ImgUploader] 文件不存在：{local_path}")
            return None

        # 获取绝对路径作为 cache key
        abs_path = FileUtil.recookPath(local_path)
        # 计算当前文件的 md5
        file_md5 = FileUtil.md5(abs_path)

        # 检查缓存
        if use_cache and self.cache.get(abs_path):
            cache_data = self.cache.get(abs_path)
            cached_md5 = cache_data.get('md5')
            cached_url = cache_data.get('url')

            # md5 一致，说明文件未变化，直接返回缓存的 url
            if cached_md5 and cached_url and cached_md5 == file_md5:
                CommonUtil.printLog(f"[ImgUploader] ✅ 使用缓存：{abs_path}")
                return cached_url
            # else:
            #     CommonUtil.printLog(f"[ImgUploader] ⚠️ 缓存失效 (md5 不匹配)，重新上传：{abs_path}")

        _url = None  # 上传结果url
        for attempt in range(1, max_retry_cnt + 1):
            if not CommonUtil.isNoneOrBlank(_url):
                break

            if self.imgbb_key:  # 图床 1：ImgBB
                _url = self.upload_to_imgbb(local_path, self.imgbb_key)

            if not _url and attempt < max_retry_cnt:
                wait_time = min(2 ** (attempt - 1), 5)  # 指数退避：1s, 2s, 4s, 最多 5s
                CommonUtil.printLog(f"  {wait_time}秒后重试...")
                time.sleep(wait_time)

        if not CommonUtil.isNoneOrBlank(_url):  # 缓存上传结果
            self.cache.set(abs_path, {'md5': file_md5, 'url': _url}).save()
            # CommonUtil.printLog(f"[ImgUploader] 💾 已缓存：{abs_path} -> {_url}")
            return _url

        CommonUtil.printLog(f"[ImgUploader] 所有图床均失败：{local_path}")
        return None

    # ─────────────────────────────────────────────────────────
    # ImgBB 实现
    # 文档：https://api.imgbb.com/
    # ─────────────────────────────────────────────────────────

    def upload_to_imgbb(self, local_path: str, api_key: str = "") -> Optional[str]:
        """
        将本地图片上传到 ImgBB 免费图床，返回图片 URL。

        :param local_path: 本地图片绝对路径
        :param api_key:   ImgBB API Key
        :return: 图片 URL；失败返回 None
        """
        key = api_key or self.imgbb_key
        if not key:
            CommonUtil.printLog("[ImgUploader] upload_to_imgbb: 需要 ImgBB API Key，"
                                "请在 https://api.imgbb.com 注册获取")
            return None

        try:
            with open(local_path, "rb") as f:
                image_data = f.read()
            b64_image = base64.b64encode(image_data).decode("utf-8")

            resp = requests.post(
                "https://api.imgbb.com/1/upload",
                params={"key": key},
                data={"image": b64_image, "name": os.path.basename(local_path)},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                inner = data.get("data") or {}
                # 优先使用原图 URL，避免图床压缩
                # 优先级：image.url (原图) > url (标准) > display_url (预览压缩图)
                url = ((inner.get("image") or {}).get("url")
                       or inner.get("url")
                       or inner.get("display_url")
                       or "")
                if url:
                    CommonUtil.printLog(f"[ImgUploader] 上传到 ImgBB 成功：{url}")
                    return url

            CommonUtil.printLog(f"[ImgUploader] upload_to_imgbb 失败: {data}")
        except Exception as e:
            CommonUtil.printLog(f"[ImgUploader] upload_to_imgbb 异常: {e}")
        return None


if __name__ == "__main__":
    # 方式1：从 .env 文件加载（放在当前工作目录下，或传入绝对路径）
    uploader = ImgUploader()
    # 方式2：从指定路径加载
    # uploader = ImgUploader(env_path=r"H:\Workspace\Python\PyUtils\util\.env")
    # 方式3：跳过 .env，直接使用代码中定义的 key
    # uploader = ImgUploader(env_path="")
    # uploader.imgbb_key = "your_key_here"

    _pic = r"H:/Pictures/test.jpg"
    url = uploader.upload_local_img(_pic)
    print(f"图片 URL：{url}")
