#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉文档工具类（独立 MCP 客户端版）

基于 dingtalk-doc-rw skill 改造，直接通过钉钉 MCP HTTP 网关调用文档节点级操作
支持通过构造函数、环境变量或 .env 文件配置 MCP 授权地址

注意：本类处理钉钉文档/文件的节点级与内容级操作；
如需表格级操作（读写单元格、工作表），请使用独立的 `util.DingExcelTool.DingExcelTool`

首次使用申请 MCP 授权：
    https://mcp.dingtalk.com/#/detail?mcpId=9629&detailType=marketMcpDetail
    进入页面后，在右侧「使用 MCP」区域复制 StreamableHttp URL
    （格式类似 https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>）

支持的操作及对应方法：
    - 删除指定 node_id 的表格/文件
        tool.delete_by_node_id(node_id)
    - 按文件名删除表格（通过 search_documents 搜索匹配）
        tool.delete_by_name(name)
    - 检测指定 node_id 的文档是否存在
        tool.exists(node_id)
    - 上传本地 Excel 并转为钉钉在线表格
        tool.upload(file_path, name=None)
    - 删除同名旧表格后上传新文件（最常用）
        tool.replace(file_path, name=None)
    - 批量上传目录下匹配正则的文件
        tool.upload_directory(directory, pattern=".*")
    - 上传时自动设置 Excel 样式（冻结/筛选/换行/字体等）
        tool.replace(file_path, style_options={...})

    文档节点与内容管理：
    - 读取文档 Markdown 内容
        tool.get_document_content(node_id)
    - 编辑/追加文档 Markdown 内容
        tool.update_document(node_id, markdown, mode="overwrite")
    - 创建新文档
        tool.create_document(name, markdown=None)
    - 创建文件夹
        tool.create_folder(name)
    - 搜索文档
        tool.search_documents(keyword)
    - 复制/移动/重命名节点
        tool.copy_document(node_id, target_folder_id)
        tool.move_document(node_id, target_folder_id)
        tool.rename_document(node_id, new_name)

    文档 Block 级精确编辑：
    - 查询一级块元素列表
        tool.list_document_blocks(node_id)
    - 插入块元素
        tool.insert_document_block(node_id, element)
    - 更新块元素
        tool.update_document_block(node_id, block_id, element=element)
    - 删除块元素
        tool.delete_document_block(node_id, block_id)

.env / 环境变量支持的 key-value：
    # 方式一：单条授权 URL（最常用）
    DINGTALK_DOC_MCP_URL=https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>

    # 方式二：多条服务器配置 JSON（跨组织/容灾）
    DINGTALK_DOC_MCP_SERVERS=[{"base_url":"...","server_id":"...","key":"..."}]

    # 兼容旧变量名（仍可用但不推荐）
    DINGTALK_MCP_URL=...
    DINGTALK_MCP_SERVERS=...

简单调用示例：
    from util.DingDocTool import DingDocTool

    # 从 .env / 环境变量读取 DINGTALK_DOC_MCP_URL
    tool = DingDocTool("<folder-node-id>")
    result = tool.replace("/path/to/local.xlsx")
    print(result["url"])

