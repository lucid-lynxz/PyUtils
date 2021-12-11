# !/usr/bin/env python3
# -*- coding:utf-8 -*-
import json
import urllib.request as urllib2


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
    headers = {"Content-type": "application/json"}
    json_data_obj = {
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
    print('data_obj', json_data_obj)
    # 将str类型转换为bytes类型
    json_data_obj = json.dumps(json_data_obj).encode('utf-8')
    # json_data_obj = urllib.parse.urlencode(json_data_obj).encode("utf-8")
    request = urllib2.Request(url='https://oapi.dingtalk.com/robot/send?access_token=%s' % access_token,
                              data=json_data_obj,
                              headers=headers, method="POST")
    response = urllib2.urlopen(request)
    ddResult = response.read().decode('utf-8')
    print(ddResult)
    return ddResult
