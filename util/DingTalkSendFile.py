import requests
import json
from typing import Union


class DingTalkSendFile:
    """
    * 钉钉发送文件到企业群中
    * 来源: https://zhuanlan.zhihu.com/p/679429562
    * 实测发送得文件/图片都无法预览, 需要下载后查看, 下载的文件都是 .file 后缀, 还需要自行修改
    *
    * 操作:
    * 1. 创建钉钉应用:https://open-dev.dingtalk.com/fe/app#/appMgr/inner/eapp/1484669569/2
    * 2. https://open-dev.dingtalk.com/，获取CorpId(网页右上角)
    * 3. 进入开发者后台应用开发/企业内部应用/钉钉应用，选中应用点击右侧扩展菜单的应用详情，点击左上角的凭证与基础信息获取AppKey(Client ID)，AppSecret(Client Secret)
    * 4. 获取群聊chat_id:
    *   4.1 进入 https://open.dingtalk.com/tools/explorer/jsapi?id=10303
    *   4.2 左侧栏选择chooseChat，手机钉钉扫右侧二维码，登录钉钉开发者后台之后corpId默认填充不用填，isAllowCreateGroup和filterNotOwnerGroup选False
    *   4.3 右侧点运行调试，在手机上选中接受文件的群获取 chatid
    * 5. 调用 send_file(path) 方法传入本地文件路径进行发送
    """

    # ----------------------------------------------------------------------------------------------------
    def __init__(self, app_key: str, app_secret: str, chat_id: str):
        self.client_id = app_key  # 用户id appKey
        self.client_secret = app_secret  # 用户密码  appSecret
        self.chat_id = chat_id  # 企业群聊id
        self.access_token: str = ''

    # ----------------------------------------------------------------------------------------------------
    def get_access_token(self):
        """
        获取接口凭证
        """
        url = f"https://oapi.dingtalk.com/gettoken?appkey={self.client_id}&appsecret={self.client_secret}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json().get("access_token")
        except requests.RequestException as err:
            print(f"获取access_token失败，错误信息：{err}")
            return None

    # ----------------------------------------------------------------------------------------------------
    def get_media_id(self, file_path: str):
        """
        获取文件media_id
        """
        self.access_token = self.get_access_token()  # 接口凭证，值不固定每次调用前获取
        url = f"https://oapi.dingtalk.com/media/upload?access_token={self.access_token}&type=file"
        try:
            with open(file_path, "rb") as file:
                files = {"media": file}
                response = requests.post(url, files=files)
                response.raise_for_status()
                data = response.json()
                if data["errcode"]:
                    print(f"获取media_id失败，错误信息：{data['errmsg']}")
                    return ""
                return data["media_id"]
        except requests.RequestException as err:
            print(f"上传文件失败，错误信息：{err}")
            return ""

    # ----------------------------------------------------------------------------------------------------
    def send_file(self, file_path: str):
        """
        * 发送文件到钉钉
        """
        media_id = self.get_media_id(file_path)
        if not media_id:
            return

        url = f"https://oapi.dingtalk.com/chat/send?access_token={self.access_token}"
        payload = {
            "chatid": self.chat_id,
            "msg": {
                "msgtype": "file",
                "file": {"media_id": media_id}
            }
        }

        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            data = response.json()
            if data["errcode"]:
                print(f"发送文件出错，错误代码：{data['errcode']}，错误信息：{data['errmsg']}")
        except requests.RequestException as err:
            print(f"发送文件请求出错，错误信息：{err}")


if __name__ == '__main__':
    # 实例化类
    sendFileUtil = DingTalkSendFile(app_key='dingawz6kljlkwvfjhlk', app_secret='gqAbiGv6iYcWYq0Q7zCDhaN3EF26vo9fwP4N_vph8XJGJs_6eN2OzfEA7ABqUfxJ',
                                    chat_id='chat2ecc29e3838be6ca44f793b36b4aa870')
    sendFileUtil.send_file(r'H:\Pictures\拯救姬3.jpg')
