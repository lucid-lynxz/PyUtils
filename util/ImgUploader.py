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
import base64
import requests
from dotenv import load_dotenv
from typing import Optional, Dict

# 让同级的 util.CommonUtil 可以被找到（直接运行时需要）
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil


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

    def upload_local_img(self, local_path: str) -> Optional[str]:
        """
        将本地图片上传到图床，返回图片 URL。

        上传顺序：ImgBB（需 imgbb_key）

        :param local_path: 本地图片绝对路径
        :return: 图片 URL；所有图床均失败返回 None
        """
        if not os.path.isfile(local_path):
            CommonUtil.printLog(f"[ImgUploader] 文件不存在：{local_path}")
            return None

        # ── 图床 1：ImgBB ───────────────────────────────────
        if self.imgbb_key:
            _url = self.upload_to_imgbb(local_path, self.imgbb_key)
            if _url:
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
                # 优先 display_url（高清），fallback 到 url / image.url
                url = (inner.get("display_url")
                       or inner.get("url")
                       or (inner.get("image") or {}).get("url")
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
