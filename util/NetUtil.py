# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import re
import json
import socket
import traceback
import urllib.request as urllib2
from urllib.error import URLError, HTTPError

from util.CommonUtil import CommonUtil
from util.DingTalkBot import DingTalkBot
from util.TimeUtil import TimeUtil
from util.FileUtil import FileUtil


class NetUtil(object):
    robot_dict: dict = dict()  # 默认的机器人配置信息, 用于发送通知,具体字段见 push_to_robot 方法

    @staticmethod
    def push_to_robot(content: str, configDict: dict = None, printLog: bool = True,
                      with_time: bool = True) -> bool:
        """
        自动按需发送普通文本给钉钉/飞书自定义机器人
        :param content: 普通文本消息
        :param configDict: config.ini 中配置的机器人信息, 应包含以下内容:
              通用字段: keyWord,atAll,extraInfo
              飞书: feishuToken
              钉钉: accessToken,atPhone,
              各字段解释如下:
              keyWord: str 机器人要求的关键词, 根据机器人设置而变化,默认可放空
              atAll: bool 是否at所有人
              extraInfo: str 所有消息都要额外拼接的固定内容, 可放空
              feishuToken: 飞书机器人链接中的token信息
              accessToken: 钉钉机器人中的accessToken
              atPhone: 钉钉机器人支持at特定人员,此处填写手机号, 可多个,逗号分隔
        :param printLog: 是否打印日志, 默认为False
        :param with_time: 是否在消息前面加上时间, 默认为 True
        """
        if CommonUtil.isNoneOrBlank(content):
            return False
        if printLog:
            CommonUtil.printLog(f'push_to_robot content={content}')

        configDict = NetUtil.robot_dict if configDict is None else configDict
        if configDict is None:
            return False
        keyWord = configDict.get('keyWord', '')
        extraInfo = configDict.get('extraInfo', '')
        extraInfo = '' if CommonUtil.isNoneOrBlank(extraInfo) else f'{extraInfo}\n'
        timeInfo = TimeUtil.getTimeStr("%H:%M:%S") if with_time else ''
        content = f'{keyWord} {timeInfo}\n{extraInfo}{content}'
        content = content.strip()

        atAll = configDict.get('atAll', 'False') == 'True'

        ddAccessToken = configDict.get('accessToken', '')
        ddSecret = configDict.get('secret', '')
        atPhone = configDict.get('atPhone', '')
        fsToken = configDict.get('feishuToken', '')
        if CommonUtil.isNoneOrBlank('%s%s' % (ddAccessToken, fsToken)):
            return False
        # CommonUtil.printLog(f'ddAccessToken={ddAccessToken},fsToken={fsToken}---')
        if not CommonUtil.isNoneOrBlank(ddAccessToken):
            NetUtil.push_ding_talk_robot(content, ddAccessToken, atAll, at_mobiles=atPhone.split(','), secret=ddSecret)
        if not CommonUtil.isNoneOrBlank(fsToken):
            NetUtil.push_feishu_robot(content, fsToken, atAll)
        return True

    @staticmethod
    def push_ding_talk_robot(content: str,
                             access_token: str,
                             is_at_all: bool = False,
                             at_mobiles: list = '',
                             secret: str = None) -> str:
        """
        发送文本消息到钉钉机器人
        文档:  https://developers.dingtalk.com/document/robots/custom-robot-access
        :param content: 待发送的内容
        :param access_token: 机器人token,必填
        :param is_at_all: 是否@所有人
        :param at_mobiles: @指定人员,填入对应人员的手机号列表, 如: ['123', '456']
        :param secret: 钉钉机器人开启加签模式时需要使用,非空有效
        """
        result = DingTalkBot(token=access_token, secret=secret).send_text(content, is_at_all, at_mobiles)
        ddResult = json.dumps(result, default=str)
        CommonUtil.printLog(f'push_ding_talk_robot result={ddResult}')
        return ddResult
        # headers = {"Content-type": "application/json"}
        # json_data_obj = {
        #     "at": {
        #         "atMobiles": at_mobiles,
        #         "atUserIds": [],
        #         "isAtAll": is_at_all
        #     },
        #     "text": {
        #         "content": content
        #     },
        #     "msgtype": "text"
        # }
        # CommonUtil.printLog(f'data_obj:{json_data_obj}')
        # # 将str类型转换为bytes类型
        # json_data_obj = json.dumps(json_data_obj).encode('utf-8')
        # # json_data_obj = urllib.parse.urlencode(json_data_obj).encode("utf-8")
        # request = urllib2.Request(url='https://oapi.dingtalk.com/robot/send?access_token=%s' % access_token,
        #                           data=json_data_obj,
        #                           headers=headers, method="POST")
        # response = urllib2.urlopen(request)
        # ddResult = response.read().decode('utf-8')
        # CommonUtil.printLog(f'push_ding_talk_robot result={ddResult}')
        # return ddResult

    @staticmethod
    def push_feishu_robot(content: str,
                          access_token: str,
                          is_at_all: bool = False, ) -> str:
        """
        发送普通文本消息到飞书自定义机器人
        官方文档: https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN
        """
        headers = {"Content-type": "application/json"}
        atAllOpt = '\n<at user_id=\"all\">所有人</at>' if is_at_all else ''
        json_data_obj = {
            "content": {
                "text": "%s%s" % (content, atAllOpt)
            },
            "msg_type": "text"
        }
        # CommonUtil.printLog(f'data_obj={json_data_obj}')
        # 将str类型转换为bytes类型
        json_data_obj = json.dumps(json_data_obj).encode('utf-8')
        # json_data_obj = urllib.parse.urlencode(json_data_obj).encode("utf-8")
        request = urllib2.Request(url='https://open.feishu.cn/open-apis/bot/v2/hook/%s' % access_token,
                                  data=json_data_obj,
                                  headers=headers, method="POST")
        try:
            response = urllib2.urlopen(request)
            fsResult = response.read().decode('utf-8')
            CommonUtil.printLog(f'push_feishu_robot result={fsResult}')
            return fsResult
        except Exception as e:
            traceback.print_exc()
            CommonUtil.printLog(f'push_feishu_robot fail url={request.full_url} {e}')
            return 'fail'

    @staticmethod
    def getIp() -> str:
        """
        获取本机ip
        """
        ip = socket.gethostbyname(socket.gethostname())
        # s: socket = None
        # try:
        #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #     s.connect(('8.8.8.8', 80))
        #     ip = s.getsockname()[0]
        # finally:
        #     if s is not None:
        #         s.close()
        CommonUtil.printLog(f'ip={ip}')
        return ip

    @staticmethod
    def download(url: str, save_path: str = '', **kwargs) -> str:
        """
         通过get形式下载文件
         :param url: 文件下载地址
         :param save_path: 本地保存地址,,默认保存在当前目录下
         :param kwargs: 如: auth=('账号', '密码'), timeout=10
         :return: 本地文件路径, 空表示下载失败
         """
        if CommonUtil.isNoneOrBlank(url):
            return ''

        regex = re.compile(r'^(https?|ftp)://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
        if re.match(regex, url):
            filename = url.split("/")[-1]

            if CommonUtil.isNoneOrBlank(save_path):
                save_path = f'./{filename}'
            elif save_path.endswith('/'):
                save_path = f'{save_path}{filename}'

            CommonUtil.printLog(f'download started:{filename}')
            try:
                # 创建请求对象并处理认证
                headers = {}
                auth = kwargs.get('auth')
                if auth:
                    import base64
                    username, password = auth
                    credentials = f'{username}:{password}'.encode('utf-8')
                    b64_credentials = base64.b64encode(credentials).decode('utf-8')
                    headers['Authorization'] = f'Basic {b64_credentials}'

                # 创建支持重定向的opener
                opener = urllib2.build_opener(urllib2.HTTPRedirectHandler(), urllib2.HTTPSHandler())
                urllib2.install_opener(opener)

                req = urllib2.Request(url, headers=headers)
                timeout = kwargs.get('timeout', 10)
                response = urllib2.urlopen(req, timeout=timeout)

                # 获取重定向后的最终URL文件名（如果需要）
                final_url = response.geturl()
                if final_url != url:
                    final_filename = final_url.split("/")[-1]
                    # 如果原始URL没有文件名或者最终URL的文件名不同，则更新文件名
                    if (not filename or '?' in filename or filename == final_url.split('/')[-2] + '/'):
                        if CommonUtil.isNoneOrBlank(save_path) or save_path.endswith('/') or save_path.endswith(filename):
                            save_path = save_path.rsplit('/', 1)[0] + '/' + final_filename if '/' in save_path else final_filename
                        CommonUtil.printLog(f'Redirected to {final_url}, using filename: {final_filename}')

                # 获取文件总大小
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded_size = 0
                start_ms = TimeUtil.currentTimeMillis()

                with open(save_path, "wb") as f:
                    while True:
                        chunk = response.read(4096)  # 分块读取
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # 计算并打印进度
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            print(f"\rDownload progress: {progress}%", end='', flush=True)
                            if progress >= 100:
                                duration_sec = (TimeUtil.currentTimeMillis() - start_ms) / 1000
                                file_size = FileUtil.format_size(total_size)
                                avg_speed = FileUtil.format_speed(total_size / duration_sec) if duration_sec > 0 else "0 B/s"
                                CommonUtil.printLog(f'file size:{file_size},consume:{duration_sec:.2f}s,avg speed:{avg_speed}', prefix='\n')
                CommonUtil.printLog(f'download finish,save_path={save_path}')
                return save_path
            except HTTPError as e:
                CommonUtil.printLog(f'download HTTP error: {e.code} {e.reason}')
                return ''
            except URLError as e:
                CommonUtil.printLog(f'download URL error: {e.reason}')
                return ''
            except Exception as e:
                CommonUtil.printLog(f'download fail: {str(e)}')
                return ''
        return ''


if __name__ == '__main__':
    _url = "https://tac.gientech.com/tac/download/mobile/software/SecID.apk"
    NetUtil.download(_url, './cache/')
