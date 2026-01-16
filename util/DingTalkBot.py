import requests
from typing import Optional, Dict, Any
from util.CommonUtil import CommonUtil


class DingTalkBot:
    """
    发送消息到钉钉群机器人
    每个机器人每分钟最多发送20条消息到群里，如果超过20条，会限流10分钟
    文档:https://open.dingtalk.com/document/orgapp/custom-robots-send-group-messages
    """

    def __init__(self, token: str, secret: str = None):
        """
        初始化钉钉机器人
        :param token: 钉钉机器人的 Webhook URL 中的token信息
        :param secret: 启用机器人加签模式,传入 secret参数
        """
        _hook_host_url = 'https://oapi.dingtalk.com/robot/send'
        self.access_token: str = token
        self.secret: str = secret
        self.headers = {"Content-Type": "application/json"}
        self.webhook_url = f'{_hook_host_url}?access_token={token}'

    def send_text(self, content: str, is_at_all: bool = False, at_mobiles: list = None) -> Dict[str, Any]:
        """
        发送纯文本消息

        :param content: 文本内容
        :param is_at_all: 是否@所有人
        :return: 响应结果
        """
        at_mobiles = [] if at_mobiles is None else at_mobiles
        data = {
            "at": {
                "atMobiles": at_mobiles,
                "atUserIds": [],
                "isAtAll": is_at_all
            },
            "text": {
                "content": content
            },
            "msgtype": "text"
        }

        return self._send(data)

    def send_link(self, title: str, message_url: str, text: str, pic_url: Optional[str] = None) -> Dict[str, Any]:
        """
        发送超链接卡片消息

        :param title: 标题
        :param message_url: 超链接地址
        :param text: 消息正文
        :param pic_url: 图片地址（可选）
        :return: 响应结果
        """
        data = {
            "msgtype": "link",
            "link": {
                "title": title,
                "messageUrl": message_url,
                "text": text
            },
        }
        if pic_url:
            data["link"]["picUrl"] = pic_url
        return self._send(data)

    def send_image(self, pic_url: str, title: str = 'image', is_at_all: bool = False) -> Dict[str, Any]:
        """
        发送图片
        :param pic_url: 图片网址
        :param title: 图片标题, 请勿传空
        :param is_at_all: 是否@所有人
        """
        return self.send_markdown(title=title, markdown_text=f"![{title}]({pic_url})", is_at_all=is_at_all)

    def send_markdown(self, title: str, markdown_text: str, is_at_all: bool = False) -> Dict[str, Any]:
        """
        发送 Markdown 格式消息（支持图片和超链接）

        :param title: 消息会话列表中展示的标题，非消息体的标题
        :param markdown_text: Markdown 内容
        :param is_at_all: 是否@所有人
        :return: 响应结果
        """
        data = {
            "at": {
                "isAtAll": is_at_all
            },
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown_text
            }
        }
        return self._send(data)

    def _generate_url(self):
        """
        生成钉钉机器人通知的url, 主要是处理加签模式下的url
        """
        if CommonUtil.isNoneOrBlank(self.secret):
            return self.webhook_url
        else:
            import time
            import hmac
            import hashlib
            import base64
            import urllib.parse
            import requests
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f'{timestamp}\n{self.secret}'
            hmac_code = hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            return f'{self.webhook_url}&timestamp={timestamp}&sign={sign}'

    def _send(self, data: Dict[str, Any], print_log: bool = True) -> Dict[str, Any]:
        """
        发送请求到钉钉机器人

        :param data: 构建好的消息数据
        :return: 响应结果
        """
        try:
            url = self._generate_url()
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            result = {"error": str(e)}

        if print_log:
            CommonUtil.printLog(f"_send result={result}, reqData={data}")
        return result


if __name__ == '__main__':
    _host_url = "https://www.baidu.com"
    _pic_url = 'https://q6.itc.cn/images01/20240821/9617e87d12d744948b311e19ac502bce.png'
    _token = 'replace_you_bot_token'
    _secret = 'you_bot_secret'

    bot = DingTalkBot(token=_token, secret=_secret)
    bot.send_text("测试发送普通文本, world!2_189", is_at_all=True)
    bot.send_link("测试卡片效果333", _host_url, "来自百度的链接\n正文多行带图片", pic_url=_pic_url)

    # 发送markdown文本,包含文字/图片/超链接
    bot.send_markdown('测试markdown效果+超链接+图片', f"""
    # H1大标题 仅@lynxz 33
      这是正文

    ## H2小标题
    * 小点1
    * 小点2

    [超链接-baidu]({_host_url})
    ![图片链接]({_pic_url})""", False)

    # 仅发送一张图片
    bot.send_image(_pic_url, is_at_all=True)
