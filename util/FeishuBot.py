import base64
import hashlib
import hmac
import json, re
import time
import traceback
import requests
import urllib.request as urllib2
from typing import Optional

from util.CommonUtil import CommonUtil


class FeishuBot:
    """
    飞书机器人
    需要安装 lark-markdown-to-rich-text
    """

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

        if markdown:
            self.send_markdown(content)
            return ''

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

    def send_markdown(self, markdown_text: str, title: str = "Markdown消息", is_at_all: bool = False):
        rich_content = FeishuBot.markdown_to_feishu_rich_text(markdown_text)
        atAllOpt = '\n<at user_id="all">所有人</at>' if is_at_all else ''

        message = {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": title,
                        "content": f'{rich_content}{atAllOpt}'
                    }
                }
            }
        }

        resp = requests.post(
            url=self.webhook_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(message, ensure_ascii=False)
        )
        return resp.json()

    @staticmethod
    def markdown_to_feishu_rich_text(md_text: str) -> list:
        """
        飞书机器人专用：Markdown 转 富文本
        官方文档: https://open.feishu.cn/document/common-capabilities/message-card/message-cards-content/using-markdown-tags?lang=zh-CN
        支持：
        - 标题 # / ## / ###
        - 加粗 **text**
        - 无序列表 - / *
        - 超链接 [文字](链接)
        - 图片 ![](图片URL)
        """
        content = []
        lines = md_text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # ----------------------
            # 1. 图片：![alt](url)
            # ----------------------
            img_pattern = r"!\[.*?\]\((.+?)\)"
            img_match = re.fullmatch(img_pattern, line)
            if img_match:
                img_url = img_match.group(1).strip()
                content.append([
                    {"tag": "img", "image_key": img_url}
                ])
                continue

            # ----------------------
            # 2. 标题 # / ## / ###
            # ----------------------
            if line.startswith("# "):
                content.append([
                    {"tag": "text", "text": line[2:], "style": {"bold": True}}
                ])
                continue
            if line.startswith("## "):
                content.append([
                    {"tag": "text", "text": "▪ " + line[3:]}
                ])
                continue
            if line.startswith("### "):
                content.append([
                    {"tag": "text", "text": "▫ " + line[4:]}
                ])
                continue

            # ----------------------
            # 3. 列表 - / *
            # ----------------------
            is_list = False
            if line.startswith("- ") or line.startswith("* "):
                line = "• " + line[2:]
                is_list = True

            # ----------------------
            # 4. 解析一行内的所有样式：链接 + 加粗
            # ----------------------
            parts = []
            patterns = {
                "link": r"\[([^\]]+)\]\(([^)]+)\)",  # [文本](链接)
                "bold": r"\*\*(.*?)\*\*",  # **加粗**
            }

            tokens = []
            text_ptr = 0

            # 扫描所有链接、加粗
            for pat_name, pat in patterns.items():
                for m in re.finditer(pat, line):
                    tokens.append((m.start(), m.end(), pat_name, m))

            # 按位置排序
            tokens = sorted(tokens, key=lambda x: x[0])

            # 逐段解析
            for start, end, typ, m in tokens:
                if start > text_ptr:
                    txt = line[text_ptr:start]
                    parts.append({"tag": "text", "text": txt})

                if typ == "link":
                    text = m.group(1)
                    href = m.group(2)
                    parts.append({"tag": "a", "text": text, "href": href})
                elif typ == "bold":
                    text = m.group(1)
                    parts.append({"tag": "text", "text": text, "style": {"bold": True}})

                text_ptr = end

            # 剩余文本
            if text_ptr < len(line):
                parts.append({"tag": "text", "text": line[text_ptr:]})

            if parts:
                content.append(parts)

        return content


if __name__ == '__main__':
    feishuBot = FeishuBot(token='f0da0f8b-1208-4316-99d5-d750b9b4c3d5', secret='E72zioma5UzrvRiZGVZzjh')
    md_msg = f"""
王世辰】2026-05-06 15:38:58
今日知识点小结：\n![img_v3_0211e_4b2218d5-fef5-40f6-9161-4fe78abf057g_part_0_5](https://i.ibb.co/ZzH2rK1J/20260506-160150-a6cd3111-p1-img-v3-0211e-4b2218d5-fef5-40f6-9161-4fe78abf057g-part1-png.png)
\n![img_v3_0211e_4b2218d5-fef5-40f6-9161-4fe78abf057g_part_1_5](https://i.ibb.co/r2GPnfNC/20260506-160150-a6cd3111-p1-img-v3-0211e-4b2218d5-fef5-40f6-9161-4fe78abf057g-part2-png.png)
"""
    feishuBot.send_msg(md_msg, markdown=True, is_at_all=True)
