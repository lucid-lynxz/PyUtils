"""
钉钉多维表工具类

通过钉钉 MCP 接口操作多维表，支持子表管理、字段管理、数据增删改查等功能。

配置优先级: 直接传入 > .env配置文件 > 系统环境变量
环境变量:
    DINGTALK_MCP_URL: 钉钉 MCP 接口地址
    DINGTALK_BASE_ID: 多维表 Base ID

.env 配置文件路径: 用户指定 或 ./config/.env 或 ./cache/.env

pip install python-dotenv

模块	方法	说明
配置管理	__init__()	支持直接传入 / .env / 环境变量三级优先级
子表管理
    create_table()	创建子表
    delete_table()	删除子表
    get_tables()	获取子表列表
    get_default_view_id()	获取默认视图 ID
    get_table_link()	获取子表访问链接
字段管理
    create_fields()	批量创建字段（自动重命名标题列为"编号"）
    get_fields()	获取字段列表
    update_field()	更新字段
    delete_field()	删除字段
数据操作
    create_records()	批量写入记录（支持分页）
    get_records()	查询记录（支持分页和过滤）
    update_records()	批量更新记录
    delete_records()	批量删除记录
DataFrame 转换
    records_to_dataframe()	读取子表数据转为 DataFrame
    dataframe_to_records()	DataFrame 转为记录列表
便捷方法
    export_to_sheet()	一键导出（创建子表+字段+写入）


配置方式:
# 方式1: .env 文件 (ai_test/cache/.env)
DINGTALK_MCP_URL=https://mcp-gw.dingtalk.com/server/xxx?key=xxx
DINGTALK_BASE_ID=AbCdEfGhIjKlMnOpQrStUvWxYz

# 方式2: 环境变量
export DINGTALK_MCP_URL=...
export DINGTALK_BASE_ID=...

# 方式3: 直接传入
util = DingTalkAISheetUtil(mcp_url="...", base_id="...")

使用示例:
from util.DingTalkAISheetUtil import DingTalkAISheetUtil

util = DingTalkAISheetUtil()  # 自动从 .env 或环境变量读取

# 一键导出
link = util.export_to_sheet(rows, "测试表")

# 或分步操作
table_id = util.create_table("测试表")
util.create_fields(table_id)
util.create_records(table_id, rows)

# 读取为 DataFrame
df = util.records_to_dataframe(table_id)
"""

import json
import os
import requests
from typing import Dict, Optional, Any, List, Union, Self
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

from util.CommonUtil import CommonUtil
from util.FileUtil import FileUtil


