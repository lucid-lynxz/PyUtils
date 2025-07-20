# !/usr/bin/env python3
# -*- coding:utf-8 -*-

from PIL import ImageGrab
from util.FileUtil import FileUtil
from util.CommonUtil import CommonUtil
from util.TimeUtil import TimeUtil
from util.TimeUtil import log_time_consume


class ExcelTakeShotUtil(object):
    """
    excel截图工具类, 仅支持windows, 主要用于批量截图
    """

    @log_time_consume()
    def __init__(self, xlPath: str, sheetName: str, img_cache_dir: str = None, debug_mode: bool = False):
        """
        python excel截图， 参考： https://blog.csdn.net/weixin_30378623/article/details/96566903
        需要安装win库：
        pip install pywin32 -i https://pypi.douban.com/simple
        pip install pillow -i https://pypi.douban.com/simple
        :param xlPath: excel源文件路径
        :param sheetName: 待截图的表格名
        :param img_cache_dir: 图片缓存目录, 空时, 会自动在excel所在目录下创建: 'imgCache/{excel文件名}_{sheetName}/' 子目录, 用于截图时可只传入要保存的图片名
        :param debug_mode: 调试模式, 为True时, 会打印调试信息
        """
        # 仅系统是win时才可用
        if not CommonUtil.isWindows():
            raise Exception(f"仅支持window平台,当前是:{CommonUtil.getPlatformName()}")

        from win32com.client import DispatchEx

        self.xlPath: str = FileUtil.recookPath(xlPath)
        self.sheetName: str = sheetName
        self.debug_mode: bool = debug_mode

        # 创建图片缓存目录
        _, xlFileName, _ = FileUtil.getFileName(self.xlPath)
        if CommonUtil.isNoneOrBlank(img_cache_dir):
            img_cache_dir = FileUtil.getParentPath(self.xlPath) + f'/imgCache{xlFileName}_{sheetName}/'  # 截图缓存目录
        self.image_cache = img_cache_dir  # 截图缓存目录
        FileUtil.createFile(self.image_cache)

        self.excel = None  # excel应用层程序
        self.wb = None  # excel工作簿
        self.wx = None  # {sheetName} 工作表对象

        self.success_cnt: int = 0  # 截图成功次数
        self.fail_cnt: int = 0  # 截图失败次数

        if FileUtil.isFileExist(self.xlPath):
            self.excel = DispatchEx("Excel.Application")  # 启动excel
            self.excel.Visible = False  # 可视化
            self.excel.DisplayAlerts = False  # 是否显示警告
            self.wb = self.excel.Workbooks.Open(self.xlPath)  # 打开excel
            self.ws = self.wb.Worksheets(sheetName)  # 选择sheet
        else:
            raise Exception(f"excel文件不存在: {self.xlPath}")
        CommonUtil.printLog(f'初始化excel截图工具, 表格名:{self.sheetName}, 图片缓存目录:{self.image_cache}')

    def getCellValue(self, cellAddress: str) -> str:
        """
        获取指定单元格的内容
        """
        return self.ws.Range(cellAddress).Value

    # @log_time_consume()
    def take_shot(self, area: str, imgPath: str = None, continueMode: bool = False) -> tuple:
        """
        :param area:待截图的区域，如: "A1:X2"
        :param imgPath: 图片保存的绝对路径 或者文件名, 会保存到 self.image_cache 目录下
        :param continueMode: 若为True,则表示若图片已经存在,则不重新截图
        :return: (bool,str) 依次表示是否截图成功，以及图片的位置
        """
        imgPath = FileUtil.recookPath(imgPath)
        if '/' not in imgPath:  # 表明只传入了图片文件名
            imgPath = FileUtil.recookPath(f'{self.image_cache}/{imgPath}')

        if FileUtil.isFileExist(imgPath) and continueMode:
            CommonUtil.printLog(f"图片已经存在，无需重新截图: {imgPath}")
            self.success_cnt += 1
            return True, imgPath

        maxRetryCnt = 3  # 重试次数限制
        for retryCnt in range(maxRetryCnt):
            try:
                CommonUtil.printLog(' 正在截图区域:%s, 图片名: %s' % (
                    area, 'unknown' if imgPath is None else FileUtil.getFileName(imgPath)[0]))

                self.ws.Select()  # 选中激活某个工作表, 避免由于可能多个工作表被同时被选中，导致无法复制/粘贴单元格区域
                self.ws.Range(area).CopyPicture(Format=2)  # 复制图片区域
                # time.sleep(1)
                # # ws.Paste()  # 粘贴
                # ws.Paste(ws.Range('B1'))  # 将图片移动到具体位置
                # name = str(uuid.uuid4())  # 重命名唯一值
                # new_shape_name = name  # name[:6]
                # excel.Selection.ShapeRange.Name = new_shape_name  # 将刚刚选择的Shape重命名，避免与已有图片混淆
                # ws.Shapes(new_shape_name).Copy()  # 选择图片
                # # img = ws.pictures[len(ws.pictures) - 1]
                # # img.Copy()
                # time.sleep(1)  # 延迟下， 不然img为空
                img = ImageGrab.grabclipboard()  # 获取剪贴板的图片数据

                if img is None:
                    CommonUtil.printLog("剪贴板img为None,原始 pic=%s" % img)
                    self.fail_cnt += 1
                    return False, imgPath
                else:
                    img.save(imgPath, quality=95)  # 保存图片
                    self.success_cnt += 1
                    if self.debug_mode:
                        CommonUtil.printLog(f"截图成功,图片路径: {imgPath}")
                    return True, imgPath
            except BaseException as e:
                self.fail_cnt += 1
                CommonUtil.printLog(f"截图 {area} 发生异常,重试 {(retryCnt + 1)}/{maxRetryCnt} {e}")
        return False, imgPath

    @log_time_consume()
    def close(self):
        """
        所有图片都截图完毕后,关闭excel文件和程序
        """
        if self.wb is not None:
            self.wb.Close(SaveChanges=0)  # 关闭工作薄，不保存

        if self.excel is not None:
            self.excel.Quit()  # 退出excel

        FileUtil.deleteEmptyDirsRecursively(self.image_cache)  # 删除空白目录
        CommonUtil.printLog(f"截图完成,成功:{self.success_cnt},失败:{self.fail_cnt}")


if __name__ == '__main__':
    _xl_path = 'H:/tmp/20240718_salary/在职2025.07带邮箱.xlsx'
    _util = ExcelTakeShotUtil(_xl_path, "Sheet", debug_mode=True)
    _util.take_shot("A1:Z3", 'A1_Z3.png')
    _util.take_shot("A4:X6", 'A4_Z6.png')
    _util.take_shot("A7:X9", 'A7_Z9.png')
    _util.close()
