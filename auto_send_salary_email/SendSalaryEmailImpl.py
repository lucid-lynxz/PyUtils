# !/usr/bin/env python
# -*- coding:utf-8 -*-
"""
工资单汇总表拆分,每个人的工资信息加上固定标题行
"""
import os
import sys
import time

from openpyxl.worksheet import cell_range, pagebreak

# 将整个根目录加入到path环境变量中,并且是第一个,以便脚本导包时柯使用绝对路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from util.FileUtil import FileUtil
from util.ConfigUtil import NewConfigParser
from util.TimeUtil import TimeUtil
from util.CommonUtil import CommonUtil
from util.XLUtil import XLUtil
from util.MailUtil import MailUtil
from base.BaseConfig import BaseConfig


class EmployeeSalaryInfo(object):
    """
    员工工资截图信息对象
    """

    def __init__(self, imagePath: str, name: str = None, email: str = None):
        """
        员工信息
        :param imagePath: 截图文件路径, 文件名称格式为: 姓名_邮箱地址.png
        :param name: 员工姓名, 若为空, 则通过截图文件名截取,如: 张三
        :param email: 员工邮箱地址, 若为空,则通过截图文件名截取, 如: 123456@qq.com
        """
        self.imagePath: str = imagePath  # 工资截图地址
        fullName, fileNameOly, ext = FileUtil.getFileName(imagePath)
        self.imageName: str = fullName  # 图片名称,带后缀, 如: 张三_123456@qq.com.png

        arr = fileNameOly.split('_')
        _name: str = arr[0]
        _email: str = '_'.join(arr[1:])
        self.name: str = _name if CommonUtil.isNoneOrBlank(name) else name
        self.email: str = _email if CommonUtil.isNoneOrBlank(email) else email


