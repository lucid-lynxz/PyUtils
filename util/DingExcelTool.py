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

    # 3. 写入数据
    tool.write_range(
        node_id,
        sheet_id,
        "A1:B2",
        [
            [{"type": "text", "text": "姓名"}, {"type": "text", "text": "年龄"}],
            [{"type": "text", "text": "张三"}, {"type": "text", "text": "18"}],
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
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
    def _cells_to_range(cells: List[List[Any]]) -> str:
        """根据 cells 二维数组的行/列数生成 A1 表示法范围,如 A1:C3"""
        if not cells:
            return "A1"
        rows = len(cells)
        cols = max(len(row) for row in cells) if cells else 0
        return f"A1:{DingExcelTool._col_index_to_letter(cols)}{rows}"

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

    def write_range(
        self,
        node_id: str,
        sheet_id: str = "Sheet1",
        range_address: str = "",
        cells: Optional[List[List[Dict[str, Any]]]] = None,
        batch_rows: int = 180,
    ) -> Dict[str, Any]:
        """向钉钉在线表格指定区域写入单元格内容

        当 cells 行数超过 batch_rows 时,会自动分批调用 set_cell_range,
        避免单次请求体过大导致钉钉 MCP 返回「未知错误」。

        Args:
            node_id: 表格文档 ID 或文档链接 URL
            sheet_id: 工作表 ID 或名称,默认为 "Sheet1"
            range_address: 写入范围,A1 表示法,如 "A1:C3"
                传空字符串时,会根据 cells 的维度自动计算范围
            cells: 二维数组,每个元素为单元格对象,例如 {"type": "text", "text": "值"}
                可传入 {} 表示跳过该单元格
            batch_rows: 每批最大写入行数。实测 94 列表格约 180 行安全,
                超过后 set_cell_range 会报「未知错误」。

        Returns:
            最后一批 set_cell_range 的返回结果；全部成功时 overall success 为 True。
        """
        if cells is None:
            raise ValueError("cells 参数不能为空")

        total_rows = len(cells)
        if total_rows == 0:
            return {"success": True, "message": "无数据需要写入"}

        cols = max(len(row) for row in cells) if cells else 0
        col_letter = self._col_index_to_letter(cols)

        last_result: Dict[str, Any] = {"success": True}
        for start in range(0, total_rows, batch_rows):
            end = min(start + batch_rows, total_rows)
            batch = cells[start:end]
            batch_range = f"A{start + 1}:{col_letter}{end}"
            print(f"[DingExcelTool] 写入第 {start + 1}-{end} 行, 范围 {batch_range}")
            result = self.mcp.call_tool(
                "set_cell_range",
                nodeId=node_id,
                sheetId=sheet_id,
                rangeAddress=batch_range,
                cells=batch,
            )
            if not result.get("success"):
                return result
            last_result = result

        return {
            **last_result,
            "success": True,
            "message": f"Successfully updated {total_rows} rows in batches.",
            "totalRows": total_rows,
            "batchRows": batch_rows,
        }

    def upload_excel(
        self,
        file_path: Union[str, Path],
        node_id: str,
        sheet_id: str = "Sheet1",
        local_sheet_name: str = "Sheet1",
        range_address: str = "",
        batch_rows: int = 180,
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

        Returns:
            set_cell_range 的原始返回结果

        Raises:
            ImportError: 未安装 openpyxl
            ValueError: 本地 Excel 中不存在指定工作表
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

        return self.write_range(
            node_id=node_id,
            sheet_id=sheet_id,
            range_address=range_address,
            cells=cells,
            batch_rows=batch_rows,
        )

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


if __name__ == "__main__":
    # 示例用法：请确保已配置 DINGTALK_TABLE_MCP_URL 环境变量
    tool = DingExcelTool()
    result = tool.create_sheet("测试表格")
    print(result)
