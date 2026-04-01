import os
import re
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from typing import Optional, Dict, Any
from util.CommonUtil import CommonUtil


class DingTalkBot:
    """
    发送消息到钉钉群机器人
    每个机器人每分钟最多发送20条消息到群里，如果超过20条，会限流10分钟
    文档:https://open.dingtalk.com/document/orgapp/custom-robots-send-group-messages
    """

    def __init__(self, token: str, secret: str = None,
                 app_key: str = None, app_secret: str = None):
        """
        初始化钉钉机器人

        :param token:       钉钉机器人的 Webhook URL 中的 token
        :param secret:      机器人加签密钥（可选）
        :param app_key:     钉钉应用 AppKey（可选，用于 upload_media）
        :param app_secret:  钉钉应用 AppSecret（可选，用于 upload_media）
        """
        _hook_host_url = 'https://oapi.dingtalk.com/robot/send'
        self.access_token: str = token
        self.secret: str = secret
        self.app_key: str = app_key
        self.app_secret: str = app_secret
        self.headers = {"Content-Type": "application/json"}
        self.webhook_url = f'{_hook_host_url}?access_token={token}'
        # app_access_token 缓存
        self._app_token: Optional[str] = None
        self._app_token_expires_at: float = 0

    # ──────────────────────── 发消息 ────────────────────────

    def send_text(self, content: str, is_at_all: bool = False,
                  at_mobiles: list = None) -> Dict[str, Any]:
        """发送纯文本消息"""
        at_mobiles = [] if at_mobiles is None else at_mobiles
        return self._send({
            "msgtype": "text",
            "text": {"content": content},
            "at": {"atMobiles": at_mobiles, "atUserIds": [], "isAtAll": is_at_all}
        })

    def send_link(self, title: str, message_url: str, text: str,
                  pic_url: Optional[str] = None) -> Dict[str, Any]:
        """发送超链接卡片消息"""
        payload = {
            "msgtype": "link",
            "link": {"title": title, "messageUrl": message_url, "text": text}
        }
        if pic_url:
            payload["link"]["picUrl"] = pic_url
        return self._send(payload)

    def send_markdown(self, title: str, markdown_text: str,
                      is_at_all: bool = False, at_mobiles: list = None,
                      max_image_count: int = 4) -> Dict[str, Any]:
        """
        发送 Markdown 消息（支持图片链接和超链接）
        若要在 md 中@所有人或@特定人员：
          1. 在 markdown_text 添加 '@所有人'，并设置 is_at_all=True
          2. 在 markdown_text 添加 '@{手机号}'，并在 at_mobiles 列表中添加该手机号

        
        :param title: 消息标题
        :param markdown_text: Markdown 内容
        :param is_at_all: 是否@所有人
        :param at_mobiles: @特定手机号列表
        :param max_image_count: 单个消息最大图片数，超过会自动拆分发送（默认 5 张）
        """
        at_mobiles = [] if at_mobiles is None else at_mobiles

        # 统计图片数量
        image_urls = re.findall(r'!\[.*?]\((.*?)\)', markdown_text)

        # 如果图片超过限制，拆分发送
        if len(image_urls) > max_image_count:
            return self._send_markdown_batch(title, markdown_text, is_at_all, at_mobiles, max_image_count)

        return self._send({
            "msgtype": "markdown",
            "markdown": {"title": title, "text": markdown_text},
            "at": {"atMobiles": at_mobiles, "isAtAll": is_at_all}
        })

    def send_image(self, pic_url: str, title: str = 'image',
                   is_at_all: bool = False) -> Dict[str, Any]:
        """
        发送图片（Markdown 链接形式，pic_url 需为可访问的在线地址）
        如需上传本地图片，请使用 ImgUploader.upload_local_img()，
        再将返回的 URL 传入本方法。
        """
        return self.send_markdown(title=title,
                                  markdown_text=f"![{title}]({pic_url})",
                                  is_at_all=is_at_all)

    def _send_markdown_batch(self, title: str, markdown_text: str,
                             is_at_all: bool, at_mobiles: list,
                             max_image_count: int) -> Dict[str, Any]:
        """
        分批发送包含多张图片的 Markdown 消息
            
        :return: 返回最后一条消息的结果
        """
        # 提取所有图片链接
        image_pattern = r'!\[(.*?)]\((.*?)\)'
        images = re.findall(image_pattern, markdown_text)

        # 移除所有图片后的纯文本部分
        text_without_images = re.sub(r'!\[.*?]\(.*?\)', '', markdown_text)
        lines = [line.strip() for line in text_without_images.split('\n') if line.strip()]

        CommonUtil.printLog(f"📸 检测到 {len(images)} 张图片，将分批发送（每批最多{max_image_count}张）")

        results = []
        batch_num = 1

        # 按批次发送图片
        for i in range(0, len(images), max_image_count):
            batch_images = images[i:i + max_image_count]
            batch_md_lines = [f"#### {title} (第{batch_num}/{(len(images) + max_image_count - 1) // max_image_count}批)"]

            # 添加文本内容（只在第一批添加）
            if batch_num == 1 and lines:
                batch_md_lines.extend(lines[:10])  # 限制文本行数

            # 添加图片
            for img_title, img_url in batch_images:
                batch_md_lines.append(f"![{img_title}]({img_url})")

            batch_md_text = '\n'.join(batch_md_lines)
            CommonUtil.printLog(f"📤 发送第{batch_num}批...")

            result = self._send({
                "msgtype": "markdown",
                "markdown": {"title": f"{title}_part{batch_num}", "text": batch_md_text},
                "at": {"atMobiles": at_mobiles, "isAtAll": is_at_all}
            })
            results.append(result)
            batch_num += 1

            # 避免限流，批次间延迟 0.5 秒
            if i + max_image_count < len(images):
                time.sleep(0.5)

        CommonUtil.printLog(f"✅ 已分批发送完成，共{len(results)}条消息")
        return results[-1] if results else {"error": "no messages sent"}

    # ──────────────────────── 钉钉原生 media upload ────────────────────────

    def _get_app_access_token(self) -> Optional[str]:
        """获取 app_access_token，带缓存（有效期约 2 小时，提前 5 分钟刷新）"""
        now = time.time()
        if self._app_token and now < self._app_token_expires_at - 300:
            return self._app_token
        if not self.app_key or not self.app_secret:
            return None
        try:
            resp = requests.post(
                "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                headers={"Content-Type": "application/json"},
                json={"appKey": self.app_key, "appSecret": self.app_secret},
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            token = result.get("accessToken", "")
            expire = int(result.get("expireIn", 7200))
            if token:
                self._app_token = token
                self._app_token_expires_at = now + expire
                return token
        except Exception:
            pass
        return None

    def upload_media(self, local_path: str) -> Optional[str]:
        """
        将本地图片上传到钉钉服务器，获取 media_id（永久有效）。
        需要 app_key 和 app_secret 才可使用。

        如需使用图床上传，请使用 ImgUploader.upload_local_img()。

        :param local_path: 本地图片绝对路径
        :return: media_id；失败返回 None
        """
        if not os.path.isfile(local_path):
            CommonUtil.printLog(f"[DingTalkBot] upload_media: 文件不存在 {local_path}")
            return None
        size = os.path.getsize(local_path)
        if size > 10 * 1024 * 1024:
            CommonUtil.printLog(f"[DingTalkBot] upload_media: 文件超过 10MB")
            return None
        token = self._get_app_access_token()
        if not token:
            return None
        filename = os.path.basename(local_path)
        ext = os.path.splitext(filename)[-1].lower().lstrip(".")
        allowed = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
        mime = f"image/{ext}" if ext in allowed else "image/jpeg"
        try:
            with open(local_path, "rb") as f:
                resp = requests.post(
                    "https://api.dingtalk.com/v1.0/media/upload",
                    headers={
                        "x-acs-dingtalk-access-token": token,
                        "Content-Type": "multipart/form-data",
                    },
                    files={"media": (filename, f, mime)},
                    data={"fileName": filename, "fileSize": str(size)},
                    timeout=30,
                )
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode", 0) == 0 or result.get("success"):
                media_id = result.get("mediaId", "")
                CommonUtil.printLog(f"[DingTalkBot] upload_media 成功: {media_id}")
                return media_id
            CommonUtil.printLog(f"[DingTalkBot] upload_media 失败: {result}")
        except Exception as e:
            CommonUtil.printLog(f"[DingTalkBot] upload_media 异常: {e}")
        return None

    def send_local_image(self, local_path: str,
                         is_at_all: bool = False) -> Dict[str, Any]:
        """
        发送本地图片到钉钉群（仅限有 app_key/app_secret 的用户）。
        如需使用图床上传，请使用 ImgUploader.upload_local_img()。
        """
        media_id = self.upload_media(local_path)
        if not media_id:
            return {"error": f"upload_media 失败: {local_path}"}
        return self._send({
            "msgtype": "image",
            "image": {"media_id": media_id},
            "at": {"isAtAll": is_at_all}
        })

    # ──────────────────────── 内部方法 ────────────────────────

    def _generate_url(self) -> str:
        """生成机器人发送消息的 URL（含加签）"""
        if CommonUtil.isNoneOrBlank(self.secret):
            return self.webhook_url
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    def _send(self, data: Dict[str, Any], print_log: bool = True) -> Dict[str, Any]:
        """
        发送请求到钉钉机器人 webhook
        
        注意：钉钉 API 在某些情况下会返回 errcode=-1 但实际发送成功
        特别是当消息包含多个外部图片链接时
        """
        try:
            response = requests.post(self._generate_url(), json=data, headers=self.headers, timeout=15)
            response.raise_for_status()
            result = response.json()

            # 特殊处理：钉钉返回 -1 但有 msgid 表示实际发送成功
            if result.get('errcode') == -1 and result.get('msgid'):
                CommonUtil.printLog(f"⚠️ 钉钉返回系统繁忙但消息已发送 (msgid={result.get('msgid')})", condition=print_log)
                return {'errcode': 0, 'errmsg': 'ok', 'msgid': result.get('msgid'), 'warning': '系统繁忙但已发送'}
        except requests.exceptions.Timeout as e:
            CommonUtil.printLog(f"⚠️ 请求超时，但消息可能已发送：{e}", condition=print_log)
            return {'errcode': 0, 'errmsg': 'timeout_but_may_sent', 'warning': str(e)}
        except requests.exceptions.RequestException as e:
            result = {"error": str(e)}

        CommonUtil.printLog(f"_send result={result}", condition=print_log)
        return result


if __name__ == '__main__':
    _token = 'replace_you_bot_token'
    _secret = 'replace_you_bot_secret'
    _host_url = "https://www.baidu.com"
    _pic_url = 'https://q6.itc.cn/images01/20240821/9617e87d12d744948b311e19ac502bce.png'

    bot = DingTalkBot(token=_token, secret=_secret)

    bot.send_text("测试发送普通文本，world!", is_at_all=True)
    bot.send_link("测试卡片效果", _host_url, "来自百度的链接\n正文多行", pic_url=_pic_url)
    bot.send_markdown('测试 Markdown', f"""# H1 大标题
## H2 小标题
* 小点1
* 小点2
[百度链接]({_host_url})
![图片]({_pic_url})""", is_at_all=False)