如需表格级操作（读写单元格/工作表），请使用独立的 `util.DingExcelTool.DingExcelTool`
"""

import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

from util.DingTalkMCPClient import DEFAULT_MCP_TIMEOUT, DingTalkMCPClient


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


# 模块导入时默认加载当前文件所在目录的 .env（若存在）
_load_dotenv()


class DingDocTool:
    """钉钉文档节点级操作工具

    常用流程：
        tool = DingDocTool(
            "<folder-node-id>",
            mcp_url="https://mcp-gw.dingtalk.com/server/<server_id>?key=<key>"
        )
        result = tool.replace("/path/to/local.xlsx")
        print(result["url"])
    """

    def __init__(
            self,
            folder_node_id: str,
            mcp_url: Optional[str] = None,
            mcp_servers: Optional[List[Dict[str, Any]]] = None,
            dotenv_path: Optional[Union[str, Path]] = None,
            timeout: int = DEFAULT_MCP_TIMEOUT,
    ):
        """
        Args:
            folder_node_id: 钉钉目录（文件夹）的节点 ID
                从钉钉文档链接 `https://alidocs.dingtalk.com/i/nodes/<node_id>`
                中拷贝 <node_id> 部分即可工具后续会把 Excel 上传到这个目录里
            mcp_url: 钉钉文档 MCP 授权地址（单条）
                格式：`https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>`
                如果传了该参数，会优先使用；不传则尝试环境变量 / .env 文件
            mcp_servers: 多条钉钉文档 MCP 服务器配置（可选）
                用于跨组织场景或需要自动容灾切换时传入，例如：
                `[{"base_url": "...", "server_id": "...", "key": "..."}]`
                与 mcp_url 二选一即可
            dotenv_path: 指定要加载的 .env 文件路径（可选）
                为 None 时已在模块导入时加载当前文件所在目录的 .env；
                传入具体路径时额外加载该 .env；传空字符串则不加载任何 .env
            timeout: MCP 接口调用超时时间，单位秒，默认 60 秒
        """
        if dotenv_path is not None:
            _load_dotenv(dotenv_path)

        self.folder_node_id = folder_node_id

        # 优先使用新的文档 MCP 环境变量名，兼容旧的 DINGTALK_MCP_URL/SERVERS
        mcp_url = (
                mcp_url
                or os.getenv("DINGTALK_DOC_MCP_URL")
                or os.getenv("DINGTALK_MCP_URL")
        )
        if not mcp_servers:
            doc_servers_env = os.getenv("DINGTALK_DOC_MCP_SERVERS")
            legacy_servers_env = os.getenv("DINGTALK_MCP_SERVERS")
            if doc_servers_env:
                mcp_servers = json.loads(doc_servers_env)
            elif legacy_servers_env:
                mcp_servers = json.loads(legacy_servers_env)

        self.mcp = DingTalkMCPClient(
            mcp_url=mcp_url, mcp_servers=mcp_servers, timeout=timeout
        )

        folder_info = self.get_document_info(folder_node_id)
        if not folder_info.get("success"):
            raise RuntimeError(f"无法访问钉钉目录: {folder_info}")

        self.workspace_id = folder_info.get("workspaceId")
        # 当目标节点本身就是 folder 时，应使用它自己的 nodeId 作为 folder_id；
        # get_document_info 返回的 folderId 在某些场景下可能是父目录 ID
        if folder_info.get("nodeType") == "folder":
            self.folder_id = folder_node_id
        else:
            self.folder_id = (
                    folder_info.get("folderId")
                    or folder_info.get("nodeId")
                    or folder_node_id
            )

    def _upload_to_oss(self, file_path: Path, upload_info: Dict[str, Any]) -> bool:
        """使用 curl 上传文件到 OSS"""
        headers = upload_info["headers"]
        url = upload_info["resourceUrl"]
        cmd = [
            "curl",
            "-s",
            "-X", "PUT",
            url,
            "-H", f"x-oss-date: {headers['x-oss-date']}",
            "-H", f"Authorization: {headers['Authorization']}",
            "--upload-file", str(file_path),
            "--max-time", "300",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=310)
            return result.returncode == 0
        except Exception as e:
            print(f"[ERROR] curl 上传异常: {e}")
            return False

    def search_nodes_by_name(
            self,
            name: str,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
            allow_global: bool = False,
    ) -> List[Dict[str, Any]]:
        """按名称搜索节点
        可能不准, 若需要精确搜索某个目录下的文件, 建议改用: search_in_folder() 方法

        默认只在当前目录所属的工作空间（self.workspace_id）内搜索，避免把
        "我的文档"个人空间或其他知识库中的同名文件误匹配进来

        Args:
            name: 要搜索的文件名
            folder_id: 指定搜索的文件夹 ID未指定时默认使用构造时传入的 folder_node_id
            workspace_id: 指定搜索的工作空间 ID未指定时使用 self.workspace_id
            allow_global: 是否允许全局跨空间搜索默认 False，优先保证精确性

        Returns:
            匹配到的节点列表search_documents 失败时返回空列表并打印 WARN
        """
        if not workspace_id:
            workspace_id = self.get_workspace_id(folder_id)

        target_workspace = workspace_id if workspace_id is not None else self.workspace_id
        print(f'search_nodes_by_name target_workspace={target_workspace}')
        kwargs: Dict[str, Any] = {"keyword": name, "page_size": 50}
        if target_workspace and not allow_global:
            kwargs["workspaceIds"] = [target_workspace]

        try:
            result = self.mcp.call_tool("search_documents", **kwargs)
            if result.get("success"):
                matches = []
                for doc in result.get("documents", []):
                    doc_name = doc.get("name", "")
                    if doc_name == name or doc_name.startswith(name + "("):
                        matches.append(doc)
                return matches
        except Exception as e:
            print(f"[WARN] search_documents 失败: {e}")
        return []

    def search_in_folder(self, name: str, folder_id: Optional[str] = None, ) -> List[Dict[str, Any]]:
        """在指定目录下按名称搜索节点（本地精确过滤）

        由于 search_documents 不支持按 folder_id 精确过滤，本方法先通过
        list_all_nodes 拉取目录下全部节点，再在本地按名称匹配适用于需要
        严格限定"某个目录内"查找文件的场景，避免跨 workspace / 个人空间误匹配

        Args:
            name: 要搜索的文件名
            folder_id: 目标目录节点 ID未指定时使用 self.folder_node_id

        Returns:
            匹配到的节点列表, 元素示例:
            {
                "contentType": "ALIDOC",
                "hasChildren": "False",
                "updateTime": 1760734430000,
                "extension": "axls",
                "createTime": 1760734430000,
                "nodeType": "file",
                "nodeId": "xxx",
                "workspaceId": "yyy",
                "docUrl": "https://alidocs.dingtalk.com/i/nodes/xxx?utm_scene=team_space",
                "name": "xxx"
            }
        """
        target = folder_id or self.folder_node_id
        all_nodes = self.list_all_nodes(folder_id=target)
        matches = []
        for node in all_nodes:
            node_name = node.get("name", "")
            if node_name == name or node_name.startswith(name + "("):
                matches.append(node)
        return matches

    def list_nodes(
            self,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
            page_size: int = 50,
            page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列举指定文件夹或工作空间下的节点

        Args:
            folder_id: 文件夹节点 ID未指定时默认使用构造时传入的 folder_node_id
                注意：当 nodeType 为 folder 时，应使用节点自身的 nodeId，而非
                get_document_info 返回的 folderId（后者是父目录 ID）
            workspace_id: 工作空间 ID与 folder_id 二选一，优先级低于 folder_id
            page_size: 每页返回数量，list_nodes 接口实测最大支持 50，超过会报错
            page_token: 分页 token，用于获取下一页

        Returns:
            list_nodes 接口的原始返回结果，通常包含 nodes / hasMore / nextPageToken
            其中 nodes 是个列表, 元素示例:         
            {
                "nodeId": "xxx",
                "contentType": "ALIDOC",
                "extension": "axls",
                "createTime": 1760734589000,
                "hasChildren": "False",
                "nodeType": "file",
                "docUrl": "https://alidocs.dingtalk.com/i/nodes/xxx?utm_scene=team_space",
                "updateTime": 1760734589000,
                "workspaceId": "yyy",
                "name": "xxx"
            }
            调用失败时返回 {"success": False, "nodes": []}
        """
        target = folder_id or self.folder_node_id
        try:
            return self.mcp.call_tool(
                "list_nodes",
                folderId=target,
                workspaceId=workspace_id,
                pageSize=page_size,
                pageToken=page_token,
            )
        except Exception as e:
            print(f"[WARN] list_nodes 失败: {e}")
            return {"success": False, "nodes": []}

    def list_all_nodes(
            self,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
            page_size: int = 50,
    ) -> List[Dict[str, Any]]:
        """自动分页列举指定目录或工作空间下的全部节点

        Args:
            folder_id: 文件夹节点 ID未指定时默认使用构造时传入的 folder_node_id
            workspace_id: 工作空间 ID与 folder_id 二选一
            page_size: 每页返回数量，默认 50（接口最大值）

        Returns:
            节点信息列表
        """
        target = folder_id or self.folder_node_id
        all_nodes: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            result = self.list_nodes(
                folder_id=target,
                workspace_id=workspace_id,
                page_size=page_size,
                page_token=page_token,
            )
            if not result.get("success"):
                break
            nodes = result.get("nodes", [])
            all_nodes.extend(nodes)
            if not result.get("hasMore"):
                break
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return all_nodes

    def delete_by_node_id(self, node_id: str) -> bool:
        """根据 node_id 删除节点"""
        try:
            res = self.mcp.call_tool("delete_document", nodeId=node_id)
            if res.get("success"):
                return True
            print(f"[WARN] delete_document 返回失败: {res}")
        except Exception as e:
            print(f"[WARN] 删除节点 {node_id} 失败: {e}")
        return False

    def delete_by_name(self, name: str) -> int:
        """根据文件名删除匹配的表格，返回删除数量

        通过 search_documents 全局搜索匹配名称的节点后删除当前 MCP 授权下
        search_documents 可能失败，调用方应做好失败兜底

        Args:
            name: 普通字符串文件名匹配精确名称或 "name(数字)" 的重复命名
        """
        deleted = 0
        nodes = self.search_nodes_by_name(name)

        for node in nodes:
            node_id = node.get("nodeId")
            if node_id and self.delete_by_node_id(node_id):
                deleted += 1
                print(f"[DingDocTool] Deleted '{node.get('name')}' ({node_id})")
        return deleted

    def exists(self, node_id: str) -> bool:
        """检测指定 node_id 的文档/文件是否存在

        Args:
            node_id: 要检测的文档节点 ID 或文档链接 URL

        Returns:
            存在且可访问返回 True，否则返回 False
        """
        if not node_id:
            return False

        try:
            _result = self.get_document_info(node_id)
            return bool(_result.get("success"))
        except Exception as e:
            print(f"[WARN] 检测节点 {node_id} 是否存在失败: {e}")
        return False

    @staticmethod
    def apply_style(
            file_path: Union[str, Path],
            style_options: Optional[Dict[str, Any]] = None,
            output_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """对本地 Excel 应用样式后另存，返回处理后的文件路径

        需要安装 openpyxl如果 style_options 为空或 None，直接返回原路径

        Args:
            file_path: 原始 Excel 路径
            style_options: 样式配置字典，可包含以下 key：
                - freeze_panes: 冻结窗格坐标，例如 "D2"；默认不冻结
                - auto_filter: 是否开启自动筛选；默认 False
                - wrap_text_columns: 需要自动换行的列名列表（按首行标题匹配）
                - column_widths: 列宽配置字典 {列名: 宽度},按首行标题匹配
                - default_column_width: 其余未显式指定列宽的列统一使用的默认宽度, 不传则保持原列宽不变
                - font_name: 字体名称，默认 "默认"（表示不强制指定字体）
                - font_size: 字号，默认 11
                - vertical: 垂直对齐方式，默认 "center"（垂直居中）
            output_path: 输出路径，默认在原文件名后加 .styled 后缀

        Returns:
            处理后的文件路径（可能与输入相同）
        """
        file_path = Path(file_path)
        style_options = style_options or {}
        if not style_options:
            return file_path

        if load_workbook is None:
            raise RuntimeError(
                "设置 Excel 样式需要 openpyxl，请安装：pip install openpyxl"
            )

        from openpyxl.styles import Alignment, Font

        freeze_panes = style_options.get("freeze_panes")
        auto_filter = style_options.get("auto_filter", False)
        wrap_text_columns = style_options.get("wrap_text_columns") or []
        column_widths = style_options.get("column_widths") or {}
        default_column_width = style_options.get("default_column_width")
        font_name = style_options.get("font_name", "默认")
        font_size = style_options.get("font_size", 11)
        vertical = style_options.get("vertical", "center")

        wb = load_workbook(file_path)
        ws = wb.active

        # 冻结窗格
        if freeze_panes:
            ws.freeze_panes = freeze_panes

        # 自动筛选
        if auto_filter:
            ws.auto_filter.ref = ws.dimensions

        # 按首行标题建立列名 -> 列索引映射
        header_map = {}
        if ws.max_row > 0:
            for col_idx, cell in enumerate(ws[1], start=1):
                if cell.value is not None:
                    header_map[str(cell.value)] = col_idx

        def resolve_col_indices(column_names):
            indices = []
            for col_name in column_names:
                idx = header_map.get(col_name)
                if idx is None:
                    # print(f"[WARN] 未找到列 '{col_name}'，跳过样式设置")
                    continue
                indices.append(idx)
            return indices

        wrap_cols = resolve_col_indices(wrap_text_columns)

        def clone_alignment(src, **overrides):
            """复制 Alignment 对象并覆盖指定属性，避免使用 IDE 无法识别的 copy()"""
            # openpyxl Alignment 构造函数使用 camelCase 参数名
            kw = {
                "horizontal": src.horizontal,
                "vertical": src.vertical,
                "textRotation": src.textRotation,
                "wrapText": src.wrapText,
                "shrinkToFit": src.shrinkToFit,
                "indent": src.indent,
                "relativeIndent": src.relativeIndent,
                "justifyLastLine": src.justifyLastLine,
                "readingOrder": src.readingOrder,
            }
            kw.update(overrides)
            return Alignment(**kw)

        # 全表应用字体与垂直对齐
        font_kw = {"size": font_size}
        if font_name and font_name != "默认":
            font_kw["name"] = font_name
        default_font = Font(**font_kw)

        for row in ws.iter_rows():
            for cell in row:
                cell.font = default_font
                if cell.alignment:
                    cell.alignment = clone_alignment(cell.alignment, vertical=vertical)
                else:
                    cell.alignment = Alignment(vertical=vertical)

        def set_alignment(cols, wrap_text=None, shrink_to_fit=None):
            """按列索引批量设置 alignment 属性，None 表示不修改该属性"""
            for row in ws.iter_rows():
                for col_idx in cols:
                    cell = row[col_idx - 1]
                    if cell.alignment:
                        cell.alignment = clone_alignment(
                            cell.alignment,
                            wrap_text=wrap_text,
                            shrink_to_fit=shrink_to_fit,
                        )
                    else:
                        cell.alignment = Alignment(
                            wrap_text=wrap_text,
                            shrink_to_fit=shrink_to_fit,
                            vertical=vertical,
                        )

        # 自动换行
        if wrap_cols:
            set_alignment(wrap_cols, wrap_text=True, shrink_to_fit=False)

        # 设置列宽：先应用 column_widths 中显式指定的列，再为其余列套默认宽度
        if column_widths or default_column_width:
            from openpyxl.utils import get_column_letter

            explicit_letters = set()
            for col_name, width in column_widths.items():
                idx = header_map.get(col_name)
                if idx is None:
                    # print(f"[WARN] 未找到列 '{col_name}'，跳过列宽设置")
                    continue
                letter = get_column_letter(idx)
                ws.column_dimensions[letter].width = width
                explicit_letters.add(letter)

            if default_column_width:
                for col_idx in range(1, ws.max_column + 1):
                    letter = get_column_letter(col_idx)
                    if letter in explicit_letters:
                        continue
                    dim = ws.column_dimensions.get(letter)
                    if dim is None or dim.width is None:
                        ws.column_dimensions[letter].width = default_column_width

        if output_path:
            out_path = Path(output_path)
        else:
            out_path = file_path.parent / (file_path.stem + ".styled" + file_path.suffix)
        wb.save(out_path)
        return Path(out_path)

    def upload(
            self,
            file_path: Union[str, Path],
            name: Optional[str] = None,
            style_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """上传本地 Excel 到钉钉目录并转为在线表格

        Args:
            file_path: 本地 Excel 路径
            name: 上传后在钉钉中显示的表格名称，默认使用文件 stem
            style_options: 样式配置字典，详见 apply_style() 文档

        Returns:
            {"success": True, "node_id": ..., "name": ..., "url": ...}
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        desired_name = name or file_path.stem

        # 如有样式参数，先处理 Excel
        styled_path = self.apply_style(file_path, style_options=style_options)
        file_size = styled_path.stat().st_size

        upload_info = self.mcp.call_tool(
            "get_file_upload_info", workspaceId=self.workspace_id
        )
        if not upload_info.get("success"):
            raise RuntimeError(f"获取上传信息失败: {upload_info}")

        print(f"[DingDocTool] Uploading '{desired_name}.xlsx' ({file_size:,} bytes) ...")
        if not self._upload_to_oss(styled_path, upload_info):
            raise RuntimeError("OSS 文件上传失败")

        commit = self.mcp.call_tool(
            "commit_uploaded_file",
            uploadKey=upload_info["uploadKey"],
            name=desired_name + ".xlsx",
            fileSize=file_size,
            folderId=self.folder_id,
            workspaceId=self.workspace_id,
            convertToOnlineDoc=True,
        )
        if not commit.get("success"):
            raise RuntimeError(f"提交在线表格失败: {commit}")

        node_id = commit["nodeId"]
        created_name = commit.get("name", "")
        print(f"[DingDocTool] Created online table: {node_id} (initial name: {created_name})")

        doc_url = f'https://alidocs.dingtalk.com/i/nodes/{node_id}'
        print(f"[DingDocTool] Online table URL: {doc_url}")

        # 必要时重命名
        try:
            if created_name != desired_name and name is not None:
                renamed = False
                for attempt in range(3):
                    try:
                        self.mcp.call_tool("rename_document", nodeId=node_id, newName=desired_name)
                        print(f"[DingDocTool] Renamed to '{desired_name}'")
                        renamed = True
                        break
                    except Exception as e:
                        print(f"[WARN] 重命名 attempt {attempt + 1} 失败: {e}")
                        time.sleep(5)
                if not renamed:
                    print(f"[WARN] 未能重命名，表格仍显示为 '{created_name}'")
        except Exception as e:
            print(f"[WARN] 重命名失败: {e}")

        try:
            info = self.get_document_info(node_id)
            doc_url = info.get("docUrl", doc_url)
        except Exception as e:
            print(f"[WARN] 获取文档信息失败: {e}")

        return {
            "success": True,
            "node_id": node_id,
            "name": desired_name,
            "url": doc_url,
            "styled_path": '' if (style_options is None or len(style_options) == 0) else str(styled_path),
        }

    def replace(
            self,
            file_path: Union[str, Path],
            name: Optional[str] = None,
            style_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """删除同名的现有表格，然后上传新文件

        这是最常用的「清空旧内容并替换为新文件」流程

        Args:
            file_path: 本地 Excel 路径
            name: 上传后在钉钉中显示的表格名称，默认使用文件stem
            style_options: 样式配置字典，详见 apply_style() 文档
        """
        file_path = Path(file_path)
        desired_name = name or file_path.stem

        print(f"[DingDocTool] Replacing '{desired_name}' ...")
        deleted = self.delete_by_name(desired_name)
        if deleted:
            print(f"[DingDocTool] Deleted {deleted} existing node(s), wait for settle ...")
            time.sleep(5)
        else:
            print(f"[DingDocTool] No existing node named '{desired_name}' found or lookup failed.")

        return self.upload(file_path, desired_name, style_options=style_options)

    def upload_directory(
            self,
            directory: Union[str, Path],
            pattern: str = ".*",
            style_options: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """批量上传目录下匹配正则表达式的文件

        只遍历指定目录下的直接文件（不递归子目录），对每个匹配文件调用 replace()

        Args:
            directory: 本地目录路径
            pattern: 用于匹配文件名的正则表达式，默认 ".*" 表示任意文件名
                示例：r"query_.*\\.xlsx$" 只上传以 query_ 开头且以 .xlsx 结尾的文件
            style_options: 样式配置字典，详见 apply_style() 文档

        Returns:
            每个文件上传结果的列表，元素格式与 replace() / upload() 返回一致
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"不是有效目录: {directory}")

        compiled = re.compile(pattern)
        results = []

        for file_path in sorted(directory.iterdir()):
            if not file_path.is_file():
                continue
            if not compiled.search(file_path.name):
                print(f"[DingDocTool] Skip '{file_path.name}' (not match pattern)")
                continue
            try:
                result = self.replace(file_path, style_options=style_options)
                results.append(result)
            except Exception as e:
                print(f"[ERROR] 上传 '{file_path.name}' 失败: {e}")
                results.append(
                    {
                        "success": False,
                        "file": str(file_path),
                        "name": file_path.stem,
                        "error": str(e),
                    }
                )

        print(f"[DingDocTool] Directory upload done: {len(results)} file(s) processed")
        return results

    # ------------------------------------------------------------------
    # 钉钉表格导出
    # ------------------------------------------------------------------

    def export_excel(
            self,
            node_id: str,
            output_path: Union[str, Path],
            export_format: str = "xlsx",
            timeout: int = 120,
            poll_interval: int = 3,
    ) -> Dict[str, Any]:
        """将钉钉在线表格导出为本地 Excel 文件

        钉钉表格（extension=axls）无法通过 get_document_content 直接读取，
        需先提交导出任务，再轮询下载链接

        Args:
            node_id: 钉钉表格的节点 ID 或文档链接 URL
            output_path: 导出文件保存的本地路径
            export_format: 导出格式，默认 "xlsx"
            timeout: 轮询超时时间，单位秒，默认 120 秒
            poll_interval: 轮询间隔，单位秒，默认 3 秒

        Returns:
            {"success": True, "node_id": ..., "output_path": ..., "download_url": ...}
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 可选：确认节点类型并打印提示
        try:
            info = self.get_document_info(node_id)
            ext = info.get("extension", "")
            if ext and ext != "axls":
                print(f"[WARN] 节点扩展名为 '{ext}'，可能不是钉钉表格，但仍尝试导出")
        except Exception as e:
            print(f"[WARN] 获取节点信息失败: {e}")

        print(f"[DingDocTool] Submitting export job for '{node_id}' ...")
        job = self.mcp.call_tool(
            "submit_export_job",
            nodeId=node_id,
            exportFormat=export_format,
        )
        if not job.get("success"):
            raise RuntimeError(f"提交导出任务失败: {job}")

        job_id = job["jobId"]
        print(f"[DingDocTool] Export job id: {job_id}, polling ...")

        download_url = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.mcp.call_tool("query_export_job", jobId=job_id)
            status = result.get("status", "")
            if status in ("success", "SUCCESS", "completed", "COMPLETED"):
                download_url = result.get("downloadUrl") or result.get("fileUrl")
                if download_url:
                    break
            elif status in ("failed", "FAILED", "error", "ERROR"):
                raise RuntimeError(f"导出任务失败: {result}")
            time.sleep(poll_interval)
        else:
            raise TimeoutError(f"导出任务超时（{timeout}s），未获取到下载链接")

        print(f"[DingDocTool] Downloading to '{output_path}' ...")
        urllib.request.urlretrieve(download_url, str(output_path))

        file_size = output_path.stat().st_size
        print(f"[DingDocTool] Exported {file_size:,} bytes: {output_path}")

        return {
            "success": True,
            "node_id": node_id,
            "output_path": str(output_path),
            "download_url": download_url,
            "job_id": job_id,
        }

    # ------------------------------------------------------------------
    # 文档内容读写与节点管理
    # ------------------------------------------------------------------

    def get_document_info(self, node_id: str) -> Dict[str, Any]:
        """获取钉钉文档/文件节点的基本信息

        Args:
            node_id: 文档链接 URL 或 32 位 dentryUuid

        Returns:
            get_document_info 的原始返回结果
        """
        return self.mcp.call_tool("get_document_info", nodeId=node_id)

    def get_workspace_id(self, node_id: str) -> str:
        """
        根据文档node_id获取其所属的知识库 ID
        """
        if not node_id:
            return ''

        folder_info = self.get_document_info(node_id)
        if not folder_info.get('success'):
            return ''

        return folder_info.get('workspaceId', '')

    def get_document_content(
            self,
            node_id: str,
            doc_format: str = "markdown",
            **kwargs,
    ) -> Dict[str, Any]:
        """获取钉钉文档的内容

        Args:
            node_id: 文档链接 URL 或 32 位 dentryUuid
            doc_format: 内容格式，"markdown"（默认）或 "jsonml"
            **kwargs: 其他 get_document_content 支持的参数，如 historyVersion、
                password、scope、tags、startBlockId、endBlockId、maxDepth 等

        Returns:
            get_document_content 的原始返回结果
        """
        return self.mcp.call_tool(
            "get_document_content",
            nodeId=node_id,
            format=doc_format,
            **kwargs,
        )

    def update_document(
            self,
            node_id: str,
            markdown: str,
            mode: str = "overwrite",
            **kwargs,
    ) -> Dict[str, Any]:
        """更新或追加钉钉文档内容

        Args:
            node_id: 文档链接 URL 或 32 位 dentryUuid
            markdown: 要写入的 Markdown 内容
            mode: "overwrite"（覆盖，默认）或 "append"（追加）
            **kwargs: 其他 update_document 支持的参数，如 index、format、jsonml 等

        Returns:
            update_document 的原始返回结果
        """
        return self.mcp.call_tool(
            "update_document",
            nodeId=node_id,
            markdown=markdown,
            mode=mode,
            **kwargs,
        )

    def create_document(
            self,
            name: str,
            markdown: Optional[str] = None,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建一篇新的钉钉文档

        Args:
            name: 新文档标题
            markdown: 初始 Markdown 内容（可选）
            folder_id: 目标文件夹 ID（可选，默认使用初始化时传入的目录）
            workspace_id: 目标知识库 ID（可选，默认使用初始化时传入的知识库）

        Returns:
            create_document 的原始返回结果
        """
        return self.mcp.call_tool(
            "create_document",
            name=name,
            markdown=markdown,
            folderId=folder_id or self.folder_id,
            workspaceId=workspace_id or self.workspace_id,
        )

    def create_folder(
            self,
            name: str,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建一个新的钉钉文件夹

        Args:
            name: 新文件夹名称
            folder_id: 父文件夹 ID（可选，默认使用初始化时传入的目录）
            workspace_id: 目标知识库 ID（可选，默认使用初始化时传入的知识库）

        Returns:
            create_folder 的原始返回结果
        """
        return self.mcp.call_tool(
            "create_folder",
            name=name,
            folderId=folder_id or self.folder_id,
            workspaceId=workspace_id or self.workspace_id,
        )

    def create_file(
            self,
            name: str,
            file_type: str,
            folder_id: Optional[str] = None,
            workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建一个新的钉钉节点（文档/表格/幻灯片/文件夹等）

        Args:
            name: 新文件名称
            file_type: 文件类型，支持 adoc/axls/appt/adraw/amind/able/folder
            folder_id: 目标文件夹 ID（可选，默认使用初始化时传入的目录）
            workspace_id: 目标知识库 ID（可选，默认使用初始化时传入的知识库）

        Returns:
            create_file 的原始返回结果
        """
        return self.mcp.call_tool(
            "create_file",
            name=name,
            type=file_type,
            folderId=folder_id or self.folder_id,
            workspaceId=workspace_id or self.workspace_id,
        )

    def copy_document(
            self,
            node_id: str,
            target_folder_id: str,
            **kwargs,
    ) -> Dict[str, Any]:
        """将指定节点复制到目标文件夹

        Args:
            node_id: 源文档链接 URL 或 dentryUuid
            target_folder_id: 目标文件夹 ID
            **kwargs: 其他 copy_document 支持的参数

        Returns:
            copy_document 的原始返回结果
        """
        return self.mcp.call_tool(
            "copy_document",
            nodeId=node_id,
            targetFolderId=target_folder_id,
            **kwargs,
        )

    def move_document(
            self,
            node_id: str,
            target_folder_id: str,
            **kwargs,
    ) -> Dict[str, Any]:
        """移动指定节点到目标文件夹

        Args:
            node_id: 源文档链接 URL 或 dentryUuid
            target_folder_id: 目标文件夹 ID
            **kwargs: 其他 move_document 支持的参数

        Returns:
            move_document 的原始返回结果
        """
        return self.mcp.call_tool(
            "move_document",
            nodeId=node_id,
            targetFolderId=target_folder_id,
            **kwargs,
        )

    def rename_document(self, node_id: str, new_name: str) -> Dict[str, Any]:
        """对指定节点进行重命名

        Args:
            node_id: 文档链接 URL 或 dentryUuid
            new_name: 新名称

        Returns:
            rename_document 的原始返回结果
        """
        return self.mcp.call_tool(
            "rename_document",
            nodeId=node_id,
            newName=new_name,
        )

    def search_documents(self, keyword: str, **kwargs) -> List[Dict[str, Any]]:
        """按关键词搜索文档

        Args:
            keyword: 搜索关键词（匹配标题和内容）
            **kwargs: 其他 search_documents 支持的参数，如 extensions、workspaceIds、
                page_size、pageToken 等

        Returns:
            文档信息列表，通常位于 result["documents"]
        """
        result = self.mcp.call_tool(
            "search_documents",
            keyword=keyword,
            **kwargs,
        )
        return result.get("documents", [])

    # ------------------------------------------------------------------
    # 文档 Block 级精确编辑
    # ------------------------------------------------------------------

    def list_document_blocks(
            self,
            node_id: str,
            block_format: str = "element",
            **kwargs,
    ) -> List[Dict[str, Any]]:
        """查询指定钉钉文档下的一级块元素列表

        Args:
            node_id: 文档链接 URL 或 dentryUuid
            block_format: 返回格式，"element"（默认）或 "jsonml"
            **kwargs: 其他 list_document_blocks 支持的参数，如 startIndex、endIndex、
                blockType 等

        Returns:
            块元素列表，通常位于 result["blocks"] 或 result["elements"]
        """
        result = self.mcp.call_tool(
            "list_document_blocks",
            nodeId=node_id,
            format=block_format,
            **kwargs,
        )
        return result.get("blocks") or result.get("elements", [])

    def insert_document_block(
            self,
            node_id: str,
            element: Dict[str, Any],
            **kwargs,
    ) -> Dict[str, Any]:
        """在指定文档中插入块元素

        Args:
            node_id: 文档链接 URL 或 dentryUuid
            element: 块元素对象，必须包含 blockType 及对应属性
            **kwargs: 其他 insert_document_block 支持的参数，如 referenceBlockId、
                index、where、format、jsonml 等

        Returns:
            insert_document_block 的原始返回结果
        """
        return self.mcp.call_tool(
            "insert_document_block",
            nodeId=node_id,
            element=element,
            **kwargs,
        )

    def update_document_block(
            self,
            node_id: str,
            block_id: str,
            **kwargs,
    ) -> Dict[str, Any]:
        """更新指定文档中的块元素

        Args:
            node_id: 文档链接 URL 或 dentryUuid
            block_id: 待更新块的 blockId
            **kwargs: 其他 update_document_block 支持的参数，如 element、format、jsonml 等

        Returns:
            update_document_block 的原始返回结果
        """
        return self.mcp.call_tool(
            "update_document_block",
            nodeId=node_id,
            blockId=block_id,
            **kwargs,
        )

    def delete_document_block(self, node_id: str, block_id: str) -> Dict[str, Any]:
        """删除指定文档中的块元素

        Args:
            node_id: 文档链接 URL 或 dentryUuid
            block_id: 要删除的 blockId，支持逗号分隔多个，一次最多 50 个

        Returns:
            delete_document_block 的原始返回结果
        """
        return self.mcp.call_tool(
            "delete_document_block",
            nodeId=node_id,
            blockId=block_id,
        )


if __name__ == "__main__":
    # 示例用法：请把 <folder-node-id> 替换为实际钉钉目录节点 ID
    # MCP 授权地址可通过构造函数、环境变量或 .env 文件传入
    tool = DingDocTool("<folder-node-id>")
    result = tool.replace("/path/to/your/file.xlsx")
    print(result)
