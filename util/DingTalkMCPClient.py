#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉 MCP 客户端基类。

不依赖特定业务，仅负责 JSON-RPC over HTTP 的 MCP 调用、多 server 容灾和基础配置解析。
"""
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

# 尝试加载 .env 文件；如果未安装 python-dotenv 则静默跳过
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_MCP_TIMEOUT = 60


class DingTalkMCPError(Exception):
    """钉钉 MCP 调用异常。"""

    def __init__(self, message, details=None):
        self.details = details
        super().__init__(message)


class DingTalkMCPClient:
    """钉钉文档 MCP 客户端。

    配置优先级（从高到低）：
    1. 构造函数传入的 mcp_url / mcp_servers
    2. 环境变量 DINGTALK_MCP_SERVERS（JSON 数组）或 DINGTALK_MCP_URL（单条 URL）
    3. .env 文件中的上述变量（需安装 python-dotenv）
    """

    def __init__(
        self,
        mcp_url: Optional[str] = None,
        mcp_servers: Optional[List[Dict[str, Any]]] = None,
        timeout: int = DEFAULT_MCP_TIMEOUT,
    ):
        """
        Args:
            mcp_url: 钉钉 MCP 授权地址（单条）。
                格式：`https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>`。
            mcp_servers: 多条 MCP 服务器配置（可选），用于多组织/容灾切换。
                每项字典可包含 base_url / server_id / key / name 字段。
            timeout: HTTP 请求超时时间，单位秒，默认 60 秒。
        """
        self.timeout = timeout
        self.servers = self._resolve_servers(mcp_url, mcp_servers)
        if not self.servers:
            raise DingTalkMCPError(
                "未配置钉钉 MCP 授权地址。\n"
                "请前往钉钉 MCP 市场开通并复制 StreamableHttp URL。\n\n"
                "然后通过以下任一方式配置：\n"
                "1. 构造函数传入 mcp_url='https://mcp-gw.dingtalk.com/server/<server_id>?key=<key>'\n"
                "2. 环境变量 DINGTALK_MCP_URL（单条 URL）或 DINGTALK_MCP_SERVERS（JSON 数组）\n"
                "3. .env 文件中设置上述变量（需安装 python-dotenv）"
            )

    @staticmethod
    def _parse_mcp_url(mcp_url: str) -> Dict[str, Any]:
        """从 MCP URL 中解析出 base_url、server_id、key。"""
        parsed = urlparse(mcp_url)
        qs = parse_qs(parsed.query)

        key = qs.get("key", [None])[0]
        if not key:
            raise ValueError(
                f"授权地址缺少 key 参数: {mcp_url}\n"
                "格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
            )

        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) < 2 or path_parts[0] != "server":
            raise ValueError(
                f"授权地址路径格式不正确: {parsed.path}\n"
                "格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
            )
        server_id = path_parts[1]
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        return {
            "base_url": base_url,
            "server_id": server_id,
            "key": key,
            "name": server_id,
        }

    def _resolve_servers(
        self, mcp_url: Optional[str], mcp_servers: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """解析最终要使用的 MCP 服务器列表。"""
        if mcp_servers:
            return [
                {
                    "base_url": s.get("base_url") or s.get("url", "").split("?")[0],
                    "server_id": s.get("server_id"),
                    "key": s.get("key"),
                    "name": s.get("name", s.get("server_id", "unknown")),
                }
                for s in mcp_servers
            ]

        if mcp_url:
            return [self._parse_mcp_url(mcp_url)]

        env_servers = os.getenv("DINGTALK_MCP_SERVERS")
        if env_servers:
            try:
                servers = json.loads(env_servers)
                return [
                    {
                        "base_url": s.get("base_url", s.get("url", "").split("?")[0]),
                        "server_id": s.get("server_id"),
                        "key": s.get("key"),
                        "name": s.get("name", s.get("server_id", "unknown")),
                    }
                    for s in servers
                ]
            except json.JSONDecodeError as e:
                raise DingTalkMCPError(f"DINGTALK_MCP_SERVERS JSON 解析失败: {e}")

        env_url = os.getenv("DINGTALK_MCP_URL")
        if env_url:
            return [self._parse_mcp_url(env_url)]

        return []

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _call(
        self,
        server: Dict[str, Any],
        method: str,
        params: Dict[str, Any],
        request_id: int = 1,
    ) -> Dict[str, Any]:
        """向指定 MCP 服务器发送 JSON-RPC 请求。"""
        url = f"{server['base_url']}?key={server['key']}"
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        response = requests.post(
            url, headers=self._headers(), json=payload, timeout=self.timeout
        )

        if not response.ok:
            raise DingTalkMCPError(
                f"HTTP {response.status_code}: {response.text}",
                details={"status_code": response.status_code},
            )

        data = response.json()
        if "error" in data:
            raise DingTalkMCPError(
                f"接口错误 {data['error'].get('code')}: {data['error'].get('message')}",
                details=data["error"],
            )
        return data.get("result", {})

    def _initialize(self, server: Dict[str, Any]) -> Dict[str, Any]:
        return self._call(
            server,
            method="initialize",
            params={
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "dingtalk-table-tool", "version": "1.0.0"},
            },
        )

    def _tool_call(
        self, server: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = self._call(
            server,
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
        )
        contents = result.get("content", [])
        if not contents:
            return {}
        text = contents[0].get("text", "")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {"raw_text": text}

    def call_tool(self, tool_name: str, **arguments) -> Dict[str, Any]:
        """尝试所有 MCP 服务器，返回第一个成功结果。"""
        errors = []
        for server in self.servers:
            try:
                self._initialize(server)
                result = self._tool_call(
                    server, tool_name, self._compact_arguments(**arguments)
                )

                # 跨组织错误 → 尝试下一个
                if isinstance(result, dict) and result.get("errorCode") == "forbidden.accessDenied":
                    errors.append(
                        f"[{server.get('name', '?')}] 跨组织限制: {result.get('errorMessage', '')}"
                    )
                    continue

                # 业务失败 → 尝试下一个
                if isinstance(result, dict) and result.get("success") is False:
                    errors.append(
                        f"[{server.get('name', '?')}] {result.get('errorMessage', '未知错误')}"
                    )
                    continue

                return result
            except DingTalkMCPError as e:
                errors.append(f"[{server.get('name', '?')}] {str(e)}")
                continue
            except requests.RequestException as e:
                errors.append(f"[{server.get('name', '?')}] 网络错误: {str(e)}")
                continue

        raise DingTalkMCPError(
            f"所有授权均无法完成请求-{tool_name}:\n" + "\n".join(errors),
            details={"errors": errors},
        )

    @staticmethod
    def _compact_arguments(**arguments) -> Dict[str, Any]:
        return {key: value for key, value in arguments.items() if value is not None}
