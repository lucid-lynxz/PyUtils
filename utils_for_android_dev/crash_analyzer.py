#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os
import re
import subprocess
import sys
from typing import List, Tuple, Optional

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil

"""
使用时,请在系统环境变量中添加 aarch64-linux-android-addr2line 文件所在目录, 比如: 
mac:     ~/ProgramFiles/sdk/Android/ndk/21.4.7075529/toolchains/aarch64-linux-android-4.9/prebuilt/darwin-x86_64/bin
windows: D:/ProgramFiles/Android/SDK/ndk-bundle/toolchains/aarch64-linux-android-4.9/prebuilt/windows-x86_64/bin
    
支持以下几种使用方法:
1. 命令行传参:
   命令: python3 crash_analyzer.py <so文件路径> <崩溃堆栈文件或文本> [符号表文件]
   
   示例:
   python3 crash_analyzer.py libTester.so crash.txt"  # 适用于有符号的 SO
   python3 crash_analyzer.py libTester.so crash.txt libTester.sym  # 适用于无符号 SO
   python3 crash_analyzer.py libTester.so "#00 pc 00000000021ace5c /path/to/lib.so" # 直接传入堆栈文本
   
2. 若未传参, 或者参数个数小于3个, 则:
    a. 优先查找当前目录下:  ./cache/crash/ 下的so文件和堆栈日志文件: crash.txt 或者 tombstone_N, 若存在则进行反解
    b. 否则命令行界面会依次提示输入 so文件路径/堆栈文件路径/符号文件路径/addr2line文件路径, 由用户输入后再反解
"""


