# !/usr/bin/env python3
# -*- coding:utf-8 -*-

import os

from util.TimeUtil import TimeUtil


class CommonUtil(object):
    # @classmethod
    # def convertStringEncode(cls, srcStr, srcEncode: str = "utf-8", toEncode=sys.stdout.encoding):
    #     """
    #     将字符串转为另一种编码,默认从 utf-8 转为默认控制台的编码,避免中文乱码等问题
    #     :param srcStr:  要进行编码转换的字符串
    #     :param srcEncode:  原始编码
    #     :param toEncode:  目标编码
    #     :return:
    #     """
    #     return srcStr.decode(srcEncode).encode(toEncode)

    @classmethod
    def exeCmd(cls, cmd: str, printCmdInfo: bool = True) -> str:
        """
        执行shell命令, 可得到返回值
        :param cmd: 待执行的命令
        :param printCmdInfo: 是否打印命令内容
        """
        if printCmdInfo:
            print("%s execute cmd: %s" % (TimeUtil.getTimeStr(), cmd))
        # readlines = os.popen(cmd).readlines()
        # result = "".join(readlines)
        # print("result=%s" % result)
        # return result

        with os.popen(cmd) as fp:
            bf = fp._stream.buffer.read()
        try:
            return bf.decode('utf8', 'ignore').strip()
        except UnicodeDecodeError:
            return bf.decode('gbk', 'ignore').strip()

    @classmethod
    def exeCmdByOSSystem(cls, cmd: str, printCmdInfo: bool = True):
        """
        通过os.system(xxx) 执行命令, 吴返回信息
        """
        if printCmdInfo:
            print("execute cmd by os.system: %s" % cmd)
        os.system(cmd)

    @classmethod
    def isNoneOrBlank(cls, info: str) -> bool:
        """
        判断所给字符串是否为None或者空(都是空白字符),若是则返回True
        :param info: 待判定的字符串
        :return:
        """
        if info is None or len(info.strip()) == 0:
            return True
        else:
            return False


if __name__ == "__main__":
    result = CommonUtil.exeCmd('git --git-dir=D:/D/987/.git/ --work-tree=D:\D\987 log -1')
    print("===> %s" % result)