class DingTalkAISheetUtil:
    """钉钉多维表工具类"""

    def __init__(
            self,
            fields_names: Optional[List[str]] = None,
            url_field_names: Optional[List[str]] = None,
            mcp_url: Optional[str] = None,
            base_id: Optional[str] = None,
            env_path: str = None,
            timeout: int = 60,
            print_log: bool = True
    ):
        """
        初始化钉钉多维表工具类

        :param fields_names: 列名列表(含url字段)
        :param url_field_names: 列名中属于URL的列名列表
        :param mcp_url: 钉钉 MCP 接口地址，优先级: 直接传入 > .env > 环境变量
        :param base_id: 多维表 Base ID，优先级: 直接传入 > .env > 环境变量
        :param timeout: 请求超时时间（秒）
        :param print_log: 是否打印日志
        """
        self.timeout = timeout
        self.print_log = print_log

        # 加载 .env 配置文件
        if CommonUtil.isNoneOrBlank(env_path):
            dir_parent = Path(__file__).resolve().parent
            env_path1 = str((dir_parent / "config" / ".env").resolve())
            env_path2 = str((dir_parent / "cache" / ".env").resolve())
            if FileUtil.isFileExist(env_path1):
                env_path = FileUtil.recookPath(env_path1)
            elif FileUtil.isFileExist(env_path2):
                env_path = FileUtil.recookPath(env_path2)

        if FileUtil.isFileExist(env_path):
            load_dotenv(dotenv_path=env_path)

        # 配置优先级: 直接传入 > .env > 环境变量
        self.mcp_url = self._resolve_config(mcp_url, "DINGTALK_MCP_URL")
        self.base_id = self._resolve_config(base_id, "DINGTALK_BASE_ID")

        # 字段名 -> fieldId 缓存（按 table_id 分组）
        self._field_cache: Dict[str, Dict[str, str]] = {}

        # 默认字段配置
        self.all_field_names = fields_names or []
        self.url_field_names = url_field_names or []

    def update_fields(self, fields_names: Optional[List[str]] = None,
                      url_field_names: Optional[List[str]] = None) -> Self:
        """
        更新默认字段配置
        :param fields_names: 列名列表(含url字段)
        :param url_field_names: 列名中属于URL的列名列表
        """
        self.all_field_names = fields_names or []
        self.url_field_names = url_field_names or []
        return self

    def _resolve_config(self, direct_value: Optional[str], env_var: str) -> Optional[str]:
        """
        解析配置值，优先级: 直接传入 > .env/环境变量

        :param direct_value: 直接传入的值, 若为空,则从环境变量中读取 env_var 变量值
        :param env_var: 环境变量名
        """
        if not CommonUtil.isNoneOrBlank(direct_value):
            return direct_value

        # 从系统环境变量读取
        return os.getenv(env_var)
        # return os.environ.get(env_var)

    def _log(self, msg: str):
        """打印日志"""
        if self.print_log:
            CommonUtil.printLog(msg)

    def _call(self, tool_name: str, args_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        调用钉钉 MCP 接口

        :param tool_name: 工具名称，如 create_table, get_records 等
        :param args_dict: 工具参数
        :return: 接口返回结果 dict，失败返回 None
        """
        if not self.mcp_url:
            self._log(f"错误: MCP URL 未配置")
            return None

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args_dict},
            "id": 1,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        try:
            resp = requests.post(self.mcp_url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                self._log(f"接口调用失败: HTTP {resp.status_code}")
                return None
            result = resp.json()
            if "result" in result and "content" in result["result"]:
                for item in result["result"]["content"]:
                    if item.get("type") == "text":
                        return json.loads(item["text"])
            return result
        except (requests.RequestException, json.JSONDecodeError) as e:
            self._log(f"接口调用失败: {e}")
            return None

    # ==================== 子表管理 ====================

    def create_table(self, table_name: str, table_id: Optional[str] = None) -> Optional[str]:
        """
        创建子表

        :param table_name: 子表名称
        :param table_id: 指定 base_id，不传则使用实例默认值
        :return: 子表 ID，失败返回 None
        """
        bid = table_id or self.base_id
        if not bid:
            self._log("错误: base_id 未配置")
            return None

        self._log(f"创建子表: {table_name} ...")
        resp = self._call("create_table", {"baseId": bid, "tableName": table_name})
        if resp and resp.get("status") == "success":
            tid = resp["data"]["tableId"]
            self._log(f"[OK] tableId={tid}")
            return tid
        self._log("[FAIL]")
        return None

    def delete_table(self, table_id: str, base_id: Optional[str] = None) -> bool:
        """
        删除子表

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 是否成功
        """
        bid = base_id or self.base_id
        self._log(f"删除子表: {table_id} ...")
        resp = self._call("delete_table", {"baseId": bid, "tableId": table_id})
        if resp and resp.get("status") == "success":
            self._log("[OK]")
            return True
        self._log("[FAIL]")
        return False

    def get_tables(self, base_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取多维表下的所有子表列表

        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 子表列表，每个元素包含 id, name 等信息
        """
        bid = base_id or self.base_id
        self._log(f"获取子表列表 ...")
        resp = self._call("get_tables", {"baseId": bid})
        if resp and resp.get("status") == "success":
            tables = resp.get("data", {}).get("tables", [])
            self._log(f"[OK] 共 {len(tables)} 个子表")
            return tables
        self._log("[FAIL]")
        return []

    def get_default_view_id(self, table_id: str, base_id: Optional[str] = None) -> Optional[str]:
        """
        获取指定子表的默认视图 ID

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 视图 ID，失败返回 None
        """
        bid = base_id or self.base_id
        self._log(f"获取子表视图 ...")
        resp = self._call("get_views", {"baseId": bid, "tableId": table_id})
        if resp and resp.get("status") == "success":
            views = resp.get("data", {}).get("views", [])
            if views:
                view_id = views[0].get("viewId")
                self._log(f"[OK] viewId={view_id}")
                return view_id
            self._log("[WARN] 未找到视图")
        else:
            self._log(f"[FAIL] resp={resp}")
        return None

    def get_table_link(self, table_id: str, base_id: Optional[str] = None) -> Optional[str]:
        """
        获取子表的访问链接

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 访问链接，失败返回 None
        """
        bid = base_id or self.base_id
        view_id = self.get_default_view_id(table_id, bid)
        if view_id:
            return f"https://docs.dingtalk.com/i/nodes/{bid}?iframeQuery=entrance%3Ddata%26sheetId%3D{table_id}%26viewId%3D{view_id}"
        return f"https://docs.dingtalk.com/i/nodes/{bid}?iframeQuery=sheet%3D{table_id}"

    # ==================== 字段管理 ====================

    def _get_field_cache_key(self, table_id: str, base_id: Optional[str] = None) -> str:
        """获取字段缓存的 key"""
        bid = base_id or self.base_id
        return f"{bid}:{table_id}"

    def _load_field_mapping(self, table_id: str, base_id: Optional[str] = None) -> Dict[str, str]:
        """
        从已有表加载字段名 -> fieldId 映射

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 字段名 -> fieldId 映射
        """
        cache_key = self._get_field_cache_key(table_id, base_id)
        if cache_key in self._field_cache:
            return self._field_cache[cache_key]

        bid = base_id or self.base_id
        resp = self._call("get_fields", {"baseId": bid, "tableId": table_id})
        field_map = {}
        if resp and resp.get("status") == "success":
            for f in resp.get("data", {}).get("fields", []):
                fn, fid = f.get("fieldName"), f.get("fieldId")
                if fn and fid:
                    field_map[fn] = fid
        self._field_cache[cache_key] = field_map
        return field_map

    def create_fields(self, table_id: str, base_id: Optional[str] = None, batch_size: int = 15) -> bool:
        """
        批量创建字段

        :param table_id: 子表 ID
        :param fields: 字段列表，每项为 {"fieldName": "字段名", "type": "text|url|..."}
                       不传则使用默认字段配置
        :param base_id: 指定 base_id，不传则使用实例默认值
        :param batch_size: 每批创建的字段数
        :return: 是否全部成功
        """
        bid = base_id or self.base_id
        fields = []

        for key in self.all_field_names:
            field_type = "url" if key in self.url_field_names else "text"
            fields.append({"fieldName": key, "type": field_type})

        total = len(fields)
        all_success = True

        for batch_start in range(0, total, batch_size):
            batch = fields[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            self._log(f"创建字段 [{batch_num}/{total_batches}] ...")
            resp = self._call("create_fields", {
                "baseId": bid, "tableId": table_id, "fields": batch,
            })
            if resp and resp.get("status") == "success":
                for r in resp.get("data", {}).get("results", []):
                    fn, fid = r.get("fieldName"), r.get("fieldId")
                    if fn and fid:
                        self._field_cache[self._get_field_cache_key(table_id, bid)][fn] = fid
                self._log("[OK]")
            else:
                self._log("[FAIL]")
                all_success = False

        # 重命名标题列为"编号"
        self._rename_title_field(table_id, bid)
        # 重新加载字段映射
        self._load_field_mapping(table_id, bid)
        return all_success

    def _rename_title_field(self, table_id: str, base_id: Optional[str] = None):
        """重命名标题列为"编号"，删除重复的编号字段"""
        bid = base_id or self.base_id
        resp = self._call("get_fields", {"baseId": bid, "tableId": table_id})
        if not resp or resp.get("status") != "success":
            return

        fields = resp.get("data", {}).get("fields", [])
        title_field_id = None
        duplicate_field_id = None

        for f in fields:
            if f.get("fieldName") == "编号" and f.get("type") == "primaryDoc":
                return
            if f.get("type") == "primaryDoc":
                title_field_id = f["fieldId"]
            if f.get("fieldName") == "编号" and f.get("type") != "primaryDoc":
                duplicate_field_id = f["fieldId"]

        if not title_field_id:
            return

        if duplicate_field_id:
            self._call("delete_field", {
                "baseId": bid, "tableId": table_id, "fieldId": duplicate_field_id,
            })

        self._log(f"重命名标题列为编号 ...")
        resp = self._call("update_field", {
            "baseId": bid, "tableId": table_id,
            "fieldId": title_field_id, "newFieldName": "编号",
        })
        self._log("[OK]" if resp and resp.get("status") == "success" else "[FAIL]")

    def get_fields(self, table_id: str, base_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取子表的所有字段

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 字段列表
        """
        bid = base_id or self.base_id
        resp = self._call("get_fields", {"baseId": bid, "tableId": table_id})
        if resp and resp.get("status") == "success":
            return resp.get("data", {}).get("fields", [])
        return []

    def update_field(
            self,
            table_id: str,
            field_id: str,
            new_field_name: Optional[str] = None,
            base_id: Optional[str] = None
    ) -> bool:
        """
        更新字段

        :param table_id: 子表 ID
        :param field_id: 字段 ID
        :param new_field_name: 新字段名
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 是否成功
        """
        bid = base_id or self.base_id
        args = {"baseId": bid, "tableId": table_id, "fieldId": field_id}
        if new_field_name:
            args["newFieldName"] = new_field_name
        resp = self._call("update_field", args)
        return resp and resp.get("status") == "success"

    def delete_field(self, table_id: str, field_id: str, base_id: Optional[str] = None) -> bool:
        """
        删除字段

        :param table_id: 子表 ID
        :param field_id: 字段 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 是否成功
        """
        bid = base_id or self.base_id
        resp = self._call("delete_field", {"baseId": bid, "tableId": table_id, "fieldId": field_id})
        return resp and resp.get("status") == "success"

    # ==================== 数据操作 ====================

    def _build_cells(self, row: Dict[str, Any], table_id: str, base_id: Optional[str] = None) -> Dict[str, Any]:
        """
        将一行数据转换为 cells 格式

        :param row: 数据行 dict
        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: cells dict
        """
        field_map = self._load_field_mapping(table_id, base_id)
        cells = {}

        for key, value in row.items():
            fid = field_map.get(key)
            if not fid:
                continue
            if value is None:
                value = ""
            elif key in self.url_field_names and value:
                value = {"link": str(value), "text": str(value)}
            elif isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            else:
                value = str(value)
            cells[fid] = value

        # 标题列
        serial = row.get("编号", "")
        title_fid = field_map.get("编号")
        if serial and title_fid:
            cells[title_fid] = str(serial)

        return cells

    def create_records(
            self,
            table_id: str,
            rows: List[Dict[str, Any]],
            base_id: Optional[str] = None,
            batch_size: int = 100
    ) -> tuple:
        """
        批量写入记录

        :param table_id: 子表 ID
        :param rows: 数据行列表
        :param base_id: 指定 base_id，不传则使用实例默认值
        :param batch_size: 每批写入的记录数
        :return: (成功数, 失败数)
        """
        bid = base_id or self.base_id
        total = len(rows)
        success = 0
        fail = 0

        for batch_start in range(0, total, batch_size):
            batch = rows[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            records = [self._build_cells(row, table_id, bid) for row in batch]
            self._log(f"写入记录 [{batch_num}/{total_batches}] {len(batch)} 条 ...")
            resp = self._call("create_records", {
                "baseId": bid, "tableId": table_id, "records": records,
            })
            if resp and resp.get("status") == "success":
                self._log("[OK]")
                success += len(batch)
            else:
                self._log("[FAIL]")
                error_msg = resp.get("error", {}).get("message", "") if resp else ""
                self._log(f"    错误详情: {error_msg}")
                fail += len(batch)

        self._log(f"写入完成：成功 {success} 条，失败 {fail} 条")
        return success, fail

    def get_records(
            self,
            table_id: str,
            base_id: Optional[str] = None,
            page_size: int = 100,
            page_num: int = 1,
            filter_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        查询记录

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :param page_size: 每页记录数
        :param page_num: 页码
        :param filter_query: 过滤条件
        :return: 记录列表
        """
        bid = base_id or self.base_id
        args = {"baseId": bid, "tableId": table_id, "pageSize": page_size, "pageNum": page_num}
        if filter_query:
            args["filter"] = filter_query

        self._log(f"查询记录 (page={page_num}, size={page_size}) ...")
        resp = self._call("get_records", args)
        if resp and resp.get("status") == "success":
            records = resp.get("data", {}).get("records", [])
            self._log(f"[OK] 共 {len(records)} 条")
            return records
        self._log("[FAIL]")
        return []

    def update_records(
            self,
            table_id: str,
            records: List[Dict[str, Any]],
            base_id: Optional[str] = None
    ) -> bool:
        """
        批量更新记录

        :param table_id: 子表 ID
        :param records: 记录列表，每项为 {"id": "记录ID", "cells": {"fieldId": "值"}}
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 是否成功
        """
        bid = base_id or self.base_id
        self._log(f"更新记录 {len(records)} 条 ...")
        resp = self._call("update_records", {
            "baseId": bid, "tableId": table_id, "records": records,
        })
        if resp and resp.get("status") == "success":
            self._log("[OK]")
            return True
        self._log("[FAIL]")
        return False

    def delete_records(
            self,
            table_id: str,
            record_ids: List[str],
            base_id: Optional[str] = None
    ) -> bool:
        """
        批量删除记录

        :param table_id: 子表 ID
        :param record_ids: 记录 ID 列表
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 是否成功
        """
        bid = base_id or self.base_id
        self._log(f"删除记录 {len(record_ids)} 条 ...")
        resp = self._call("delete_records", {
            "baseId": bid, "tableId": table_id, "recordIds": record_ids,
        })
        if resp and resp.get("status") == "success":
            self._log("[OK]")
            return True
        self._log("[FAIL]")
        return False

    # ==================== DataFrame 转换 ====================

    def records_to_dataframe(
            self,
            table_id: str,
            base_id: Optional[str] = None,
            page_size: int = 100,
            filter_query: Optional[str] = None
    ) -> pd.DataFrame:
        """
        读取子表所有数据并转为 DataFrame

        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :param page_size: 每页记录数
        :param filter_query: 过滤条件
        :return: DataFrame
        """
        bid = base_id or self.base_id
        field_map = self._load_field_mapping(table_id, bid)
        # 反转映射: fieldId -> fieldName
        id_to_name = {fid: fn for fn, fid in field_map.items()}

        all_records = []
        page_num = 1
        while True:
            records = self.get_records(table_id, bid, page_size, page_num, filter_query)
            if not records:
                break
            all_records.extend(records)
            if len(records) < page_size:
                break
            page_num += 1

        if not all_records:
            return pd.DataFrame()

        # 转换 cells 为列
        rows = []
        for record in all_records:
            row = {"id": record.get("id", "")}
            cells = record.get("cells", {})
            for fid, value in cells.items():
                fn = id_to_name.get(fid, fid)
                if isinstance(value, dict):
                    value = value.get("text", str(value))
                row[fn] = value
            rows.append(row)

        return pd.DataFrame(rows)

    def dataframe_to_records(self, df: pd.DataFrame, table_id: str, base_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        将 DataFrame 转换为记录列表（用于写入）

        :param df: DataFrame
        :param table_id: 子表 ID
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 记录列表
        """
        rows = df.to_dict(orient="records")
        records = []
        for row in rows:
            cells = self._build_cells(row, table_id, base_id)
            records.append({"cells": cells})
        return records

    # ==================== 便捷方法 ====================

    def export_to_sheet(
            self,
            rows: List[Dict[str, Any]],
            table_name: str,
            base_id: Optional[str] = None
    ) -> Optional[str]:
        """
        一键导出数据到钉钉多维表（创建子表 + 创建字段 + 写入数据）

        :param rows: 数据行列表
        :param table_name: 子表名称
        :param base_id: 指定 base_id，不传则使用实例默认值
        :return: 子表访问链接，失败返回 None
        """
        bid = base_id or self.base_id
        self._log(f"准备写入 {len(rows)} 条记录到钉钉多维表...")

        table_id = self.create_table(table_name, bid)
        if not table_id:
            self._log("创建子表失败，退出")
            return None

        self.create_fields(table_id, base_id=bid)
        self.create_records(table_id, rows, base_id=bid)

        return self.get_table_link(table_id, bid)


if __name__ == "__main__":
    # 测试入口
    from datetime import date

    # 创建实例（从 .env 或环境变量读取配置）
    util = DingTalkAISheetUtil(print_log=True)

    if not util.mcp_url or not util.base_id:
        print("错误: 请先配置 DINGTALK_MCP_URL 和 DINGTALK_BASE_ID")
        print("  方式1: 在 ai_test/cache/.env 中设置")
        print("  方式2: 设置环境变量 export DINGTALK_MCP_URL=... DINGTALK_BASE_ID=...")
        exit(1)

    print(f"MCP URL: {util.mcp_url}")
    print(f"Base ID: {util.base_id}")
    print()

    # 测试 1: 获取子表列表
    print("=== 测试 1: 获取子表列表 ===")
    tables = util.get_tables()
    for t in tables:
        print(f"  - {t.get('id')}: {t.get('name')}")
    print()

    # 测试 2: 创建子表 + 字段 + 写入数据
    print("=== 测试 2: 创建子表 + 字段 + 写入数据 ===")
    table_name = f"测试_{date.today().strftime('%Y%m%d')}"
    table_id = util.create_table(table_name)
    if table_id:
        print(f"子表创建成功: {table_id}")

        # 创建字段
        util.create_fields(table_id)

        # 写入测试数据
        test_rows = [
            {"编号": "1", "query": "测试查询1", "预期结果": "正常", "评分": "5"},
            {"编号": "2", "query": "测试查询2", "预期结果": "异常", "评分": "3", "aone链接": "https://aone.alibaba-inc.com"},
        ]
        success, fail = util.create_records(table_id, test_rows)
        print(f"写入结果: 成功 {success}, 失败 {fail}")

        # 获取链接
        link = util.get_table_link(table_id)
        print(f"访问链接: {link}")
        print()

        # 测试 3: 查询记录
        print("=== 测试 3: 查询记录 ===")
        records = util.get_records(table_id)
        print(f"共 {len(records)} 条记录")
        print()

        # 测试 4: 转为 DataFrame
        print("=== 测试 4: 转为 DataFrame ===")
        df = util.records_to_dataframe(table_id)
        print(df.to_string())
        print()

        # 测试 5: 删除子表
        print("=== 测试 5: 删除子表 ===")
        if util.delete_table(table_id):
            print("子表已删除")
