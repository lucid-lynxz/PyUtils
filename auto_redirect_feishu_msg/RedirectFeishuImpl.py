# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
自动push本地指定分支代码
具体以 config.ini 文件配置信息为准
"""

import os
import re
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from util.CommonUtil import CommonUtil
from util.NetUtil import NetUtil
from util.ImgUploader import ImgUploader

from base.BaseConfig import BaseConfig
from feishu_user_monitor.FeishuMonitorByOAuth import FeishuMonitorByOAuth


class RedirectFeishuImpl(BaseConfig):
    def onRun(self):
        CommonUtil.printLog(f'RedirectFeishuImpl start...')
        NetUtil.robot_dict = self.configParser.getSectionItems('robot')  # 推送消息设置

        # 飞书设置
        feishu_setting = self.configParser.getSectionItems('feishu')
        app_id = feishu_setting['app_id']
        app_secret = feishu_setting['app_secret']
        redirect_port = int(feishu_setting['redirect_port'])
        chat_names = feishu_setting['chat_names'].split(',')

        # 原生转发到飞书的目标群
        forward_to_feishu_chat_names = self.configParser.getSectionItems('forward_to_feishu_chat_names')

        # 图床配置
        imguploader_setting = self.configParser.getSectionItems('imguploader')
        imgbb_key = imguploader_setting['imgbb_key']

        img_uploader = ImgUploader(key_dict={ImgUploader.key_imgbb: imgbb_key})

        def on_message(msg: dict, chat_name: str):
            print(f"[{chat_name}] {msg['sender_name']}: {msg['content']}")
            # msg 字段说明：
            #   msg_type    消息类型（text/post/image/...）
            #   msg_id      消息 ID
            #   create_time 时间字符串（如 2026-03-28 23:35:47）
            #   sender_id   发送者 open_id
            #   sender_name 发送者姓名
            #   sender_type 发送者类型（user/app）
            #   chat_name   群名称
            #   content     解析后的可读文本内容
            #   image_key         纯图片消息时有效
            #   image_keys        富文本内嵌图片 key 列表（post 消息时有效）
            #   downloaded_images {image_key: 绝对路径}，仅包含本次已下载成功的图片
            #                     若 download_images=False 或无图片则为空 dict
            #   raw               原始飞书消息 dict（完整字段）
            chat_name = msg['chat_name']
            sender_name = msg['sender_name']
            create_time = msg['create_time']
            msg_title = f"[{chat_name}] {sender_name} {create_time}"
            content = msg['content']
            content = f'{msg_title}\n{content}'
            msg_type = msg['msg_type']
            image_keys: dict = msg.get('image_keys')
            downloaded_images: dict = msg.get('downloaded_images')

            # print(f'msg_type={msg_type},image_keys={image_keys}')
            # print(f'downloaded_images={downloaded_images}')

            target_channels = [c.strip() for c in forward_to_feishu_chat_names.get(chat_name, '').split(',') if c.strip()]
            if target_channels:
                feishuMonitorByOAuth.forward_messages(msg, target_channels, native_forward=True)

            markdown = False
            if msg_type != 'text':  # 富文本消息
                # 遍历富文本内嵌图片, 上传并替换图片链接
                for image_key in image_keys:
                    if downloaded_images:
                        img_path = downloaded_images.get(image_key)
                        img_url = img_uploader.upload_local_img(img_path)
                        if img_url:
                            pic_flag = f' ![{image_key}]({img_url}) '
                            content = content.replace(f"[图片:{image_key}]", pic_flag).replace(f"[图片] image_key={image_key}", pic_flag)
                            content = content.replace('\n', '</br>')
                            markdown = True
                    else:
                        break
            NetUtil.push_to_robot(content, with_time=False, markdown=markdown)

        feishuMonitorByOAuth = FeishuMonitorByOAuth(app_id, app_secret, redirect_port)
        feishuMonitorByOAuth.start(chat_names, download_images=True, callback=on_message, auto_save_resume=True)
