# !/usr/bin/env python
# -*- coding:utf-8 -*-

import email.encoders
import os.path
import smtplib
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
from util.CommonUtil import CommonUtil


class MailUtil(object):
    """
    smtp发送邮件工具类
    参考: https://www.liaoxuefeng.com/wiki/1016959663602400/1017790702398272
    1. 通过 __init__ 方法传入发件人信息,包括发件邮件地址,密码,smtp服务器信息等
    2. 通过 composeTextMsg 方法构造简单的文本内容
    3. 发送邮件: sendTo
    4. 关闭服务器链接: quit
    """

    def __init__(self, address: str, pwd: str,
                 smtpServer: str = "smtp.qq.com",
                 smtpPort: int = 587,
                 debugLevel: int = 0):
        """
        :param address:  发件人邮件地址
        :param pwd: 密码, qq邮箱使用的授权码,文档: https://service.mail.qq.com/cgi-bin/help?subtype=1&&id=28&&no=1001256
        :param smtpServer: smtp服务器地址, qq邮箱是: smtp.qq.com,  文档:https://service.mail.qq.com/cgi-bin/help?subtype=1&&id=28&&no=167
        :param smtpPort: smtp服务器端口,qq邮箱的默认端口是 587
        :param debugLevel: 打印调试信息 1-显示所有smtp交互日志
        """
        self.fromMail = address
        # 使用 smtp() 接口可能会报错: Connection unexpectedly closed, 改为: smtp_ssl()
        # self.server = smtplib.SMTP(smtpServer, smtpPort)  # SMTP协议默认端口是25
        self.server = smtplib.SMTP_SSL(smtpServer)
        self.server.set_debuglevel(debugLevel)
        self.server.login(address, pwd)
        self.mineMsg: MIMEMultipart = MIMEMultipart()  # 邮件对象
        self.attachCnt: int = 0  # 附件个数

    @staticmethod
    def _format_addr(s: str):
        """
        格式化一个邮件地址。
        注意 MIMEText 不能简单地传入 name <addr@example.com>，因为如果包含中文，需要通过Header对象进行编码。
        :param s:
        :return:
        """
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    def obtainMailMsg(self, forceRecreate: bool = False) -> MIMEMultipart:
        """
        获取一个 MIMEMultipart 对象
        :param forceRecreate:  是否强制重建
        :return:
        """
        if forceRecreate:
            self.mineMsg = MIMEMultipart()
            self.attachCnt = 0  # 附件个数
        return self.mineMsg

    def setMailMsg(self, content: str, fromTip: str = None, subject: str = None) -> MIMEMultipart:
        """
        构造纯邮件内容
        :param content: 邮件正文,支持html格式
                若需要插入图片到正文,请先添加附件 addAttachFile 后,得到 id, 然后插入 image 标签: <img src="cid:%s"%attachId>
        :param fromTip: 发件人信息,默认使用 self.fromMail, 可自行指定,注意邮件地址需要用尖括号括起来, 如: 测试 <4456***@qq.com>
        :param subject: 邮件主题
        :return:
        """
        self.obtainMailMsg(False)
        self.mineMsg['From'] = MailUtil._format_addr(fromTip if fromTip is not None else self.fromMail)
        if subject is not None:  # 主题
            self.mineMsg['Subject'] = Header(subject, 'utf-8').encode()
        self.mineMsg.attach(MIMEText(content, 'html', 'utf-8'))  # 邮件正文是MIMEText:
        return self.mineMsg

    def addAttachFile(self, localPath: str, fileType: str = "file") -> int:
        """
        添加附件到邮件中
        :param localPath:本地文件地址
        :param fileType:文件类型,默认为文件(file,可设置为图片等其他格式,如: iamge)
        :return: 当前附件序号 Content-ID, 从0开始
        """
        fileName = os.path.basename(localPath)  # 文件名
        ext = None if "." not in fileName else os.path.splitext(fileName)[-1][1:]  # 文件扩展名

        self.obtainMailMsg(False)
        with open(localPath, 'rb') as f:
            # 设置附件的MIME和文件名
            mime = MIMEBase(fileType, ext, filename=fileName)
            # 加上必要的头信息:
            mime.add_header('Content-Disposition', 'attachment', filename=fileName)
            mime.add_header('Content-ID', '<%s>' % self.attachCnt)
            mime.add_header('X-Attachment-Id', '%s' % self.attachCnt)
            mime.set_payload(f.read())  # 把附件的内容读进来:
            email.encoders.encode_base64(mime)  # 用Base64编码:
            self.mineMsg.attach(mime)  # 添加到MIMEMultipart
        curAttachCnt = self.attachCnt
        self.attachCnt = self.attachCnt + 1
        return curAttachCnt

    def _recookMailAddresss(self, mailAddress: str) -> str:
        """
        处理邮箱地址, 删除前后空格及中间空格
        对不符合格式规范的(如不包含 @ 符号), 返回None
        :param mailAddress: 原始邮件地址
        :return: 最终邮件地址, 接收方注意要进行判空
        """
        if CommonUtil.isNoneOrBlank(mailAddress) \
                or '@' not in mailAddress \
                or mailAddress.startswith('@') \
                or mailAddress.endswith('@'):
            return ''
        return "".join(mailAddress.split())

    def sendTo(self, toMails: list, toNames: list = None) -> bool:
        """
        发送邮件给指定的收件人
        :param toMails: 收件人邮件列表
        :param toNames: 收件人名称列表 要求与 toMails 长度一致, 若为None,这使用 toMails 替代
        :return: 是否发送成功
        """
        toMails = list(map(self._recookMailAddresss, toMails))
        toNames = toMails if (toNames is None or len(toNames) == 0) else toNames

        lenMails = len(toMails)
        lenNames = len(toNames)

        # 拼接生成收件人信息
        strToList = list()
        try:
            for index in range(lenMails):
                toMail = toMails[index]
                toName = toMail if index >= lenNames else toNames[index]
                strToList.append(self._format_addr('%s <%s>' % (toName, toMail)))
        except Exception as e:
            strToList = toMails
        self.mineMsg['To'] = ','.join(strToList)  # 生成收件人信息, 转换为 str, 逗号分隔

        try:
            self.server.sendmail(self.fromMail, toMails, self.mineMsg.as_string())
            return True
        except Exception as e:
            print(' 发送邮件给 %s 失败, 错误信息: %s' % (toMails, e))
            return False

    def quit(self):
        self.server.quit()


if __name__ == "__main__":
    mailUtil = MailUtil("4456xxxx@qq.com", "dflgfbxxxxxxxxx", "smtp.qq.com", 587, debugLevel=0)  # qq要求使用邮件授权码

    # 普通文本正文
    # msg = mailUtil.setMailMsg("你好,hello from python", "我是4456 <%s>" % mailUtil.fromMail, "测试python2")

    # 正文中插入图片, 测试后,该文件不会再显示再附件中(qq邮箱)
    # 1. 添加图片附件
    cid = mailUtil.addAttachFile("/Users/Lynxz/Desktop/hello.png", "image")
    # 2. 插入image标签
    mailUtil.setMailMsg('<html><body><h1>你好,hello from python</h1>' +
                        '<p><img src="cid:%s"></p>' % cid +
                        '</body></html>', "我是4456 <%s>" % mailUtil.fromMail, "测试python 2")

    # 添加普通文件附件
    # mailUtil.addAttachFile("/Users/***/Desktop/test.py", "file")
    # 发送到指定邮箱
    senderrs = mailUtil.sendTo([" 3605xxxxx @q q.com "])
    mailUtil.quit()