class CrashAnalyzer:
    """Android 崩溃堆栈分析工具，使用 addr2line 反解地址"""

    def __init__(self, so_path: str, sym_path: str = None, addr2line_path: str = None):
        """
        初始化分析器
        :param so_path: .so 文件路径
        :param sym_path: .sym 符号表文件路径(可选)
        """
        self.so_path = so_path
        self.sym_path = sym_path
        self.addr2line_path = self.find_addr2line() if addr2line_path is None else addr2line_path

        if not self.addr2line_path:
            raise RuntimeError("未找到 addr2line 工具，请确保已安装 NDK 或 Android SDK")

        # 自动检测并使用 symbol 目录下的 unstripped SO 文件
        self._detect_unstripped_so()

    @staticmethod
    def find_addr2line() -> Optional[str]:
        """查找 addr2line 工具"""

        # 常见的 addr2line 路径
        possible_paths = [
            'aarch64-linux-android-addr2line',  # 系统PATH中
            'addr2line',  # 系统PATH中
            'llvm-addr2line',  # LLVM版本
            '/usr/bin/addr2line',
            '/usr/local/bin/addr2line',
        ]

        # 尝试从常见 NDK 路径查找
        ndk_paths = [
            os.path.expanduser('~/Library/Android/sdk/ndk'),
            '~/ProgramFiles/sdk/Android/ndk',
        ]

        for ndk_path in ndk_paths:
            if os.path.exists(ndk_path):
                # 查找所有 NDK 版本
                try:
                    for ndk_version in os.listdir(ndk_path):
                        toolchain_path = os.path.join(
                            ndk_path, ndk_version,
                            'toolchains', 'aarch64-linux-android-4.9',
                            'prebuilt', 'darwin-x86_64', 'bin',
                            'aarch64-linux-android-addr2line'
                        )
                        if os.path.exists(toolchain_path):
                            possible_paths.insert(0, toolchain_path)
                except Exception:
                    continue

        for path in possible_paths:
            try:
                env = os.environ.copy()
                result = subprocess.run(
                    ['which', path],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=env  # 显式传递环境变量
                )
                print(f'check {path}:  {result}')
                if result.returncode == 0 and result.stdout.strip():
                    return path
            except Exception:
                continue

        return None

    @staticmethod
    def check_file_with_readelf(file_path: str) -> Tuple[Optional[bool], Optional[bool]]:
        """
        使用 readelf 检查文件类型(跨平台) 是否带符号信息
        :return: (is_stripped, has_debug_info)  is_stripped 表示符号信息是否被清除 True-被清除,无法反解, 需要额外传入符号表
        """
        if not FileUtil.isFileExist(file_path):
            return None, None

        if CommonUtil.isWindows():
            # Windows 上尝试使用 readelf(如果安装了 MinGW/MSYS2)
            try:
                result = subprocess.run(
                    ['readelf', '-S', file_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # 检查是否有 .debug_info 或 .debug_line 段
                    has_debug_info = '.debug_info' in result.stdout or '.debug_line' in result.stdout
                    # 如果有调试信息段，则不是 stripped
                    is_stripped = not has_debug_info
                    return is_stripped, has_debug_info
            except Exception:
                pass
            # Windows 上如果没有 readelf，返回未知状态
            # 后续会通过 addr2line 的实际输出来判断
            return False, False
        else:
            # Linux/macOS 上使用 file 命令
            try:
                result = subprocess.run(
                    ['file', file_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                is_stripped = 'stripped' in result.stdout and 'not stripped' not in result.stdout
                has_debug_info = 'not stripped' in result.stdout or 'with debug_info' in result.stdout
                return is_stripped, has_debug_info
            except Exception:
                return False, False

    def _detect_unstripped_so(self):
        """自动检测并使用 symbol 目录下的 unstripped SO 文件"""
        if not self.sym_path:
            # 检查当前 SO 文件是否为 stripped 版本
            try:
                is_stripped, _ = CrashAnalyzer.check_file_with_readelf(self.so_path)
                if is_stripped:
                    print(f"⚠️  警告: SO 文件为 stripped 版本(无调试符号)，可能无法反解出源文件和行号信息")
            except Exception as e:
                print(f"检查 SO 文件类型失败: {e}", file=sys.stderr)

            # 查找 SO 文件所在目录下的 symbol 子目录
            so_dir = os.path.dirname(self.so_path)
            symbol_dir = os.path.join(so_dir, 'symbol')

            if os.path.isdir(symbol_dir):
                so_filename = os.path.basename(self.so_path)
                unstripped_so_path = os.path.join(symbol_dir, so_filename)

                if os.path.exists(unstripped_so_path):
                    # 检查是否是 unstripped 文件
                    try:
                        _, has_debug_info = self.check_file_with_readelf(unstripped_so_path)
                        if has_debug_info:
                            print(f"✓ 检测到 unstripped SO 文件: {unstripped_so_path}")
                            print(f"  将使用 unstripped 版本进行地址反解")
                            self.so_path = unstripped_so_path
                    except Exception as e:
                        print(f"检测 unstripped SO 文件失败: {e}", file=sys.stderr)

    def _get_so_build_id(self) -> Optional[str]:
        """获取 SO 文件的 BuildId"""
        if CommonUtil.isWindows():
            # Windows 上尝试使用 readelf 获取 BuildId(如果安装了 MinGW/MSYS2)
            try:
                result = subprocess.run(
                    ['readelf', '-n', self.so_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # readelf -n 输出中查找 Build ID
                    build_id_match = re.search(r'Build ID:\s*([0-9a-fA-F]+)', result.stdout)
                    if build_id_match:
                        return build_id_match.group(1)
            except Exception:
                pass
            # Windows 上如果没有 readelf，无法获取 BuildId
            return None
        else:
            # Linux/macOS 上使用 file 命令
            try:
                result = subprocess.run(
                    ['file', self.so_path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # file 命令输出格式：... BuildID[sha1]=b3faf8935fd25b4bd4a3a3990a5d756e98f640b9, ...
                # 注意：BuildID 中的 ID 是大写的
                build_id_match = re.search(r'BuildID\[sha1\]=([0-9a-fA-F]+)', result.stdout)
                if build_id_match:
                    return build_id_match.group(1)
            except Exception as e:
                print(f"获取 SO 文件 BuildId 失败: {e}", file=sys.stderr)
            return None

    def parse_backtrace(self, backtrace_text: str) -> List[Tuple[str, str, str]]:
        """
        解析崩溃堆栈文本
        :param backtrace_text: 崩溃堆栈文本
        :return: 返回列表，每个元素是 (序号, 偏移地址, so路径)
        """
        frames = []
        lines = backtrace_text.strip().split('\n')

        # 匹配模式：#00 pc 00000000021ace5c  /path/to/libTester.so
        pattern = r'#(\d+)\s+pc\s+([0-9a-fA-F]+)\s+(.+)'

        for line in lines:
            line = line.strip()
            if not line or not line.startswith('#'):
                continue

            match = re.match(pattern, line)
            if match:
                frame_num = match.group(1)
                offset = match.group(2)
                so_path = match.group(3).strip()

                # 提取 BuildId(如果有)
                build_id = None
                build_id_match = re.search(r'BuildId:\s*([0-9a-fA-F]+)', so_path)
                if build_id_match:
                    build_id = build_id_match.group(1)
                    so_path = so_path.split('(BuildId:')[0].strip()

                frames.append((frame_num, offset, so_path, build_id))

        return frames

    def _find_ndk_stack(self) -> Optional[str]:
        """查找 ndk-stack 工具"""
        # 常见的 ndk-stack 路径
        possible_paths = [
            'ndk-stack',  # 系统PATH中
            '/usr/local/bin/ndk-stack',
        ]

        for path in possible_paths:
            try:
                result = subprocess.run(
                    ['which', path],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return path
            except Exception:
                continue

        return None

    def _parse_sym_file(self, sym_path: str) -> dict:
        """
        解析 Breakpad .sym 符号表文件
        :param sym_path: .sym 文件路径
        :return: 返回字典 {offset: (function, file, line)}
        """
        symbols = {}
        try:
            with open(sym_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 跳过文件头(前几行是 MODULE、INFO 等元数据)
            # FUNC 记录格式：FUNC m r offset size function_name
            # LINE 记录格式：LINE m r offset line_number file_id

            current_func = None
            current_file = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) < 4:
                    continue

                if parts[0] == 'FUNC':
                    # FUNC m r offset size function_name
                    # offset 是函数相对于模块基地址的偏移
                    offset = int(parts[2], 16)
                    func_name = ' '.join(parts[5:])
                    current_func = func_name
                    current_file = '?'
                    symbols[offset] = (current_func, current_file, '?')
                elif parts[0] == 'LINE':
                    # LINE m r offset line_number file_id
                    offset = int(parts[2], 16)
                    line_num = parts[3]
                    file_id = parts[4]
                    if current_func:
                        symbols[offset] = (current_func, file_id, line_num)
                elif parts[0] == 'FILE':
                    # FILE id file_name
                    file_id = parts[1]
                    file_name = ' '.join(parts[2:])
                    if file_name == '0':
                        current_file = '?'
                    else:
                        current_file = file_name

        except Exception as e:
            print(f"解析 .sym 文件失败: {e}", file=sys.stderr)

        return symbols

    def resolve_with_sym(self, offset: int, symbols: dict) -> Tuple[str, str]:
        """
        使用符号表反解地址
        :param offset: 偏移地址(十进制整数)
        :param symbols: 符号表字典
        :return: (函数名, 文件:行号)
        """
        # 找到最接近的符号
        sorted_offsets = sorted([k for k in symbols.keys() if k <= offset], reverse=True)

        if not sorted_offsets:
            return '??', '??'

        nearest_offset = sorted_offsets[0]
        func, file, line = symbols[nearest_offset]

        return func, f"{file}:{line}"

    def resolve_address(self, offset: str) -> Tuple[str, str]:
        """
        使用 addr2line 反解单个地址
        :param offset: 偏移地址(十六进制字符串)
        :return: (函数名, 文件:行号)
        """
        # 如果有 .sym 符号表，优先使用符号表
        if self.sym_path:
            try:
                offset_int = int(offset, 16)
                if not hasattr(self, '_sym_cache'):
                    self._sym_cache = self._parse_sym_file(self.sym_path)

                if self._sym_cache:
                    return self.resolve_with_sym(offset_int, self._sym_cache)
            except Exception as e:
                print(f"使用符号表反解失败: {e}, 尝试使用 addr2line", file=sys.stderr)

        # 使用 addr2line
        try:
            # 使用 -e 指定可执行文件，-f 显示函数名，-C 反修饰函数名
            cmd = [
                self.addr2line_path,
                '-e', self.so_path,
                '-f',  # 显示函数名
                '-C',  # 反修饰 C++ 符号
                '-p',  # 可读格式
                offset
            ]

            print(f'cmd: {" ".join(cmd)}')
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                # 输出格式通常是：function_name
                # 第二行是 file:line
                lines = output.split('\n')
                function = lines[0] if lines else '??'
                location = lines[1] if len(lines) > 1 else '??'

                return function, location
            else:
                return '??', f'addr2line error: {result.stderr}'

        except subprocess.TimeoutExpired:
            return '??', 'timeout'
        except Exception as e:
            return '??', f'exception: {str(e)}'

    def analyze(self, backtrace_text: str) -> List[str]:
        """
        分析崩溃堆栈
        :param backtrace_text: 崩溃堆栈文本
        :return: 格式化后的分析结果
        """
        frames = self.parse_backtrace(backtrace_text)

        if not frames:
            return ["未找到有效的堆栈帧"]

        results = []
        results.append("=" * 80)
        results.append(f"使用 addr2line 分析结果")
        results.append(f"SO 文件: {self.so_path}")
        if self.sym_path:
            results.append(f"符号表: {self.sym_path}")
        results.append("=" * 80)
        results.append("")

        for frame_num, offset, so_path, build_id in frames:
            results.append(f"Frame #{frame_num}")
            results.append(f"  偏移地址: 0x{offset}")
            results.append(f"  SO 路径: {so_path}")
            if build_id:
                results.append(f"  BuildId: {build_id}")

            function, location = self.resolve_address(offset)
            results.append(f"  反解结果:")
            results.append(f"    函数: {function}")
            results.append(f"    位置: {location}")
            results.append("")

        return results

    def analyze_batch(self, backtrace_text: str) -> List[str]:
        """
        批量分析(优先使用符号表，否则使用一次 addr2line 调用处理所有地址)
        :param backtrace_text: 崩溃堆栈文本
        :return: 格式化后的分析结果
        """
        frames = self.parse_backtrace(backtrace_text)

        if not frames:
            return ["未找到有效的堆栈帧"]

        # 检查 BuildId 是否一致
        so_build_id = self._get_so_build_id()
        if so_build_id:
            # 从崩溃堆栈中提取 BuildId
            crash_build_id = None
            for _, _, _, frame_build_id in frames:
                if frame_build_id:
                    crash_build_id = frame_build_id
                    break

            if crash_build_id and crash_build_id != so_build_id:
                print(f"⚠️ 警告: BuildId 不一致")
                print(f"   SO 文件 BuildId: {so_build_id}")
                print(f"   崩溃堆栈 BuildId: {crash_build_id}")
                print(f"   可能原因: SO 文件版本与崩溃时的版本不匹配，反解结果可能不准确")
                print(f"\n")

        # 收集所有偏移地址
        offsets = [offset for _, offset, _, _ in frames]

        # 尝试使用符号表
        if self.sym_path:
            print(f'使用符号表批量分析')
            try:
                if not hasattr(self, '_sym_cache'):
                    self._sym_cache = self._parse_sym_file(self.sym_path)

                if self._sym_cache:
                    # 使用符号表批量反解
                    resolved_info = {}
                    for offset in offsets:
                        offset_int = int(offset, 16)
                        function, location = self.resolve_with_sym(offset_int, self._sym_cache)
                        resolved_info[offset] = (function, location)

                    # 格式化输出 - 简洁格式
                    results = []
                    results.append("=" * 80)
                    results.append(f"使用 Breakpad 符号表分析结果")
                    results.append(f"SO 文件: {self.so_path}")
                    results.append(f"符号表: {self.sym_path}")
                    results.append("=" * 80)
                    results.append("")

                    for frame_num, offset, so_path, build_id in frames:
                        function, location = resolved_info.get(offset, ('??', '??'))
                        results.append(f"#{frame_num} --->>>")
                        results.append(f" {function} at {location}")
                        results.append("")

                    return results
            except Exception as e:
                print(f"使用符号表批量分析失败: {e}, 尝试使用 addr2line", file=sys.stderr)

        # 使用 addr2line 批量分析
        try:
            # 一次性传入所有地址
            cmd = [
                      self.addr2line_path,
                      '-e', self.so_path,
                      '-f',  # 显示函数名
                      '-C',  # 反修饰 C++ 符号
                  ] + offsets

            print(f'使用addr2line反解: {" ".join(cmd)}')

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return [f"addr2line 执行失败: {result.stderr}"]

            # 解析输出(每个地址对应两行：函数名和位置)
            output_lines = result.stdout.strip().split('\n')
            resolved_info = {}

            for i, offset in enumerate(offsets):
                if i * 2 + 1 < len(output_lines):
                    function = output_lines[i * 2]
                    location = output_lines[i * 2 + 1]
                    resolved_info[offset] = (function, location)
                else:
                    resolved_info[offset] = ('??', '??')

            # 格式化输出 - 简洁格式
            results = []
            results.append('\n')
            results.append("=" * 80)
            results.append(f"批量 addr2line 分析结果")
            results.append(f"SO 文件: {self.so_path}")
            if self.sym_path:
                results.append(f"符号表: {self.sym_path}")
            results.append("=" * 80)
            results.append("")

            for frame_num, offset, so_path, build_id in frames:
                function, location = resolved_info.get(offset, ('??', '??'))
                results.append(f"#{frame_num} --->>>")
                results.append(f" {function} at {location}")
                results.append("")

            return results

        except subprocess.TimeoutExpired:
            return ["addr2line 执行超时"]
        except Exception as e:
            return [f"批量分析异常: {str(e)}"]


def main(so_path: str, backtrace_input: str, sym_path: str = None, addr2line_path: str = None) -> str:
    # 判断第二个参数是文件还是直接文本
    import os
    if os.path.isfile(backtrace_input):
        with open(backtrace_input, 'r', encoding='utf-8') as f:
            backtrace_text = f.read()
    else:
        backtrace_text = backtrace_input

    # 创建分析器
    try:
        analyzer = CrashAnalyzer(so_path, sym_path, addr2line_path)

        # 执行批量分析
        results = analyzer.analyze_batch(backtrace_text)

        # 输出结果
        for line in results:
            print(line)
        return '\n'.join(results)
    except Exception as e:
        print(f"错误: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    cache_dir = FileUtil.create_cache_dir(None, __file__)
    crash_dir = FileUtil.create_cache_dir(cache_dir, name='crash')

    # # 若是在IDE启动后才添加的环境变量, 请重新启动IDE, 否则可能获取不到
    # print(f"环境变量 PATH: {os.environ.get('PATH')}")

    addr2line_path = CrashAnalyzer.find_addr2line()
    print(f'找到的addr2line: {addr2line_path}\n')

    so_files = FileUtil.listAllFilePath(crash_dir, 1, 0, False, lambda so_path: so_path.endswith('.so'))
    so_path = '' if CommonUtil.isNoneOrBlank(so_files) else f'{so_files[0]}'  # 有/无 符号 .so 文件路径

    crash_txt = FileUtil.recookPath(f'{crash_dir}/crash.txt')  # 默认的崩溃堆栈文件名
    if not FileUtil.isFileExist(crash_txt):
        tombstone_files = FileUtil.listAllFilePath(crash_dir, 1, 0, False, lambda so_path: 'tombstone_' in so_path)
        tombstone_path = '' if CommonUtil.isNoneOrBlank(tombstone_files) else f'{tombstone_files[0]}'  # 存在 tombstone_xx 文件
        crash_txt = tombstone_path
    backtrace_input = FileUtil.recookPath(crash_txt)  # 最终使用的堆栈文本路径

    # 符号文件
    _, so_name, _ = FileUtil.getFileName(so_path)
    sym_path = None if CommonUtil.isNoneOrBlank(so_name) else f'{crash_dir}/{so_name}.sym'  # 符号文件路径
    if not FileUtil.isFileExist(sym_path):
        sym_path = None

    # print("使用方法:")
    # print("  python crash_analyzer.py <so文件路径> <崩溃堆栈文件或文本> [符号表文件]")
    # print("")
    # print("示例:")
    # print("  python crash_analyzer.py libTester.so crash.txt")  # 使用 addr2line 分析(适用于有符号的 SO)
    # print("  python crash_analyzer.py libTester.so crash.txt libTester.sym")  # 使用符号表分析(推荐用于无符号 SO)
    # print("")
    # print("或者直接传入堆栈文本:")
    # print('  python crash_analyzer.py libTester.so "#00 pc 00000000021ace5c /path/to/lib.so"')  # 直接传入堆栈文本
    # print("")

    if len(sys.argv) >= 3:
        so_path = sys.argv[1]
        backtrace_input = sys.argv[2]
        sym_path = sys.argv[3] if len(sys.argv) > 3 else None
    else:
        so_path = CommonUtil.get_input_info(f"请输入待反解的SO文件路径(默认:{so_path.replace(cache_dir, '')}):", so_path)

        backtrace_input = CommonUtil.get_input_info(f"请输入堆栈文件或者内容(默认:{backtrace_input.replace(cache_dir, '')}):", backtrace_input)

        if CrashAnalyzer.check_file_with_readelf(so_path)[0]:
            sym_path = CommonUtil.get_input_info(f"请输入符号文件路径(默认:{sym_path}): ", sym_path)

    if CommonUtil.isNoneOrBlank(addr2line_path):
        addr2line_path = CommonUtil.get_input_info(f"请输入addr2line路径:", '')

    result_info = main(so_path, backtrace_input, sym_path, addr2line_path)
    result_log_path = FileUtil.recookPath(f'{crash_dir}/反解结果.txt')
    success = FileUtil.write2File(result_log_path, result_info)
    CommonUtil.printLog(f"反解结果保存到: {result_log_path}")
