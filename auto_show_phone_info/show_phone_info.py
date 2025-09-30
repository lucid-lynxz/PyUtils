# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
将设备信息绘制在图片上,并在手机上显示, 需要安装pillow
具体以 config.ini 文件配置信息为准
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from base.BaseConfig import BaseConfig
from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil
from util.AdbUtil import AdbUtil
from util.NetUtil import NetUtil
from util.TimeUtil import TimeUtil
from util.ImageUtil import ImageUtil


class ShowPhoneInfoImpl(BaseConfig):

    def onRun(self):
        # 创建图片缓存目录
        self._cache_path = FileUtil.create_cache_dir(None, __file__, clear=True)
        NetUtil.robot_dict = self.configParser.getSectionItems('robot')
        cmd_after_show_dict: dict = self.configParser.getSectionItems('cmd_after_show')

        cmd_after_show_list: list = []
        for k, v in cmd_after_show_dict.items():
            if CommonUtil.isNoneOrBlank(v):
                cmd_after_show_list.append(f'k')
            else:
                cmd_after_show_list.append(f'k={v}')

        setting = self.configParser.getSectionItems('setting')

        extra_tip: str = setting.get('extra_tip', '')
        if CommonUtil.isNoneOrBlank(extra_tip):
            extra_tip = TimeUtil.getTimeStr()

        font_size: int = CommonUtil.convertStr2Int(setting['font_size'], 70)
        properties = setting.get('properties', 'serial,ip')
        if CommonUtil.isNoneOrBlank(properties):
            properties = 'serial,ip'
        properties = properties.split(',')

        if CommonUtil.isNoneOrBlank(setting['devices']):  # 若未配置设备序列号,则自动获取所有在线设备
            device_id_list = AdbUtil().getAllDeviceId(onlineOnly=True)[0]
        else:
            device_id_list = setting['devices'].split(',')

        NetUtil.push_to_robot(f'自动显示设备信息脚本开始执行,设备号:{device_id_list}\nproperties={properties}')

        for deviceId in device_id_list:
            adbUtil = AdbUtil(defaultDeviceId=deviceId)
            img_path = self.generate_image(deviceId, extra_tip, properties, adbUtil, font_size, setting.get('bg_color', 'white'))
            name, _, _ = FileUtil.getFileName(img_path)
            dst_path = f'/sdcard/{name}'
            adbUtil.deleteFromPhone(dst_path, deviceId)
            result = adbUtil.push(img_path, dst_path)
            if not result:
                NetUtil.push_to_robot(f'设备 {deviceId} 推送图片失败,取消该设备后续操作')
                continue

            # adbUtil.exeShellCmds([f'am start -a android.intent.action.VIEW -d file:///sdcard/{name}'], deviceId, printCmdInfo=True)
            adbUtil.exeShellCmds([
                'am force-stop com.android.gallery3d',
                'am force-stop com.sec.android.gallery3d ',
                'am force-stop com.google.android.apps.photos',
                f'am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file://{dst_path}"',
                f'am start -a android.intent.action.VIEW -d "file://{dst_path}" -t "image/*"'
            ], deviceId, printCmdInfo=True)

            if not CommonUtil.isNoneOrBlank(cmd_after_show_list):
                for cmd in cmd_after_show_list:
                    adbUtil.exeShellCmds([cmd])

        NetUtil.push_to_robot(f'自动显示设备信息脚本执行结束')

    def generate_image(self, serial: str,
                       extra_tip: str,
                       properties: list,
                       adbUtil: AdbUtil,
                       font_size: int = 70,
                       bg_color: str = 'white'):
        """
        生成图片
        :param serial: 序列号
        :param extra_tip: 要额外显示的信息, 当前已默认显示了: 序列号 和 设备ip
        :param font_size: 字体大小,默认70
        :param bg_color: 背景颜色,默认white
        """
        dev_info_dict: dict = adbUtil.getDeviceInfo(serial, hasRoot=True)
        w = dev_info_dict.get('width', '')
        h = dev_info_dict.get('height', '')

        # 图片大小
        width = CommonUtil.convertStr2Int(w, 400)
        height = CommonUtil.convertStr2Int(h, 800)

        # 文字内容
        msg_arr = []
        for key in properties:
            msg_arr.append(f'{key}: {dev_info_dict.get(key, "")}')

        if not CommonUtil.isNoneOrBlank(extra_tip):
            msg_arr.append(extra_tip)

        msg = '\n'.join(msg_arr)

        image_path = os.path.join(self._cache_path, f'{serial}.png')  # 保存路径

        # 绘制文本信息
        (ImageUtil()
         .new((width, height), bg_color)
         .draw_text(msg, (width // 2, height // 2), align='center', vertical_align='center', font_size=font_size)
         .save(image_path))

        CommonUtil.printLog(f"✅ 已生成图片: {image_path}")
        return image_path
