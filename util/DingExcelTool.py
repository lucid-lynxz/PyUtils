#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉在线表格操作工具(基于「钉钉表格」MCP)

与 `DingDocTool` 不同,本类不处理文件上传、目录节点等文档级操作,
只聚焦钉钉在线表格的单元格/工作表级读写：创建表格、读取/写入单元格、
追加行、删除工作表等

首次使用需开通 MCP：
    https://aihub.dingtalk.com/#/mcp-market/detail?mcpId=9704
    进入页面后,在右侧「使用 MCP」区域复制 StreamableHttp URL
    (格式类似 https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>)

配置方式(任选其一)：
    1. 构造函数传入 mcp_url='https://mcp-gw.dingtalk.com/server/<server_id>?key=<key>'
    2. 环境变量 DINGTALK_TABLE_MCP_URL(单条 URL)或 DINGTALK_TABLE_MCP_SERVERS(JSON 数组)
    3. .env 文件中设置上述变量(需安装 python-dotenv)

使用示例：
    from util.DingExcelTool import DingExcelTool

    tool = DingExcelTool()

    # 1. 新建表格
    new_sheet = tool.create_sheet("测试表格")
    node_id = new_sheet["nodeId"]

    # 2. 查看工作表
    sheets = tool.get_sheets(node_id)
    sheet_id = sheets[0]["sheetId"]

    # 3. 写入数据(覆盖 A1:B2)
    tool.write_range(
        node_id,
        sheet_id,
        "A1:B2",
        [
            [{"type": "text", "text": "姓名"}, {"type": "text", "text": "年龄"}],
            [{"type": "text", "text": "张三"}, {"type": "text", "text": "18"}],
        ],
    )

    # 3.1 只改已存在表格的 B5:B6 两行,不动其它列(range_address 指定起始位置,
    # 行/列数由 cells 自动推导;不想要的列传 {} 表示跳过而非清空)
    tool.write_range(
        node_id,
        sheet_id,
        "B5",
        [
            [{"type": "text", "text": "新值1"}],
            [{"type": "text", "text": "新值2"}],
        ],
    )

    # 4. 追加行
    tool.append_rows(node_id, sheet_id, [["李四", "20"]])

    # 5. 读取数据
    data = tool.read_range(node_id, sheet_id, "A1:B3")
    print(data)
"""
import json
import os
import re
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from util.DingTalkMCPClient import DEFAULT_MCP_TIMEOUT, DingTalkMCPClient, DingTalkMCPError

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None


def _load_dotenv(path: Optional[Union[str, Path]] = None) -> None:
    """加载指定 .env 文件；path 为 None 时加载当前文件所在目录的 .env"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    if path is None:
        default_path = Path(__file__).resolve().parent / ".env"
        if default_path.exists():
            load_dotenv(default_path)
    elif str(path):
        load_dotenv(path)


# 模块导入时默认加载当前文件所在目录的 .env(若存在)
_load_dotenv()


