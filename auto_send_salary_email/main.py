# !/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
对工资单总表进行拆分和截图,并自动发送邮件给对方
由于截图依赖于pywin32库,暂时只支持windows平台
1. 对工资单总表进行拆分, 每个人一张工资条
2. 对工资条进行截图, 图片会命名为:{姓名}_{邮箱}.png
2. 根据图片名中的姓名和邮箱信息, 将图片通过邮件发送给对方

具体以 config.ini 文件配置信息为准
"""
import os
import sys

# 把项目根目录路径加入到 sys.path ,否则在shell中运行可能会提示找不到包
# 参考: https://www.cnblogs.com/hi3254014978/p/15202910.html
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

from auto_send_salary_email.SendSalaryEmailImpl import SendSalaryEmailImpl

if __name__ == "__main__":
    # 默认使用当前目录下的 config.ini 文件路径
    curDirPath = os.path.abspath(os.path.dirname(__file__))
    configPath = '%s/config.ini' % curDirPath

    # 触发更新
    SendSalaryEmailImpl(configPath, optFirst=True).run()