class SendSalaryEmailImpl(BaseConfig):
    """
    自动拆分工资条,截图,发送邮件实现类
    """

    def onRun(self):
        # 1. 确定工资单总表excel文件路径
        configSection = self.configParser.getSectionItems('config')
        salaryPath: str = FileUtil.recookPath(configSection['salaryPath'])
        CommonUtil.printLog(f"当前config.ini中指定的salaryPath={FileUtil.absPath(salaryPath)}")

        while not FileUtil.isFileExist(salaryPath):
            salaryPath = CommonUtil.get_input_info("salaryPath不存在,请输入工资表excel文件路径:", "")

        sheetName: str = configSection['sheetName']
        xlPath: str = salaryPath  # 目标excel文件路径

        if FileUtil.isDirFile(salaryPath):
            # 1.1 提取目录下的所有excel文件
            subExcelList: list = FileUtil.get_sub_file_names(salaryPath, ['.xlsx'])
            excelCnt = len(subExcelList)

            # 1.2 若目录下没有excel文件,则提示用户输入
            # 若目录下有多个excel文件,则提示用户选择其中一个
            needInput: bool = False
            if excelCnt > 1:
                CommonUtil.printLog("存在多个excel文件: ")
                for index, name in enumerate(subExcelList):
                    CommonUtil.printLog("\t%d\t%s" % (index, name))
                excelIndex = int(CommonUtil.get_input_info("请选择序号(默认:0): ", "0"))
                xlPath = f"{salaryPath}/{subExcelList[excelIndex]}"
            elif excelCnt == 1:
                CommonUtil.printLog(f"指定目录下只有一个excel文件: {subExcelList[0]}")
                if "yes" == CommonUtil.get_input_info("是否使用该文件 yes/no (默认:yes): ", "yes"):
                    xlPath = f"{salaryPath}/{subExcelList[0]}"
                else:
                    needInput = True
            else:
                needInput = True

            if needInput:
                xlPath = input("请输入excel文件路径: ").strip()

            # 判断文件是否存在
            if not FileUtil.isFileExist(xlPath):
                CommonUtil.printLog(f"excel文件不存在, 请检查 {xlPath}")
                exit(1)

        # 2. 确定工资单sheet名称
        _xlutil = XLUtil(xlPath)
        allSheetNames = _xlutil.getAllSheetNames()

        needInput = False
        sheetTitle = sheetName
        CommonUtil.printLog("其sheet名列表为: ", includeTime=False)
        nameIndexList = list(enumerate(allSheetNames))
        for index, name in nameIndexList:
            CommonUtil.printLog("\t%d\t%s" % (index, name), includeTime=False)

        if sheetName in allSheetNames:
            needInput = "no" == CommonUtil.get_input_info(f"是否使用'{sheetName}', yes/no (默认:yes):  ", "yes")
        else:
            needInput = True

        if needInput:
            sheetTitleIndex = int(CommonUtil.get_input_info("请输入要切分的工作表名序号(默认:0): ", "0"))
            sheetTitle = nameIndexList[sheetTitleIndex][1]
        CommonUtil.printLog("工资汇总表名为: %s" % sheetTitle)

        # todo 提示用户是否要查看/修改配置(支持超时自动跳过)

        # 3. 进行工资条拆分并自动截图(仅windows支持)
        headerRangeStr: str = configSection['headerRangeStr']  # 标题区域范围,默认: A3:X4
        firstColIndex, firstRowIndex = XLUtil.getColRowIndex(headerRangeStr)  # 第一列序号, 第一行序号
        colCnt, rowCnt = XLUtil.getRangeWH(headerRangeStr)  # 标题栏宽高

        firstColLetter = _xlutil.colNum2Str(firstColIndex)  # 首列字母
        maxRowNum = _xlutil.getMaxRowNumOfColumn(firstColLetter, sheetTitle)  # 首列有数据的最大行号
        CommonUtil.printLog('  计算得到首列的最大行号为: %s' % maxRowNum)

        sumRowCnt: int = int(configSection['sumRowCnt'])  # 最后的'小计'行数,默认:1, 这几行不计入个人工资内容区域
        contentRangeSug = "%s%s:%s%s" % (  # 内容范围区域
            XLUtil.colNum2Str(firstColIndex), firstRowIndex + rowCnt,
            XLUtil.colNum2Str(firstColIndex + colCnt - 1), maxRowNum - sumRowCnt)
        totalSalaryContentRangeStr: str = contentRangeSug  # 工资内容区域范围
        CommonUtil.printLog('  计算得到总表工资内容区域为: %s' % totalSalaryContentRangeStr)

        eachSalaryContentRowCnt: int = int(configSection['eachSalaryContentRowCnt'])  # 个人工资内容行数,默认: 1
        eachGap: int = int(configSection['eachGap'])  # 工人工资信息之间的间隔行数,默认: 0
        addRowPageBreak: bool = configSection['addRowPageBreak'].lower() == 'yes'  # 是否为每人的工资条增加依次分页符,yes/no,默认: yes
        autoTakeShot: bool = configSection['autoTakeShot'].lower() == 'yes'  # 是否自动截图工资条信息,yes/no, 默认: yes
        autoSendMail: bool = configSection['autoSendMail'].lower() == 'yes'  # 截图后是否自动发送工资条信息到对方邮箱中,yes/no, 默认: yes
        emailColLetter: str = configSection['emailColLetter']  # 邮箱信息所在列号, 默认: Y
        nameColLetter: str = configSection['nameColLetter']  # 姓名所在列号, 默认: B
        CommonUtil.printLog("参数配置完成,即将开始拆分,请稍后...\n\n")

        dstSheetTitle, imgMap, imgDirPath = self.split(_xlutil, sheetTitle, headerRangeStr,
                                                       totalSalaryContentRangeStr, None,
                                                       eachSalaryContentRowCnt, eachGap,
                                                       addRowPageBreak,
                                                       autoTakeShot=autoTakeShot,
                                                       emailColLetter=emailColLetter,
                                                       nameColLetter=nameColLetter)
        CommonUtil.printLog("拆分完成,请查看结果工作表: %s" % dstSheetTitle)
        time.sleep(1)
        _xlutil.close()

        # 4. 截图后进行邮件发送
        if autoTakeShot:
            # CommonUtil.printLog("完成截图%s张, %s" % (len(imgMap), imgMap))
            if autoSendMail:
                CommonUtil.printLog('\n截图完成, 准备发送邮件...')
                SendSalaryEmailImpl.sendEmailByImage(imgDirPath, self.configPath)

    def split(self, util: XLUtil, sheetTile: str, headerRangeStr: str, totalSalaryContentRangeStr: str,
              dstSheetTitle: str = None, eachSalaryContentRowCnt: int = 1, eachGap: int = 0,
              addRowPageBreak: bool = True, copyWithFormat: bool = True, autoTakeShot: bool = False,
              emailColLetter: str = None, nameColLetter: str = None) -> tuple:
        """
        拆分工资汇总表为每个人独立一个工资条(固定的标题栏+个人工资信息+gap空白分隔行)
        :param util: excel工具类, 如: XLUTIL("D:/salary.xlsx")
        :param sheetTile: 工资表名, 如: "sheet1"
        :param headerRangeStr:工资条固定标题栏区域,如: "A1:Z2"
        :param totalSalaryContentRangeStr: 员工工资表信息内容区域范围(剔除标题栏区域), 如 "A3:Z50"
        :param dstSheetTitle: 要复制到的目标表名, 默认为None,表示excel新建表格时自动命名
        :param eachSalaryContentRowCnt: 每个人的工资信息行数,默认1行
        :param eachGap: 个人工资标题栏和工资信息复制后, 空白行数,用于间隔,默认0
        :param addRowPageBreak:每复制一个工资条,增加一个打印分页符
        :param copyWithFormat:是否带格式复制,默认是
        :param autoTakeShot: 是否自动截图每个人的工资条信息
        :param emailColLetter: 邮箱信息所在列号
        :param nameColLetter: 名字信息所在列号
        :return: tuple(str,map,str):  最终的工作表名, map(截图名称, 截图路径), 截图所在目录路径
                其中截图名称格式: {姓名}_{邮箱}
        """
        # 创建截图缓存目录, 位于与excel源文件同目录下得 imgCache
        xlDirPath = os.path.dirname(util.filePath)
        _, xlFileName, _ = FileUtil.getFileName(util.filePath)
        # imgDirPath = "%s/imgCache/%s/" % (xlDirPath, TimeUtil.getTimeStr(format='%Y%m%d_%H%M%S'))
        imgDirPath = f"{xlDirPath}/imgCache/{xlFileName}/"
        imgMap = {}  # 工资条信息 key-姓名+邮箱地址 value-图片路径

        continueMode: bool = "true" == self.configParser.getSectionItems('config')["continueMode"].lower()
        if autoTakeShot or not FileUtil.isFileExist(imgDirPath):
            FileUtil.createFile(imgDirPath, not continueMode)  # continueMode下不重建目录
            if not FileUtil.isFileExist(imgDirPath):
                CommonUtil.printLog('截图缓存目录创建失败, 请手动创建后重试 %s' % imgDirPath)

        dstSheet = util.addSheet(dstSheetTitle, False)
        dstSheetTitle = dstSheet.title
        headWidth, headHeight = XLUtil.getRangeWH(headerRangeStr)

        srcCr = cell_range.CellRange(range_string=totalSalaryContentRangeStr)
        totalRow = srcCr.max_row - srcCr.min_row + 1  # 总行数
        infoCnt = int(totalRow / eachSalaryContentRowCnt)  # 总信息条数
        copyInfoCnt = 0  # 已复制的信息条数
        copyRowCnt = 0  # 已复制的总行数
        takeScreenShotFailCnt = 0  # 截图失败的数量
        for rowIndex in range(srcCr.min_row, srcCr.max_row + 1, eachSalaryContentRowCnt):
            copyInfoCnt += 1
            # 添加分页符
            if addRowPageBreak:
                dstSheet.row_breaks.append(pagebreak.Break(id=copyRowCnt))

            # 复制标题栏
            CommonUtil.printLog("%s 正在复制第 %s/%s 条信息" % (TimeUtil.getTimeStr(), copyInfoCnt, infoCnt))
            startRowIndex = copyRowCnt + 1
            startCell = "A%s" % startRowIndex  # 起始单元格, 都从A列开始

            util.copyValue(sheetTile, headerRangeStr, dstSheetTitle, startCell, dataOnly=True, autoSave=False)
            copyRowCnt += headHeight

            # 复制个人工资条信息
            ltContentAddress = XLUtil.colRowNum2Str(srcCr.min_col, rowIndex)
            brContentAddress = XLUtil.colRowNum2Str(srcCr.max_col, rowIndex + eachSalaryContentRowCnt - 1)
            contentRange = "%s:%s" % (ltContentAddress, brContentAddress)
            util.copyValue(sheetTile, contentRange, dstSheetTitle, "A%s" % (copyRowCnt + 1),
                           dataOnly=True, autoSave=True)
            copyRowCnt += eachSalaryContentRowCnt

            # 截图以便发送邮件
            if autoTakeShot:
                # 获取姓名和邮箱地址
                name = util.getCellValue(sheetTile, "%s%s" % (nameColLetter, rowIndex))
                email = util.getCellValue(sheetTile, "%s%s" % (emailColLetter, rowIndex))
                if CommonUtil.isNoneOrBlank(name):
                    CommonUtil.printLog(" %s%s 姓名为空,取消其工资条截图,请注意复查" % (nameColLetter, rowIndex))
                    takeScreenShotFailCnt += 1
                elif CommonUtil.isNoneOrBlank(email):
                    CommonUtil.printLog(
                        ' %s%s 员工 %s 并未提供邮箱地址, 取消其工资条截图' % (emailColLetter, rowIndex, name))
                    takeScreenShotFailCnt += 1
                else:
                    name = name.strip()
                    email = email.strip()
                    # CommonUtil.printLog("正在截图 name=%s,email=%s" % (name, email))
                    # 个人工资条区域,包含标题栏和内容
                    endCell = "%s%s" % (XLUtil.colNum2Str(headWidth), copyRowCnt)
                    finalRange = "%s:%s" % (startCell, endCell)

                    # 截图
                    imgName = "%s_%s" % (name, email)
                    CommonUtil.printLog(f"正在截图 {finalRange}, {imgName}")
                    imgPath = FileUtil.recookPath(f"{imgDirPath}/{imgName}.png")
                    success, path = XLUtil.takeShot(util.filePath, dstSheetTitle, finalRange, imgPath,
                                                    continueMode=continueMode)
                    if not success:
                        CommonUtil.printLog("%s 的工资条截图失败, 请手动截图 " % name)
                        takeScreenShotFailCnt += 1
                    else:
                        # CommonUtil.printLog("截图成功,图片地址:%s" % path)
                        imgMap[imgName] = path
            copyRowCnt += eachGap
        dstTotalRangStr = 'A1:%s%s' % (XLUtil.colNum2Str(headWidth), copyRowCnt)
        dstSheet.print_area = dstTotalRangStr  # 打印区域
        dstSheet.page_setup.scale = 50
        # CommonUtil.printLog("打印区域是: %s" % dstSheet.print_area)
        util.save()

        CommonUtil.printLog(
            "截图结果共 %s 张, 失败 %s 张, 存储路径为:%s" % (len(imgMap), takeScreenShotFailCnt, imgDirPath))
        return dstSheetTitle, imgMap, imgDirPath

    @staticmethod
    def sendEmailByImage(imageDirPath: str, emailConfigIniPath: str, durationSec: int = -1):
        """
        根据工资截图信息, 批量发送邮件
        :param imageDirPath: 截图所在目录绝对路径, 要去目录中存在工资截图, 文件名格式: 姓名_邮箱.png , 如: 张三_123456@qq.com
        :param durationSec: 邮件发送间隔, 单位:秒, 正数有效, 若传其他值, 则会从 config.ini 中读取配置
        :param emailConfigIniPath: 发件人邮箱信息配置参数, 要求内部包含字段如下:
            [config]
            # 邮箱服务器, 默认使用qq邮箱
            smtpServer = smtp.qq.com

            # 服务器端口号
            smtpPort = 587

            # 发件人邮箱
            senderEmail = 4***06@qq.com

            # 邮箱密码或者授权码
            senderPwd = dflg***mdhcagc
        """
        CommonUtil.printLog(
            '批量发送工资截图到邮箱工具,连续发送间隔时长durationSec=%s, imageDirPath=%s' % (durationSec, imageDirPath))
        # 根据截图信息提取员工信息列表
        employeeList = list()  # 元素类型为: EmployeeSalaryInfo
        if not FileUtil.isDirFile(imageDirPath):
            CommonUtil.printLog('您输入的不是目录路径, 请重新输入目录路径')
            return

        imageList = FileUtil.listAllFilePath(imageDirPath)
        if len(FileUtil.listAllFilePath(imageDirPath)) == 0:
            CommonUtil.printLog('该路径下并无文件, 请重新输入目录路径')
            return

        # 提取路径下的截图信息
        for imagePath in imageList:
            _, name, ext = FileUtil.getFileName(imagePath)
            if ext.lower() == 'png':
                employeeList.append(EmployeeSalaryInfo(imagePath))

        if len(employeeList) <= 0:
            CommonUtil.printLog('该路径下并无png截图, 请重新输入目录路径')
            return

        # 发送成功的记录,每行一条记录, 格式:  xxxx 姓名 邮箱地址
        sendMailSuccessLog = '%s/send_mail_success_history.txt' % imageDirPath
        skipNameMailList = []  # 发送成功的邮件无需再次发送, 格式: 姓名_邮箱地址
        if FileUtil.isFileExist(sendMailSuccessLog):
            lines = FileUtil.readFile(sendMailSuccessLog)
            for line in lines:
                arr = line.strip().split(' ')
                if len(arr) < 3:
                    CommonUtil.printLog('sendMailSuccessLog invalid: %s' % line)
                    continue
                skipNameMailList.append('%s_%s' % (arr[1].strip(), arr[2].strip()))
        CommonUtil.printLog('已发送成功,无需再次发送的邮件列表如下:\n\t%s' % '\n\t'.join(skipNameMailList))
        continueRun: bool = CommonUtil.get_input_info(
            "以上是已发送成功过的邮件 %s 条(无需再次发送), 否继续执行, yes/no (默认:yes): " % len(skipNameMailList),
            "yes").lower() == "yes"
        if not continueRun:
            CommonUtil.printLog('退出程序')
            exit(1)

        CommonUtil.printLog('目录下的图片如下:')
        for item in employeeList:
            CommonUtil.printLog('\t%s' % item.imageName)

        imageSize = len(employeeList)
        successCount = 0
        isImageSizeValid: bool = CommonUtil.get_input_info(f"\n共{imageSize} 张图片, 是否正确, yes/no (默认:yes): ",
                                                           "yes").lower() == "yes"
        if isImageSizeValid:
            sendEmailNow: bool = CommonUtil.get_input_info("\n是否开始发送邮件, yes/no (默认:yes): ",
                                                           "yes").lower() == "yes"
            # 显示属性修改提示
            # 默认使用当前目录下的 config.ini 文件路径
            # curDirPath = os.path.abspath(os.path.dirname(__file__))
            # configPath = '%s/config.ini' % curDirPath

            configParser = NewConfigParser().initPath(emailConfigIniPath)
            mailConfig = configParser.getSectionItems('mail')
            if sendEmailNow:
                CommonUtil.printLog('\n准备发送邮件...')
                smtpServer = mailConfig['smtpServer']
                smtpPort = int(mailConfig['smtpPort'])
                senderEmail = mailConfig['senderEmail']
                senderPwd = mailConfig['senderPwd']
                subject = mailConfig['subject']

                if durationSec <= 0:
                    durationSec = int(mailConfig['delaySec'])

                mailUtil: MailUtil = None
                try:
                    for employeeInfo in employeeList:
                        # qq要求使用邮件授权码, 依次传入发件人邮箱, 密码, 发送服务器地址, 服务器端口
                        mailUtil = MailUtil(senderEmail, senderPwd, smtpServer, smtpPort, debugLevel=0)

                        path = employeeInfo.imagePath
                        name, email = employeeInfo.name, employeeInfo.email
                        curNameEmail = '%s_%s' % (name, email)
                        if curNameEmail in skipNameMailList:
                            CommonUtil.printLog('%s 已发送过邮件,无需重复发送,跳过' % curNameEmail)
                            continue

                        # 正文中插入图片, 测试后,该文件不会再显示再附件中(qq邮箱)
                        # 1. 添加图片附件
                        mailUtil.obtainMailMsg(True)  # 每个人新建一个消息
                        cid = mailUtil.addAttachFile(path, "image")

                        # 2. 插入image标签
                        mailUtil.setMailMsg('<html><body>'
                                            + '<h2> %s,你好:</h2>' % name
                                            + '<p>这是您本月工资条,请查收</p>'
                                            + '<p><img src="cid:%s"></p>' % cid
                                            + '</body></html>',
                                            subject=f"{subject}-{name}")

                        # 添加普通文件附件
                        # mailUtil.addAttachFile("/Users/***/Desktop/test.py", "file")
                        # 发送到指定邮箱
                        CommonUtil.printLog("正在发送邮件给 %s %s" % (name, email))
                        if name is not None and len(name) > 0 and email is not None and '@' in email:
                            sendSuccess = mailUtil.sendTo([email])
                            if sendSuccess:
                                successCount += 1
                                FileUtil.append2File(sendMailSuccessLog, "成功发送邮件给 %s %s" % (name, email))
                            else:
                                CommonUtil.printLog('\n-->邮件发送失败,注意检查')

                        mailUtil.quit()
                        mailUtil = None
                        if durationSec > 0:
                            time.sleep(durationSec)

                except Exception as e:
                    CommonUtil.printLog('\n邮件发送出现异常, 退出发送, 请排查 %s' % e)
                finally:
                    if mailUtil is not None:
                        mailUtil.quit()
            CommonUtil.printLog('发送成功邮件: %s ,共需要发送: %s' % (successCount, imageSize))
