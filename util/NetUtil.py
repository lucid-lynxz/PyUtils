# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import re
import json
import socket
import requests
import traceback
import urllib.request as urllib2

from util.CommonUtil import CommonUtil
from util.DingTaskBot import DingTalkBot
from util.TimeUtil import TimeUtil


class NetUtil(object):
    robot_dict: dict = dict()  # 默认的机器人配置信息, 用于发送通知,具体字段见 push_to_robot 方法

    @staticmethod
    def push_to_robot(content: str, configDict: dict = None, printLog: bool = False,
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
        # print(f'ddAccessToken={ddAccessToken},fsToken={fsToken}---')
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
        print(f'push_ding_talk_robot result={ddResult}')
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
        # print('data_obj', json_data_obj)
        # # 将str类型转换为bytes类型
        # json_data_obj = json.dumps(json_data_obj).encode('utf-8')
        # # json_data_obj = urllib.parse.urlencode(json_data_obj).encode("utf-8")
        # request = urllib2.Request(url='https://oapi.dingtalk.com/robot/send?access_token=%s' % access_token,
        #                           data=json_data_obj,
        #                           headers=headers, method="POST")
        # response = urllib2.urlopen(request)
        # ddResult = response.read().decode('utf-8')
        # print('push_ding_talk_robot result=%s' % ddResult)
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
        # print('data_obj', json_data_obj)
        # 将str类型转换为bytes类型
        json_data_obj = json.dumps(json_data_obj).encode('utf-8')
        # json_data_obj = urllib.parse.urlencode(json_data_obj).encode("utf-8")
        request = urllib2.Request(url='https://open.feishu.cn/open-apis/bot/v2/hook/%s' % access_token,
                                  data=json_data_obj,
                                  headers=headers, method="POST")
        try:
            response = urllib2.urlopen(request)
            fsResult = response.read().decode('utf-8')
            print('push_feishu_robot result=%s' % fsResult)
            return fsResult
        except Exception as e:
            traceback.print_exc()
            print(f'push_feishu_robot fail url={request.full_url} {e}')
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
        print('ip=', ip)
        return ip

    @staticmethod
    def download(url: str, save_path: str = '', **kwargs) -> str:
        """
         通过get形式下载文件
         :param url: 文件下载地址
         :param save_path: 本地保存地址,,默认保存在当前目录下
         :param kwargs: 如: auth=('账号', '密码')
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
                res = requests.get(url, stream=True, **kwargs)
                res.raise_for_status()  # 验证请求是否成功
                with open(save_path, "wb") as f:
                    for chunk in res.iter_content(chunk_size=1024):
                        f.write(chunk)
                CommonUtil.printLog(f'download finish,save_path={save_path}')
                return save_path
            except Exception as e:
                CommonUtil.printLog(f'download fail: {e}')
                return ''
        return ''
