import base64
import hashlib
import hmac
import json
import time
import traceback
import urllib.request as urllib2
from typing import Optional

from util.CommonUtil import CommonUtil


class FeishuBot:
    """飞书机器人"""

    def __init__(self, token: str, secret: str = None, keyword: list[str] = None):
        """
        初始化飞书机器人

        @param token:       飞书机器人的 Webhook URL 中的 token
        @param secret:      机器人加签密钥（可选）
        @param keyword:     机器人自定义关键词(可选), 支持多个,任意一个命中即可
        """
        _hook_host_url = 'https://open.feishu.cn/open-apis/bot/v2/hook/'
        self.access_token: str = token
        self.secret: str = secret
        self.headers = {"Content-Type": "application/json"}
        self.webhook_url = f'{_hook_host_url}/{token}'
        self.keyword = keyword

    def gen_sign(self, timestamp) -> Optional[str]:
        """
        飞书签名校验: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot?lang=zh-CN#9fe10f9b
        @param timestamp: 时间戳(秒)
        """
        if CommonUtil.isNoneOrBlank(self.secret):
            return None
        # 拼接timestamp和secret
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        # 对结果进行base64处理
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign

    def send_msg(self, content: str,
                 is_at_all: bool = False,
                 markdown: bool = False) -> str:
        """
        发送普通文本消息到飞书自定义机器人
        官方文档: https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
        :param content: 待发送的内容
        :param is_at_all: 是否@所有人
        :param markdown: 是否发送markdown文本,默认为False(暂未支持)
        """
        # atAllOpt = '<at id=all></at>' if is_at_all else ''
        atAllOpt = '\n<at user_id="all">所有人</at>' if is_at_all else ''

        if not CommonUtil.isNoneOrBlank(self.keyword):
            hit = False
            for keyword in self.keyword:
                if keyword in content:
                    hit = True
                    break
            if not hit:
                content = f'{self.keyword[0]} {content}'.strip()

        # 飞书支持 \n <br> <br/>字符: https://open.feishu.cn/document/common-capabilities/message-card/message-cards-content/using-markdown-tags?lang=zh-CN
        content = content.replace('<br>', '\n').replace('</br>', '\n')
        if markdown:
            # Markdown 格式消息
            json_data_obj = {
                "content": {"post": {"zh_cn": {"title": "markdown_msg", "content": [[{"tag": "text", "text": f'{content}{atAllOpt}'}]]}}},
                "msg_type": "post"
            }
        else:
            # 普通文本消息
            json_data_obj = {
                "content": {
                    "text": f'{content}{atAllOpt}'
                },
                "msg_type": "text"
            }

        # 添加签名
        timestamp = str(round(time.time()))
        sign = self.gen_sign(timestamp)
        if not CommonUtil.isNoneOrBlank(sign):
            json_data_obj['timestamp'] = timestamp
            json_data_obj['sign'] = sign

        # CommonUtil.printLog(f'data_obj={json_data_obj}')
        # 将str类型转换为bytes类型
        json_data_obj = json.dumps(json_data_obj).encode('utf-8')
        # json_data_obj = urllib.parse.urlencode(json_data_obj).encode("utf-8")
        request = urllib2.Request(url=self.webhook_url,
                                  data=json_data_obj,
                                  headers=self.headers, method="POST")
        try:
            response = urllib2.urlopen(request)
            fsResult = response.read().decode('utf-8')
            CommonUtil.printLog(f'push_feishu_robot result={fsResult}')
            return fsResult
        except Exception as e:
            traceback.print_exc()
            CommonUtil.printLog(f'push_feishu_robot fail url={request.full_url} {e}')
            return 'fail'
