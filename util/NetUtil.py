# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import json
import socket
import traceback
import urllib.request as urllib2

from util.CommonUtil import CommonUtil
from util.DingTaskBot import DingTalkBot


class NetUtil(object):
    robot_dict: dict = dict()  # 默认的机器人配置信息, 用于发送通知,具体字段见 push_to_robot 方法

    @staticmethod
    def push_to_robot(content: str, configDict: dict = None, printLog: bool = False) -> bool:
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
        content = "%s\n%s\n%s" % (keyWord, extraInfo, content)
        content = content.strip()

        atAll = configDict.get('atAll', 'False') == 'True'

        ddAccessToken = configDict.get('accessToken', '')
        atPhone = configDict.get('atPhone', '')

        fsToken = configDict.get('feishuToken', '')

        if CommonUtil.isNoneOrBlank('%s%s' % (ddAccessToken, fsToken)):
            return False

        if not CommonUtil.isNoneOrBlank(ddAccessToken):
            NetUtil.push_ding_talk_robot(content, ddAccessToken, atAll, at_mobiles=atPhone.split(','))
        if not CommonUtil.isNoneOrBlank(fsToken):
            NetUtil.push_feishu_robot(content, fsToken, atAll)
        return True

    @staticmethod
    def push_ding_talk_robot(content: str,
                             access_token: str,
                             is_at_all: bool = False,
                             at_mobiles: list = '') -> str:
        """
        发送文本消息到钉钉机器人
        文档:  https://developers.dingtalk.com/document/robots/custom-robot-access
        :param content: 待发送的内容
        :param access_token: 机器人token,必填
        :param is_at_all: 是否@所有人
        :param at_mobiles: @指定人员,填入对应人员的手机号列表, 如: ['123', '456']
        """
        result = DingTalkBot(token=access_token).send_text(content, is_at_all, at_mobiles)
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