class DingExcelTool:
    """钉钉在线表格级操作工具"""

    def __init__(
            self,
            mcp_url: Optional[str] = None,
            mcp_servers: Optional[List[Dict[str, Any]]] = None,
            dotenv_path: Optional[Union[str, Path]] = None,
            timeout: int = DEFAULT_MCP_TIMEOUT,
    ):
        """
        Args:
            mcp_url: 钉钉表格 MCP 授权地址(单条)
                格式：`https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>`
                如果传了该参数,会优先使用；不传则尝试环境变量 / .env 文件
            mcp_servers: 多条表格 MCP 服务器配置(可选)
                用于跨组织场景或需要自动容灾切换时传入,例如：
                `[{"base_url": "...", "server_id": "...", "key": "..."}]`
                与 mcp_url 二选一即可
            dotenv_path: 指定要加载的 .env 文件路径(可选)
                为 None 时已在模块导入时加载当前文件所在目录的 .env；
                传入具体路径时额外加载该 .env；传空字符串则不加载任何 .env
            timeout: MCP 接口调用超时时间,单位秒,默认 60 秒
        """
        if dotenv_path is not None:
            _load_dotenv(dotenv_path)

        mcp_url = mcp_url or os.getenv("DINGTALK_TABLE_MCP_URL")
        mcp_servers = mcp_servers or (
            json.loads(os.getenv("DINGTALK_TABLE_MCP_SERVERS", "[]"))
            if os.getenv("DINGTALK_TABLE_MCP_SERVERS")
            else None
        )
        if not mcp_url and not mcp_servers:
            raise DingTalkMCPError(
                "未配置钉钉表格 MCP 授权地址\n"
                "请前往钉钉 AIHub 开通「钉钉表格」MCP 并复制授权地址：\n"
                "  https://aihub.dingtalk.com/#/mcp-market/detail?mcpId=9704\n\n"
                "然后通过以下任一方式配置：\n"
                "1. 构造函数传入 mcp_url='https://mcp-gw.dingtalk.com/server/<server_id>?key=<key>'\n"
                "2. 环境变量 DINGTALK_TABLE_MCP_URL(单条 URL)或 DINGTALK_TABLE_MCP_SERVERS(JSON 数组)\n"
                "3. .env 文件中设置上述变量(需安装 python-dotenv)"
            )
        self.mcp = DingTalkMCPClient(
            mcp_url=mcp_url, mcp_servers=mcp_servers, timeout=timeout
        )

    def create_sheet(
            self,
            name: str,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """新建一篇钉钉在线表格

        Args:
            name: 新表格标题
            folder_id: 目标文件夹节点 ID(可选)不传则按 workspace_id 或用户我的文档创建
            workspace_id: 目标知识库 ID(可选)

        Returns:
            create_workspace_sheet 的原始返回结果,通常包含 nodeId / url 等字段
        """
        return self.mcp.call_tool(
            "create_workspace_sheet",
            name=name,
            folderId=folder_id,
            workspaceId=workspace_id,
        )

    def get_sheets(self, node_id: str) -> List[Dict[str, Any]]:
        """获取钉钉在线表格中的所有工作表列表

        Args:
            node_id: 表格文档 ID 或文档链接 URL

        Returns:
            工作表信息列表,每个元素包含 sheetId / name 等字段
        """
        result = self.mcp.call_tool("get_all_sheets", nodeId=node_id)
        return result.get("sheets", [])

    def read_range(
            self,
            node_id: str,
            sheet_id: Optional[str] = None,
            range_str: Optional[str] = None,
            value_render_option: Optional[str] = None,
    ) -> Dict[str, Any]:
        """读取钉钉在线表格指定范围的单元格信息

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称(可选,默认第一个工作表)
            range_str: 读取范围,A1 表示法(可选,默认读取全部非空数据)
                注意：钉钉表格 MCP 对单次返回数据量有限制(约 2MB),
                数据量较大时必须指定具体范围,否则会报"返回数据量超过最大限制"
            value_render_option: 取值模式(可选)：formatted_value / raw_value / formula

        Returns:
            get_cell_infos 的原始返回结果
        """
        if not sheet_id and not range_str:
            # 不指定范围时默认读取第一个工作表的前 1000 行,避免全表数据量超限
            sheets = self.get_sheets(node_id)
            if not sheets:
                raise RuntimeError(f"表格 {node_id} 中没有工作表")
            sheet_id = sheets[0]["name"]
            range_str = "A1:Z100"
            print(f"[DingExcelTool] read_range 未指定范围,默认读取 {sheet_id}!{range_str}；如需读取全部数据请使用 read_all_rows()")

        return self.mcp.call_tool(
            "get_cell_infos",
            nodeId=node_id,
            sheetId=sheet_id,
            range=range_str,
            valueRenderOption=value_render_option,
        )

    @staticmethod
    def _col_index_to_letter(index: int) -> str:
        """将 1-based 列索引转为 Excel 列字母(1->A, 27->AA)"""
        if index <= 0:
            return "A"
        letters = []
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            letters.append(chr(remainder + ord("A")))
        return "".join(reversed(letters))

    @staticmethod
    def _letter_to_col_index(letters: str) -> int:
        """将 Excel 列字母转为 1-based 列索引(A->1, AA->27)"""
        index = 0
        for char in letters.upper():
            index = index * 26 + (ord(char) - ord("A") + 1)
        return index

    @classmethod
    def _parse_range(
            cls, range_address: str
    ) -> Tuple[int, int, Optional[int], Optional[int]]:
        """解析 A1 表示法范围为 (起始行, 起始列, 结束行, 结束列)

        支持三种写法：
            "A1:C3"  完整范围,行列数必须与 cells 维度一致
            "B5"     只给起始单元格,结束行/列由 cells 维度自动推导
            "C"      整列(等价于从 C1 开始),同上自动推导
        行/列号均为 1-based,返回中结束行/列为 None 表示待推导
        """
        match = re.match(
            r"^\$?([A-Za-z]+)\$?(\d+)?(?::\$?([A-Za-z]+)\$?(\d+)?)?$",
            range_address.strip(),
        )
        if not match:
            raise ValueError(
                f"range_address 格式不正确: {range_address!r},"
                f"请使用 A1 表示法,如 'A1:C3' 或 'B5'"
            )
        start_col = cls._letter_to_col_index(match.group(1))
        start_row = int(match.group(2)) if match.group(2) else 1
        end_col = (
            cls._letter_to_col_index(match.group(3)) if match.group(3) else None
        )
        end_row = int(match.group(4)) if match.group(4) else None
        if end_row is not None and end_row < start_row:
            raise ValueError(f"range_address 结束行小于起始行: {range_address!r}")
        if end_col is not None and end_col < start_col:
            raise ValueError(f"range_address 结束列小于起始列: {range_address!r}")
        return start_row, start_col, end_row, end_col

    def _call_with_retry(
            self,
            tool_name: str,
            action_tip: str,
            max_retries: int = 3,
            retry_interval: float = 2.0,
            **arguments,
    ) -> Dict[str, Any]:
        """调用幂等的 MCP 请求(绝对范围写入/清除/读取), 失败自动原样重发; 重发耗尽仍失败才抛 DingTalkMCPError

        为什么需要重试: 钉钉表格侧偶发返回 {"success": false} 且不带 errorMessage
        (日志里只剩"未知错误"), 大范围写入后紧接着再写下一批尤其常见。
        这类失败是瞬时的, 同一请求重发即可恢复, 不该因此让整表上传中断。
        注意: 只给幂等请求用——set_cell_range/clear_range 是"绝对范围 + 整块覆盖",
        重发结果一致; append_rows 这类非幂等写不要走本方法, 否则重试会追加出重复行。

        Args:
            tool_name: MCP 工具名, 如 set_cell_range
            action_tip: 日志里的动作描述, 如 "写入 A181:CP229"
            max_retries: 首次失败后最多重发次数, 默认 3(即总共最多请求 4 次); 传 0 表示不重试
            retry_interval: 首次重试前等待秒数, 之后逐次翻倍(2s → 4s → 8s)

        Returns:
            成功那次的原始返回(可能是非 dict 的裸返回, 此时按成功处理)

        Raises:
            DingTalkMCPError: 重发耗尽仍失败
        """
        attempts = max(1, max_retries + 1)
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                wait = retry_interval * (2 ** (attempt - 2))
                print(f"[DingExcelTool] {action_tip} 失败, {wait:.0f}s 后重发"
                      f"(第{attempt}/{attempts}次尝试)")
                time.sleep(wait)

            try:
                result = self.mcp.call_tool(tool_name, **arguments)
            except DingTalkMCPError as e:
                last_error = e
            else:
                if not isinstance(result, dict) or result.get("success") is not False:
                    return result
                last_error = DingTalkMCPError(
                    result.get("errorMessage") or result.get("message") or "未知错误",
                    details=result,
                )

        raise DingTalkMCPError(
            f"{action_tip} 连续 {attempts} 次均失败, 最后错误: {last_error}",
            details={"toolName": tool_name, "attempts": attempts},
        )

    def write_range(
            self,
            node_id: str,
            sheet_id: str = "Sheet1",
            range_address: str = "",
            cells: Optional[List[List[Dict[str, Any]]]] = None,
            batch_rows: int = 180,
            clear_before_write: bool = False,
            max_retries: int = 3,
    ) -> Dict[str, Any]:
        """向钉钉在线表格指定区域写入单元格内容

        当 cells 行数超过 batch_rows 时,会自动分批调用 set_cell_range,
        避免单次请求体过大导致钉钉 MCP 返回「未知错误」。

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称,默认为 "Sheet1"
            range_address: 写入范围,A1 表示法
                "A1:C3"  完整范围,其行/列数必须与 cells 维度一致
                "B5"     仅指定起始位置,范围大小由 cells 维度推导,
                         适用于“只改某几行的某几列”的场景
                ""       空字符串(默认)等价于从 A1 开始,范围由 cells 推导
            cells: 二维数组,每个元素为单元格对象,例如 {"type": "text", "text": "值"}
                可传入 {} 表示跳过该单元格(保留原有内容,不是清空)；
                想清空请传 {"type": "text", "text": ""}
                行内单元格个数不足最宽行时,会自动在尾部补 {},避免与范围宽度不一致
            batch_rows: 每批最大写入行数。实测 94 列表格约 180 行安全,
                超过后 set_cell_range 会报「未知错误」。
            clear_before_write: 是否在每一批 set_cell_range 前, 先对该批 range 执行
                clear_range(type="all") 清除内容与格式(含超链接)。
                钉钉 set_cell_range 用纯文本 {"type":"text"} 写入时,只会替换
                单元格显示文本,不会重置单元格已绑定的超链接属性——若旧数据是
                URL 类型单元格(如 https://example.org),覆盖为新值(https://example.com)后
                显示虽为新文字,点击却仍跳旧链接,造成「看到的不等于跳的」。
                置 True 可先清掉残留超链接/格式再写入,保证显示与跳转一致；
                代价是同时清除该区域原有字体/颜色等格式(本方法本就只写纯文本)。
                清除按批进行且紧跟该批写入, 所以中途失败最多只留白当前一批;
                注意它只覆盖本次写入范围, 新数据比旧数据短时表尾会剩旧行,
                由 upload_excel() 调用 clear_stale_tail() 补清(本方法不负责)。
                默认 False,保持既有行为。
            max_retries: 单批清除/写入失败后的重发次数,默认 3(即单批最多请求 4 次),传 0 关闭。
                钉钉在大范围写入后紧接着再写下一批时,文档侧常还在落盘,会瞬时回
                success=false 且不带 errorMessage;详见 _call_with_retry()。

        Returns:
            最后一批 set_cell_range 的返回结果；全部成功时 overall success 为 True。

        Raises:
            ValueError: cells 为空、range_address 格式错误或与 cells 维度不匹配
            DingTalkMCPError: 某一批重发耗尽仍失败;错误信息里会标明失败的 range、
                已写入多少行,以及(clear_before_write=True 时)该批是否已被清除但未回填。
        """
        if cells is None:
            raise ValueError("cells 参数不能为空")

        total_rows = len(cells)
        if total_rows == 0:
            return {"success": True, "message": "无数据需要写入"}

        total_cols = max(len(row) for row in cells)
        if total_cols == 0:
            raise ValueError("cells 中所有行都是空列表,无法确定写入列数")

        # 补齐短行,保证每行单元格数与写入范围宽度一致(补位用 {} 表示不动原值)
        batch_cells = [list(row) + [{}] * (total_cols - len(row)) for row in cells]

        start_row, start_col, end_row, end_col = (
            self._parse_range(range_address)
            if range_address
            else (1, 1, None, None)
        )
        if end_row is not None and end_row - start_row + 1 != total_rows:
            raise ValueError(
                f"range_address {range_address!r} 共 {end_row - start_row + 1} 行,"
                f"与 cells 行数 {total_rows} 不一致"
            )
        if end_col is not None and end_col - start_col + 1 != total_cols:
            raise ValueError(
                f"range_address {range_address!r} 共 {end_col - start_col + 1} 列,"
                f"与 cells 列数 {total_cols} 不一致"
            )
        end_row = start_row + total_rows - 1
        end_col = start_col + total_cols - 1
        start_col_letter = self._col_index_to_letter(start_col)
        end_col_letter = self._col_index_to_letter(end_col)

        # 逐批"先清自己这一段, 紧接着写这一段": 清除范围与写入范围完全一致,
        # 这样即使中途失败, 留白的也只有当前这一批, 而不是整张表。
        # 若改成写入前一次性清空整个范围, 一旦某批写失败, 前面已写的和后面没写的
        # 都会被这次大清空抹掉, 等于数据丢失。
        last_result: Dict[str, Any] = {"success": True}
        for start in range(0, total_rows, batch_rows):
            batch = batch_cells[start: start + batch_rows]
            first_row = start_row + start
            last_row = start_row + start + len(batch) - 1
            batch_range = f"{start_col_letter}{first_row}:{end_col_letter}{last_row}"
            if clear_before_write:
                print(f"[DingExcelTool] 写入前清除范围 {batch_range} 内容与格式(clear_range type=all)")
                self._call_with_retry(
                    "clear_range", f"清除 {batch_range}",
                    max_retries=max_retries,
                    nodeId=node_id, sheetId=sheet_id, range=batch_range, type="all",
                )
            print(f"[DingExcelTool] 写入第 {first_row}-{last_row} 行, 范围 {batch_range}")
            try:
                result = self._call_with_retry(
                    "set_cell_range",
                    f"写入 {batch_range}",
                    max_retries=max_retries,
                    nodeId=node_id,
                    sheetId=sheet_id,
                    rangeAddress=batch_range,
                    cells=batch,
                )
            except DingTalkMCPError as e:
                tip = (f"前 {first_row - start_row} 行已写入, {batch_range} 及之后未写入"
                       if first_row > start_row else "首批即失败, 全部数据均未写入")
                clear_tip = (f", 且 {batch_range} 已被 clear_range 清空但未回填"
                             if clear_before_write else "")
                raise DingTalkMCPError(
                    f"{e} [{tip}{clear_tip}]",
                    details={"failedRange": batch_range},
                ) from e
            last_result = result if isinstance(result, dict) else {"success": True, "raw": result}

        return {
            **last_result,
            "success": True,
            "message": f"Successfully updated {total_rows} rows in batches.",
            "totalRows": total_rows,
            "totalCols": total_cols,
            "rangeAddress": f"{start_col_letter}{start_row}:{end_col_letter}{end_row}",
            "batchRows": batch_rows,
        }

    @staticmethod
    def _parse_cell_infos(result: Dict[str, Any]) -> List[Tuple[int, str]]:
        """把 get_cell_infos 的返回拆成 [(绝对行号, 该行第一列文本), ...]

        实测(3 列表格 A1:C4)返回 cells 为二维数组(行 x 列), 每个单元格形如
        {"value": "文本"} 或 {"cellStyles": {...}, "value": ""}, 空单元格也会返回;
        rowIndices 与 cells 的行一一对应, 是表格里的绝对行号,
        因此本方法只取每行第一列的文本。
        """
        cells = result.get("cells") or []
        row_indices = result.get("rowIndices") or []
        rows: List[Tuple[int, str]] = []
        for idx, row in enumerate(cells):
            if idx >= len(row_indices):
                break
            first_cell = row[0] if isinstance(row, list) and row else {}
            text = "" if first_cell is None else str(first_cell.get("value", "") or "")
            rows.append((int(row_indices[idx]), text))
        return rows

    def clear_stale_tail(
            self,
            node_id: str,
            sheet_id: str,
            after_row: int,
            total_cols: int,
            probe_rows: int = 1000,
            max_probes: int = 5,
            max_retries: int = 3,
    ) -> int:
        """清除 after_row 之后残留的旧数据行, 返回实际清除的行数(0 表示表尾本就为空)

        为什么需要它: 覆盖写只会命中本次数据的行范围。新数据比钉钉表格里的旧数据短时,
        表尾多出来的旧行没人写也没人清, 看起来就像"上传后还剩一批历史数据"。
        实现上只能往下逐段探测 A 列找最后一个非空行——实测 get_all_sheets 只返回
        name/sheetId/tabColor, 没有行列数, 所以没法一步定位表尾。

        已知边界(都不影响主流程, 需要更严格时请自行读表校验):
            1. 只按 A 列判断某行是否有数据; 若旧数据存在 A 列为空但其他列有值的行, 会漏清。
            2. 探测深度上限 probe_rows * max_probes(默认 5000 行), 超出部分不会清。
            3. 只清到本次写入的列宽(total_cols), 旧数据比新数据更宽时右侧残留列不归本方法管。

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称
            after_row: 本次写入的最后一行, 只处理它之后的行
            total_cols: 本次写入的列数, 用于推导清除范围的最后一列
            probe_rows: 单次探测窗口行数, 默认 1000(只取 A 列文本, 不会触发数据量超限)
            max_probes: 最多探测窗口个数, 默认 5
            max_retries: 单次读取/清除失败后的重发次数, 透传 _call_with_retry()

        Returns:
            实际清除的行数
        """
        col_letter = self._col_index_to_letter(max(1, total_cols))
        last_non_empty_row = 0
        win_start = after_row + 1
        for _ in range(max(1, max_probes)):
            win_end = win_start + probe_rows - 1
            result = self._call_with_retry(
                "get_cell_infos", f"探测表尾 A{win_start}:A{win_end}",
                max_retries=max_retries,
                nodeId=node_id, sheetId=sheet_id, range=f"A{win_start}:A{win_end}",
            )
            rows = self._parse_cell_infos(result)
            filled = [row_no for row_no, text in rows if text]
            if not filled:
                break
            last_non_empty_row = max(last_non_empty_row, max(filled))
            if len(rows) < win_end - win_start + 1:
                # 返回行数不足说明已到表格边界, 不必再往下探
                break
            win_start = win_end + 1

        if last_non_empty_row <= after_row:
            return 0

        tail_range = f"A{after_row + 1}:{col_letter}{last_non_empty_row}"
        print(f"[DingExcelTool] 新数据止于第 {after_row} 行, 清除表尾旧数据 {tail_range}")
        self._call_with_retry(
            "clear_range", f"清除表尾 {tail_range}",
            max_retries=max_retries,
            nodeId=node_id, sheetId=sheet_id, range=tail_range, type="all",
        )
        return last_non_empty_row - after_row

    @staticmethod
    def _cell_hyperlink(text: str) -> Dict[str, Any]:
        """按单元格文本推导 cell 级 hyperlink 字段(实测语义见 upload_excel(link_cols=...) 说明)

        http/https 开头的文本 -> 整格链接指向该 URL; 其余(普通文本/空) -> 显式清除旧链接。
        注意: 形如 "example.com:443" 的裸域名不带协议, 无法猜出该链到 http 还是 https,
        一律按清除处理, 宁可不可点也不要"显示 A 跳 B"。
        """
        stripped = (text or "").strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            return {"type": "path", "link": stripped}
        return {"type": "none"}

    @classmethod
    def _resolve_col_indexes(
            cls, headers: List[str], selectors: List[Union[int, str]]
    ) -> List[int]:
        """把列选择器统一解析成 1-based 列号(顺序去重)

        selectors 每一项支持三种写法, 解析优先级从高到低：
            列名   如 "detail" —— 与 headers(本地表头行)先精确后忽略大小写匹配
            列字母 如 "BJ"     —— 纯字母时按 Excel 列字母换算
            列号   如 62       —— 整数, 1-based
        """
        resolved: List[int] = []
        lowered = {str(h).strip().lower(): i + 1 for i, h in enumerate(headers)}
        for sel in selectors:
            if isinstance(sel, bool):
                raise ValueError(f"列选择器不支持布尔值: {sel!r}")
            if isinstance(sel, int):
                index = sel
            else:
                text = str(sel).strip()
                index = lowered.get(text.lower())
                if index is None and re.fullmatch(r"[A-Za-z]{1,3}", text):
                    index = cls._letter_to_col_index(text)
                if index is None:
                    raise ValueError(
                        f"列选择器 {sel!r} 既不在表头里也不是合法列字母, "
                        f"可用列名(前 30 个): {headers[:30]}"
                    )
            if index < 1:
                raise ValueError(f"列选择器 {sel!r} 解析出非法列号 {index}")
            if index not in resolved:
                resolved.append(index)
        return resolved

    def upload_excel(
            self,
            file_path: Union[str, Path],
            node_id: str,
            sheet_id: str = "Sheet1",
            local_sheet_name: str = "Sheet1",
            range_address: str = "",
            batch_rows: int = 180,
            clear_before_write: bool = False,
            link_cols: Optional[List[Union[int, str]]] = None,
            trim_tail: bool = False,
            max_retries: int = 3,
    ) -> Dict[str, Any]:
        """读取本地 Excel 文件内容,覆盖粘贴到指定钉钉在线表格中

        与 DingDocTool 的文档节点级上传不同,本方法不创建新的表格文档,
        而是把本地 Excel 指定工作表的数据写入到已有的钉钉在线表格中

        使用 openpyxl 读取本地指定工作表,将每个单元格值转为
        {"type": "text", "text": "..."} 后调用 write_range 写入钉钉表格
        本地为空的单元格会同步设为空字符串,实现真正的覆盖效果

        注意：本方法只传递单元格文本值,不保留本地 Excel 的格式/样式
        如需保留样式,请使用 DingDocTool.upload() / DingDocTool.replace()

        Args:
            file_path: 本地 Excel 文件路径
            node_id: 目标钉钉表格文档 ID 或文档链接 URL
            sheet_id: 目标钉钉表格的工作表 ID 或名称,默认为 "Sheet1"
            local_sheet_name: 本地 Excel 中要读取的工作表名称,默认为 "Sheet1"
            range_address: 写入到钉钉表格的范围,A1 表示法,如 "A1:C3"
                传空字符串时,会根据本地表格的 max_row/max_column 自动计算范围
            batch_rows: 每批最大写入行数,默认 180。超过后钉钉 MCP 会报「未知错误」。
            clear_before_write: 是否按批"先 clear_range(type=all) 再 set_cell_range",
                把目标区域的值与格式一起清掉。代价是该区域原有字号/换行/颜色等格式
                全部丢失,只为了处理残留超链接时请改用 link_cols(更准且不伤格式)。
                详见 write_range() 说明。默认 False。
            link_cols: 需要接管"单元格级超链接"的列,支持列名(匹配本地表头行)、
                列字母(如 "BJ")、1-based 列号,可混用;命中的列在写值时同一次
                set_cell_range 请求里附带 hyperlink 字段。
                实测(临时表读回验证)钉钉 set_cell_range 的 hyperlink 三态语义：
                    不传该字段 = 保留单元格原链接(于是"写新值不改链接",看到 A 点进 B)
                    {"type": "none"} 或 null = 显式清除该格链接
                    {"type": "path", "link": url} = 覆盖为该链接
                本方法按文本推导：http/https 开头 -> 重建为该 URL 的整格链接;
                其余(普通文本/空/裸域名) -> 清除旧链接。只动 hyperlink,
                不动 cellStyles,原有字号/换行等格式保持不变。
                未列出的列一律不传 hyperlink,即原样保留其现有链接。
                列名/列字母解析不到会直接抛 ValueError,不会静默漏清。
            trim_tail: 整表写入成功后,是否再清掉本次行范围之后的残留旧行。
                新数据比钉钉表里的旧数据短时,覆盖写碰不到表尾那几行,会看起来"还剩一批历史数据"。
                只在全部批次写成功后执行,写失败时不会额外删数据。默认 False。
                注意：它会连带清掉写入区域下方同列宽范围内的内容,只有"整表覆盖"场景才该开。
            max_retries: 单批清除/写入/表尾探测失败后的重发次数,默认 3

        Returns:
            write_range 的返回结果;开启 trim_tail 且真的清掉行时多一个
            clearedStaleTailRows 字段(清除的行数)

        Raises:
            ImportError: 未安装 openpyxl
            ValueError: 本地 Excel 中不存在指定工作表,或 link_cols 解析不到对应列
            DingTalkMCPError: 某一批重发耗尽仍失败,详见 write_range()
        """
        if load_workbook is None:
            raise ImportError(
                "读取本地 Excel 需要安装 openpyxl,请执行：pip install openpyxl"
            )

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"本地文件不存在: {file_path}")

        wb = load_workbook(file_path, data_only=True)
        if local_sheet_name not in wb.sheetnames:
            raise ValueError(
                f"本地 Excel 中不存在工作表 '{local_sheet_name}',"
                f"可用工作表：{wb.sheetnames}"
            )

        ws = wb[local_sheet_name]
        cells = []
        for row in ws.iter_rows(
                min_row=1,
                max_row=ws.max_row,
                min_col=1,
                max_col=ws.max_column,
                values_only=True,
        ):
            row_cells = []
            for value in row:
                text = "" if value is None else str(value)
                row_cells.append({"type": "text", "text": text})
            cells.append(row_cells)

        if link_cols and cells:
            headers = [cell.get("text", "") for cell in cells[0]]
            indexes = self._resolve_col_indexes(headers, link_cols)
            for row in cells:
                for col_index in indexes:
                    if col_index <= len(row):
                        cell = row[col_index - 1]
                        cell["hyperlink"] = self._cell_hyperlink(cell.get("text", ""))

        result = self.write_range(
            node_id=node_id,
            sheet_id=sheet_id,
            range_address=range_address,
            cells=cells,
            batch_rows=batch_rows,
            clear_before_write=clear_before_write,
            max_retries=max_retries,
        )

        # 写成功才清表尾: 若上面抛错, 表格保持"已写批次 + 未写批次"的原状, 不额外删数据
        if trim_tail and cells:
            start_row, start_col, _, _ = (
                self._parse_range(range_address) if range_address else (1, 1, None, None)
            )
            total_rows = len(cells)
            total_cols = max(len(row) for row in cells)
            cleared = self.clear_stale_tail(
                node_id=node_id,
                sheet_id=sheet_id,
                after_row=start_row + total_rows - 1,
                total_cols=start_col + total_cols - 1,
                max_retries=max_retries,
            )
            if cleared:
                result["clearedStaleTailRows"] = cleared
        return result

    def read_all_rows(
            self,
            node_id: str,
            sheet_id: Optional[str] = None,
    ) -> List[List[str]]:
        """读取钉钉在线表格的所有行数据,返回二维字符串数组

        钉钉表格 MCP 的 get_range_as_csv / get_cell_infos 对单次返回数据量有限制,
        大表格无法直接一次性读取本方法通过 submit_export_job 将表格导出为 xlsx,
        下载到本地临时文件后解析,适合完整读取大表格

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表名称(可选,默认第一个工作表)

        Returns:
            二维字符串数组,每个元素为单元格的字符串值
        """
        if load_workbook is None:
            raise ImportError(
                "read_all_rows 需要 openpyxl,请执行：pip install openpyxl"
            )

        print(f"[DingExcelTool] Exporting table '{node_id}' to xlsx ...")
        job = self.mcp.call_tool(
            "submit_export_job", nodeId=node_id, exportFormat="xlsx"
        )
        if not job.get("success"):
            raise RuntimeError(f"提交导出任务失败: {job}")

        job_id = job["jobId"]
        download_url = None
        for attempt in range(40):
            result = self.mcp.call_tool("query_export_job", jobId=job_id)
            if result.get("status") == "success" and result.get("downloadUrl"):
                download_url = result["downloadUrl"]
                break
            time.sleep(3)
        if not download_url:
            raise TimeoutError("导出任务超时,未获取到下载链接")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            print(f"[DingExcelTool] Downloading to temporary file ...")
            urllib.request.urlretrieve(download_url, tmp_path)

            wb = load_workbook(tmp_path, data_only=True)
            ws_name = sheet_id or wb.sheetnames[0]
            if ws_name not in wb.sheetnames:
                raise ValueError(f"工作表 '{ws_name}' 不存在,可用：{wb.sheetnames}")
            ws = wb[ws_name]

            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append(["" if v is None else str(v) for v in row])
            print(f"[DingExcelTool] Read {len(rows)} row(s)")
            return rows
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def append_rows(
            self,
            node_id: str,
            sheet_id: str,
            values: List[List[str]],
    ) -> Dict[str, Any]:
        """在钉钉在线表格指定工作表末尾追加若干行

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称
            values: 二维字符串数组,每行是一个一维数组

        Returns:
            append_rows 的原始返回结果,通常包含追加的范围信息
        """
        return self.mcp.call_tool(
            "append_rows",
            nodeId=node_id,
            sheetId=sheet_id,
            values=values,
        )

    def clear_range(
            self,
            node_id: str,
            sheet_id: str,
            range_str: str,
            clear_type: str = "content",
    ) -> Dict[str, Any]:
        """清除钉钉在线表格指定范围的单元格内容或格式

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称
            range_str: 清除范围,A1 表示法
            clear_type: 清除类型：content(默认值,仅清除值)、format、all

        Returns:
            clear_range 的原始返回结果
        """
        return self.mcp.call_tool(
            "clear_range",
            nodeId=node_id,
            sheetId=sheet_id,
            range=range_str,
            type=clear_type,
        )

    def delete_sheet(self, node_id: str, sheet_id: str) -> Dict[str, Any]:
        """删除钉钉在线表格中的指定工作表

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称

        Returns:
            delete_sheet 的原始返回结果
        """
        return self.mcp.call_tool(
            "delete_sheet",
            nodeId=node_id,
            sheetId=sheet_id,
        )

    def _get_column_mapping(
            self,
            node_id: str,
            sheet_id: str,
            header_row: int = 1,
    ) -> Dict[str, str]:
        """读取表头行，建立列名到列字母的映射

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称
            header_row: 表头行号，默认 1

        Returns:
            {列名: 列字母} 的映射字典，如 {"序列号": "A", "question": "C", ...}
        """
        # 读取表头行，范围 A 到 ZZ（支持最多 702 列）
        range_str = f"A{header_row}:ZZ{header_row}"
        result = self.mcp.call_tool(
            "get_range",
            nodeId=node_id,
            sheetId=sheet_id,
            range=range_str,
        )

        mapping = {}
        display_values = result.get("displayValues", [[]])
        if display_values:
            for col_idx, col_name in enumerate(display_values[0], start=1):
                if col_name:  # 跳过空单元格
                    col_letter = self._col_index_to_letter(col_idx)
                    mapping[col_name] = col_letter
        return mapping

    def update_cell_by_condition(
            self,
            node_id: str,
            sheet_id: str,
            conditions: Dict[str, Union[str, int, float, bool]],
            target_columns: Dict[str, str],
            match_mode: str = "exact",
            max_matches: int = 0,
            header_row: int = 1,
    ) -> Dict[str, Any]:
        """根据多条件匹配行，并修改匹配行的多个目标列

        支持多条件过滤（AND 逻辑）和多目标列同时修改。条件列或目标列不存在时
        跳过该列，不报错。

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称
            conditions: 条件字典，{列名: 条件值}。所有条件必须同时满足（AND 逻辑）
                条件值支持字符串/数字/布尔，统一转字符串后比较
            target_columns: 目标列字典，{列名: 新值}。支持多列同时修改
            match_mode: 匹配模式
                - exact: 精确匹配（默认）
                - contains: 包含匹配
                - startswith: 开头匹配
                - regex: 正则表达式匹配
            max_matches: 最多修改行数，0 表示不限制
            header_row: 表头行号，默认 1

        Returns:
            {
                "success": True,
                "matched_rows": [23, 45, 67],  # 实际修改的行号列表
                "total_matched": 5,  # 总共匹配到的行数
                "total_modified": 3,  # 实际修改的行数
                "skipped_columns": ["不存在的列"],  # 跳过的目标列名列表
                "skipped_conditions": ["不存在的条件列"],  # 跳过的条件列名列表
                "message": "Successfully updated 3 rows"
            }

        Example:
            tool = DingExcelTool()
            result = tool.update_cell_by_condition(
                node_id="<node_id>",  # 表格文档 ID 或文档链接 URL
                sheet_id="Sheet1",
                conditions={"question": "示例问题", "is_evaluated": "false"},
                target_columns={"updatedat": "2026-10-09", "remark": "已修复"},
                match_mode="contains",
                max_matches=5,
            )
        """
        import re

        result = {
            "success": True,
            "matched_rows": [],
            "total_matched": 0,
            "total_modified": 0,
            "skipped_columns": [],
            "skipped_conditions": [],
            "message": "",
        }

        # 1. 读取表头，建立列名到列字母的映射
        col_mapping = self._get_column_mapping(node_id, sheet_id, header_row)
        print(f"[DingExcelTool] 读取到 {len(col_mapping)} 个列名")

        # 2. 解析条件列，跳过不存在的列
        condition_cols = {}  # {列字母: (列名, 条件值字符串)}
        for col_name, cond_value in conditions.items():
            if col_name in col_mapping:
                col_letter = col_mapping[col_name]
                # 统一转字符串比较
                cond_str = str(cond_value)
                condition_cols[col_letter] = (col_name, cond_str)
            else:
                result["skipped_conditions"].append(col_name)
                print(f"[DingExcelTool] 警告：条件列 '{col_name}' 不存在，已跳过")

        if not condition_cols:
            result["message"] = "所有条件列都不存在，无法匹配"
            return result

        # 3. 解析目标列，跳过不存在的列
        target_cols = {}  # {列字母: (列名, 新值)}
        for col_name, new_value in target_columns.items():
            if col_name in col_mapping:
                col_letter = col_mapping[col_name]
                target_cols[col_letter] = (col_name, new_value)
            else:
                result["skipped_columns"].append(col_name)
                print(f"[DingExcelTool] 警告：目标列 '{col_name}' 不存在，已跳过")

        if not target_cols:
            result["message"] = "所有目标列都不存在，无需修改"
            return result

        # 4. 读取表格数据（使用 read_all_rows 导出 xlsx 方式，避免 2MB 限制）
        try:
            all_data = self.read_all_rows(node_id, sheet_id)
            # 跳过表头行，建立 (行号, 行数据) 的列表
            all_rows = []
            for row_idx, row_data in enumerate(all_data[header_row:], start=header_row + 1):
                all_rows.append((row_idx, row_data))
        except Exception as e:
            print(f"[DingExcelTool] 读取数据出错：{e}")
            all_rows = []

        print(f"[DingExcelTool] 读取到 {len(all_rows)} 行数据")

        # 5. 匹配行
        matched_row_numbers = []
        for row_number, row_data in all_rows:
            # 检查所有条件是否都满足
            all_match = True
            for col_letter, (col_name, cond_str) in condition_cols.items():
                col_idx = self._letter_to_col_index(col_letter) - 1
                cell_value = ""
                if col_idx < len(row_data):
                    cell_value = str(row_data[col_idx]) if row_data[col_idx] is not None else ""

                # 按 match_mode 比较
                if match_mode == "exact":
                    if cell_value != cond_str:
                        all_match = False
                        break
                elif match_mode == "contains":
                    if cond_str not in cell_value:
                        all_match = False
                        break
                elif match_mode == "startswith":
                    if not cell_value.startswith(cond_str):
                        all_match = False
                        break
                elif match_mode == "regex":
                    if not re.search(cond_str, cell_value):
                        all_match = False
                        break
                else:
                    raise ValueError(f"不支持的 match_mode: {match_mode}")

            if all_match:
                matched_row_numbers.append(row_number)
                result["total_matched"] += 1

                # 检查是否达到 max_matches 限制
                if max_matches > 0 and result["total_matched"] >= max_matches:
                    break

        print(f"[DingExcelTool] 匹配到 {len(matched_row_numbers)} 行")

        # 6. 写入新值
        for row_number in matched_row_numbers:
            for col_letter, (col_name, new_value) in target_cols.items():
                range_str = f"{col_letter}{row_number}"
                try:
                    self.mcp.call_tool(
                        "update_range",
                        nodeId=node_id,
                        sheetId=sheet_id,
                        rangeAddress=range_str,
                        values=[[new_value]],
                    )
                    result["total_modified"] += 1
                except Exception as e:
                    print(f"[DingExcelTool] 写入 {range_str} 出错：{e}")

            result["matched_rows"].append(row_number)

        result["message"] = f"Successfully updated {len(result['matched_rows'])} rows"
        return result


if __name__ == "__main__":
    # 示例用法：请确保已配置 DINGTALK_TABLE_MCP_URL 环境变量
    dot_env_path = ''
    tool = DingExcelTool(dotenv_path=dot_env_path)
    result = tool.create_sheet("测试表格")
    print(result)
