# -*- coding: utf-8 -*-

import os
import time
import zipfile

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
通过7z进行目录/文件压缩/解压缩
使用:
1. 压缩指定文件: compress(src, dest)
2. 解压文件: unzip(src7zFile, dest)
"""


class CompressUtil(object):

    def __init__(self, sevenZipPath: str = None):
        """
        :param sevenZipPath: 7z.exe 可自行执行路径
        """
        # 由于在windows下,软件经常装在 C:/Program Files/ 目录下, 目录名带有空格可能导致执行命令出错,因此包装一层
        self.sevenZipPath = '\"%s\"' % CommonUtil.checkThirdToolPath(FileUtil.recookPath(sevenZipPath), "7z")

    def compress(self, src: str, dst: str = None, pwd: str = None,
                 excludeDirName: str = None, sizeLimit: str = None,
                 printCmdInfo: bool = True) -> str:
        """
        压缩指定文件成zip
        :param pwd: 密码
        :param src: 待压缩的目录/文件路径
        :param dst: 生成的压缩文件路径,包括目录路径和文件名,若为空,则默认生成在源文件所在目录
                            会自动提取文件名后缀作为压缩格式,若为空,则使用默认 .zip 格式压缩
                            支持的后缀主要包括:  .7z .zip .gzip .bzip2 .tar 等
        :param excludeDirName: 不进行压缩的子目录/文件名信息, 支持通配符,支持多个,使用逗号分隔
        :param sizeLimit: 压缩包大小限制, 支持的单位: b/k/m/g, 如: 100m 表示压缩后单文件最大100M
        :param printCmdInfo:执行命令时是否打印命令内容
        :return: 最终压缩文件路径, 若压缩失败,则返回 ""
        """
        if CommonUtil.isNoneOrBlank(src):  # 参数异常:源文件路径
            CommonUtil.printLog("Compression failed: Parameter exception, please confirm the source file path is correct")
            return ""

        if not os.path.exists(src):  # 源文件不存在
            CommonUtil.printLog("Compression failed: Source file does not exist, please check and try again")
            return ""

        if CommonUtil.isNoneOrBlank(dst):
            if src.endswith('/') or src.endswith('\\'):
                dst = '%s.zip' % src[:-1]
            else:
                dst = '%s.zip' % src

        _, _, ext = FileUtil.getFileName(dst)
        pCmd = ""
        if pwd is not None and len(pwd) > 0:
            pCmd = "-p%s -mhe" % pwd

        # 需要剔除子文件
        excludeCmd = ""
        if excludeDirName is not None and len(excludeDirName) > 0:
            arr = excludeDirName.split(',')
            if CommonUtil.isWindows():
                excludeCmd = ' -xr^!'.join(arr)
                excludeCmd = ' -xr^!%s' % excludeCmd
            else:
                for item in arr:
                    excludeCmd = '%s \'-xr!%s\'' % (excludeCmd, item)

        # 分包压缩大小
        sizeLimitCmd = ''
        if sizeLimit is not None and len(sizeLimit) > 0:
            sizeLimitCmd = '-v%s' % sizeLimit

        # 原路径和压缩包路径增加双引号,兼容路径中带空格的情形
        cmd = "%s a -t%s -r \"%s\" %s \"%s\" %s %s" % (self.sevenZipPath, ext, dst, pCmd, src, excludeCmd, sizeLimitCmd)
        CommonUtil.exeCmd(cmd, printCmdInfo=printCmdInfo)
        return dst

    def unzip(self, src7zFile: str, dest: str = None, pwd: str = None, printCmdInfo: bool = False) -> tuple:
        """
        解压缩指定7z文件
        :param pwd: 密码
        :param src7zFile: 要解压的7z文件
        :param dest: 解压目录路径, 若为空,则解压到源压缩文件同级目录下
        :param printCmdInfo:是否打印日志
        :return: (bool,str) 前者表示是否解压成功, 后者表示解压目录路径,若失败,则返回 None
        """
        if not os.path.exists(src7zFile):  # 压缩文件不存在
            CommonUtil.printLog(f"Compressed file does not exist, please check and try again: {src7zFile}")
            return False, dest

        src7zFile = src7zFile.replace("\\", "/")
        if CommonUtil.isNoneOrBlank(dest):
            _, srcFileName, _ = FileUtil.getFileName(src7zFile)
            dest = os.path.join(os.path.dirname(src7zFile), srcFileName)

        if os.path.exists(dest):
            localtime = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            dest = "%s_%s" % (dest, localtime)

        dest = dest.replace("\\", "/")
        FileUtil.makeDir(dest)

        pCmd = ""
        if not CommonUtil.isNoneOrBlank(pwd):
            pCmd = "-p%s" % pwd
        # 注意 -o 与后面的解压目录之间不要有空格
        result = CommonUtil.exeCmd(
            "echo %s | %s x %s -y -aos -o%s %s" % (pCmd, self.sevenZipPath, src7zFile, dest, pCmd), printCmdInfo)
        CommonUtil.printLog('result=%s' % result)
        success = "Can't open as archive" not in result and 'Archives with Errors: ' not in result
        return success, dest

    @staticmethod
    def read_zip_file_content(zip_path: str, target_file_path: str, charset: str = 'utf-8',
                              pwd: str = None, mode: str = 'lines') -> any:
        """
        读取 ZIP 压缩包中指定文件的内容（无需解压到磁盘）
        
        :param zip_path: ZIP 文件的路径
        :param target_file_path: 要读取的文件在 ZIP 中的路径，如 'assets/myRes/abc.txt'
        :param charset: 文本文件的字符编码（仅 text/lines 模式有效）
        :param pwd: 密码（如果压缩包有密码保护）
        :param mode: 读取模式
                    - 'lines': 按行返回列表（默认），每行已去除末尾换行符
                    - 'text': 返回完整文本字符串
                    - 'bytes': 返回原始字节数据（适合二进制文件）
        :return: 根据 mode 返回不同格式
                - 'lines' → list[str]
                - 'text' → str
                - 'bytes' → bytes
                - 失败返回 None
        
        :example:
        # 示例 1: 按行读取配置文件
        lines = read_zip_file_content('config.zip', 'config.ini', mode='lines')
        for line in lines:
        ...     print(line)
        
        # 示例 2: 读取完整 JSON 内容
        json_str = read_zip_file_content('data.zip', 'data.json', mode='text')
        import json
        data = json.loads(json_str)
        
        # 示例 3: 读取二进制文件（如图片）
        img_bytes = read_zip_file_content('images.zip', 'photo.jpg', mode='bytes')
        with open('output.jpg', 'wb') as f:
        ...     f.write(img_bytes)
        
        # 示例 4: 读取加密压缩包
        content = read_zip_file_content('secret.zip', 'info.txt', pwd='123456')
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 设置密码（如果有）
                if pwd is not None:
                    try:
                        zip_ref.setpassword(pwd.encode('utf-8'))
                    except Exception as e:
                        CommonUtil.printLog(f"❌ 密码设置失败：{e}")
                        return None

                # 快速检查文件是否存在（使用 getinfo 比 namelist 更快）
                try:
                    file_info = zip_ref.getinfo(target_file_path)
                except KeyError:
                    CommonUtil.printLog(f"⚠️ 文件中未找到：{target_file_path}")
                    # 尝试列出所有文件帮助调试
                    all_files = zip_ref.namelist()
                    if len(all_files) <= 20:  # 文件较少时才打印
                        CommonUtil.printLog(f"📋 可用文件列表：{all_files}")
                    else:
                        CommonUtil.printLog(f"📋 压缩包包含 {len(all_files)} 个文件")
                    return None

                # 根据模式读取文件
                with zip_ref.open(file_info) as file:
                    if mode == 'bytes':
                        # 返回原始字节（适合二进制文件）
                        return file.read()
                    elif mode == 'text':
                        # 返回完整文本字符串
                        content_bytes = file.read()
                        return content_bytes.decode(charset)
                    elif mode == 'lines':
                        # 按行返回列表（默认）
                        content_bytes = file.read()
                        content_str = content_bytes.decode(charset)
                        return [line.rstrip('\n') for line in content_str.splitlines()]
                    else:
                        CommonUtil.printLog(f"❌ 不支持的读取模式：{mode}，支持：lines/text/bytes")
                        return None
        except FileNotFoundError:
            CommonUtil.printLog(f"❌ ZIP 文件不存在：{zip_path}")
            return None
        except zipfile.BadZipFile:
            CommonUtil.printLog(f"❌ 无效的 ZIP 文件：{zip_path}")
            return None
        except RuntimeError as e:
            if 'password' in str(e).lower():
                CommonUtil.printLog(f"❌ 密码错误或压缩包需要密码：{e}")
            else:
                CommonUtil.printLog(f"❌ 读取运行时错误：{e}")
            return None
        except UnicodeDecodeError:
            CommonUtil.printLog(f"❌ 文件编码不是 {charset}：{target_file_path}")
            CommonUtil.printLog("💡 提示：尝试使用 mode='bytes' 或其他编码（如 gbk、latin-1）")
            return None
        except Exception as e:
            CommonUtil.printLog(f"❌ 读取文件失败：{e}")
            import traceback
            CommonUtil.printLog(traceback.format_exc())
            return None

    @staticmethod
    def unzip_files(zip_path: str, dest_dir: str = None, specific_files: list = None,
                    pwd: str = None, print_log: bool = True) -> tuple:
        """
        解压缩 ZIP 文件，支持解压全部文件或指定文件到目标目录
        
        :param zip_path: ZIP 压缩包路径
        :param dest_dir: 解压目标目录，若为 None 则解压到当前工作目录
        :param specific_files: 指定要解压的文件列表（在 ZIP 中的路径）
                              - None 或空列表：解压所有文件
                              - ['file1.txt', 'folder/file2.log']：只解压指定文件
        :param pwd: 密码（如果压缩包有密码保护）
        :param print_log: 是否打印处理日志
        :return: (bool, str) 前者表示是否解压成功，后者表示解压目录路径，失败时返回 (False, None)
        
        :example:
        # 示例 1: 解压所有文件
        success, path = unzip_files('data.zip', 'output/')
        
        # 示例 2: 只解压特定文件
        success, path = unzip_files('data.zip', 'output/',
        ...                            specific_files=['config.json', 'logs/error.log'])
        
        # 示例 3: 解压带密码的压缩包
        success, path = unzip_files('encrypted.zip', 'output/', pwd='123456')
        """
        import os

        # 参数校验
        if not FileUtil.isFileExist(zip_path):
            CommonUtil.printLog(f"❌ ZIP 文件不存在：{zip_path}")
            return False, None

        if not zip_path.lower().endswith('.zip'):
            CommonUtil.printLog(f"⚠️ 文件不是 ZIP 格式：{zip_path}")
            # 继续尝试，因为可能是 .zipx 或其他变体

        # 确定解压目录
        if CommonUtil.isNoneOrBlank(dest_dir):
            dest_dir = os.getcwd()

        FileUtil.makeDir(dest_dir)
        dest_dir = os.path.abspath(dest_dir)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 验证密码（如果有）
                if pwd is not None:
                    try:
                        zip_ref.setpassword(pwd.encode('utf-8'))
                    except Exception as e:
                        CommonUtil.printLog(f"❌ 密码设置失败：{e}")
                        return False, None

                # 确定要解压的文件列表
                all_files = zip_ref.namelist()

                if specific_files and len(specific_files) > 0:
                    # 过滤出指定的文件
                    files_to_extract = []
                    for f in specific_files:
                        if f in all_files:
                            files_to_extract.append(f)
                        else:
                            CommonUtil.printLog(f"⚠️ 文件中未找到：{f}")

                    if len(files_to_extract) == 0:
                        CommonUtil.printLog("❌ 没有要解压的有效文件")
                        return False, None

                    CommonUtil.printLog(f"📦 准备解压 {len(files_to_extract)} 个指定文件...", condition=print_log)
                else:
                    # 解压所有文件
                    files_to_extract = all_files
                    CommonUtil.printLog(f"📦 准备解压全部 {len(all_files)} 个文件...", condition=print_log)

                # 执行解压
                for file_path in files_to_extract:
                    try:
                        zip_ref.extract(file_path, dest_dir)
                        CommonUtil.printLog(f"   ✅ 已解压：{file_path}", condition=print_log)
                    except Exception as e:
                        CommonUtil.printLog(f"❌ 解压文件失败 {file_path}: {e}")
                        return False, None

                CommonUtil.printLog(f"✅ ZIP 解压成功，目标目录：{dest_dir}", condition=print_log)
                return True, dest_dir
        except zipfile.BadZipFile as e:
            CommonUtil.printLog(f"❌ 无效的 ZIP 文件：{e}")
            return False, None
        except RuntimeError as e:
            if 'password' in str(e).lower():
                CommonUtil.printLog(f"❌ 密码错误或压缩包需要密码：{e}")
            else:
                CommonUtil.printLog(f"❌ 解压运行时错误：{e}")
            return False, None
        except Exception as e:
            CommonUtil.printLog(f"❌ 解压失败：{e}")
            return False, None


if __name__ == '__main__':
    p = 'D:/temp/log_123456.7z'
    dest = CompressUtil().unzip(p, pwd='123')
    CommonUtil.printLog('dest=%s' % dest)
