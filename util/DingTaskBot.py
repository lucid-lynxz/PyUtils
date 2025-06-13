import requests
from typing import Optional, Dict, Any


class DingTalkBot:
    """
    发送消息到钉钉群机器人
    每个机器人每分钟最多发送20条消息到群里，如果超过20条，会限流10分钟
    文档:https://open.dingtalk.com/document/orgapp/custom-robots-send-group-messages
    """

    def __init__(self, token: str):
        """
        初始化钉钉机器人
        :param token: 钉钉机器人的 Webhook URL 中的token信息
        """
        _hook_host_url = 'https://oapi.dingtalk.com/robot/send'
        self.webhook_url = f'{_hook_host_url}?access_token={token}'
        self.headers = {"Content-Type": "application/json"}

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

    def _send(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送请求到钉钉机器人

        :param data: 构建好的消息数据
        :return: 响应结果
        """
        try:
            response = requests.post(self.webhook_url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}


if __name__ == '__main__':
    host_url = "https://www.baidu.com"
    pic_url = 'https://q6.itc.cn/images01/20240821/9617e87d12d744948b311e19ac502bce.png'
    token = 'replace_you_bot_token'

    bot = DingTalkBot(token=token)
    # bot.send_text("测试发送普通文本, world!2_189",is_at_all=True)
    bot.send_link("测试卡片效果333", host_url, "来自百度的链接\n正文多行带图片", pic_url=pic_url)

    # bot.send_markdown('测试markdown效果+超链接+图片', f"""
    # # H1大标题 仅@zxz 33
    #   这是正文
    #
    # ## H2小标题
    # * 小点1
    # * 小点2
    #
    # [超链接-baidu]({host_url})
    # ![图片链接]({pic_url})""", False)
