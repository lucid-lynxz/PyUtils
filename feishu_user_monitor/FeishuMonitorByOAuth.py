"""
FeishuMonitorByOAuth — 飞书群消息监听工具类（用户 OAuth 身份版）

以你自己的飞书账号身份轮询群消息，无需机器人入群。
整合了 OAuth 授权、Token 管理、群列表查询、消息监听全部功能。

快速上手：
    monitor = FeishuMonitorByOAuth(app_id="cli_xxx", app_secret="xxx")
    monitor.start(chat_names=["产品研发群", "客户支持群"])

或直接读取 .env 配置：
    monitor = FeishuMonitorByOAuth()
    monitor.start(chat_names=["产品研发群"])
"""

import os
import sys
import json
import time
import base64
import datetime
import traceback
import webbrowser
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from dotenv import load_dotenv
from util.FileUtil import FileUtil

# ══════════════════════════════════════════════════════════════════
#  常量
# ══════════════════════════════════════════════════════════════════

_FEISHU_API = "https://open.feishu.cn/open-apis"
_FEISHU_AUTHORIZE_URL = "https://open.feishu.cn/open-apis/authen/v1/authorize"
_FEISHU_TENANT_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/access_token"
_FEISHU_REFRESH_URL = "https://open.feishu.cn/open-apis/authen/v1/refresh_access_token"
_OAUTH_SCOPE = "im:chat im:message im:message:readonly"
_DEFAULT_TOKEN_FILE = Path(__file__).parent / ".token.json"
_DEFAULT_ENV_FILE = Path(__file__).parent / ".env"


# ══════════════════════════════════════════════════════════════════
#  终端颜色
# ══════════════════════════════════════════════════════════════════

class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    GRAY = "\033[90m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"


def _cp(text: str, color: str = _C.RESET) -> None:
    print(f"{color}{text}{_C.RESET}")


# ══════════════════════════════════════════════════════════════════
#  OAuth 回调 Handler（模块级，供 HTTPServer 使用）
# ══════════════════════════════════════════════════════════════════

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None
    error: str | None = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _OAuthCallbackHandler.code = params["code"][0]
            body = "<h2>✅ 授权成功！可以关闭此页面。</h2>".encode("utf-8")
        else:
            _OAuthCallbackHandler.error = params.get("error", ["unknown"])[0]
            body = "<h2>❌ 授权失败</h2>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 屏蔽 HTTP 访问日志


# ══════════════════════════════════════════════════════════════════
#  FeishuMonitorByOAuth
# ══════════════════════════════════════════════════════════════════

class FeishuMonitorByOAuth:
    """
    飞书群消息监听工具类（用户 OAuth 身份版）

    Args:
        app_id:          飞书 App ID。不传则读取 .env / 环境变量 FEISHU_APP_ID
        app_secret:      飞书 App Secret。不传则读取 .env / 环境变量 FEISHU_APP_SECRET
        redirect_port:   OAuth 回调本地端口，默认 9721
        token_file:      token 持久化路径，默认 <包目录>/.token.json
        env_file:        .env 文件路径，默认 <包目录>/.env

    典型用法：
        monitor = FeishuMonitorByOAuth(app_id="cli_xxx", app_secret="xxx")
        monitor.start(chat_names=["产品群"])
    """

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------

    def __init__(
            self,
            app_id: str | None = None,
            app_secret: str | None = None,
            redirect_port: int = 9721,
            token_file: Path | str | None = None,
            env_file: Path | str | None = None,
    ):
        self._env_file = Path(env_file) if env_file else _DEFAULT_ENV_FILE
        self._token_file = Path(token_file) if token_file else _DEFAULT_TOKEN_FILE
        if self._env_file and self._env_file.is_file():
            load_dotenv(str(self._env_file))
        self.cache_dir = FileUtil.create_cache_dir(None, __file__)

        self.app_id = app_id or self._env("FEISHU_APP_ID")
        self.app_secret = app_secret or self._env("FEISHU_APP_SECRET")
        self.redirect_port = redirect_port or int(self._env("FEISHU_REDIRECT_PORT", "9721"))

        if not self.app_id or not self.app_secret:
            _cp("❌ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET", _C.RED)
            _cp("   请在 .env 中配置，或通过构造参数传入", _C.RED)
            sys.exit(1)

        # 发送者名称缓存
        self._sender_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 公开方法：监听消息（主入口）
    # ------------------------------------------------------------------

    def start(
            self,
            chat_names: list[str] | None = None,
            poll_interval: int = 8,
            download_images: bool = False,
            callback=None,
    ) -> None:
        """
        启动消息监听，阻塞运行直到 Ctrl+C。

        Args:
            chat_names:      要监听的群名列表，支持精确/模糊匹配。
                             为空时自动从 .env 的 FEISHU_CHAT_NAMES 读取，支持多个群以逗号分割。
            poll_interval:   轮询间隔（秒），默认 8
            download_images: 是否将图片保存到本地，默认 False
            callback:        新消息回调函数，签名为 callback(msg: dict, chat_name: str)
                             msg 字段说明：
                               msg_type    消息类型（text/post/image/...）
                               msg_id      消息 ID
                               create_time 时间字符串（已格式化）
                               sender_id   发送者 open_id
                               sender_name 发送者姓名（预加载缓存命中则为真实名）
                               sender_type 发送者类型（user/app）
                               content     解析后的可读内容
                               raw         原始消息 dict（完整飞书消息体）
        """
        if not chat_names:
            raw = self._env("FEISHU_CHAT_NAMES", "")
            chat_names = [n.strip() for n in raw.split(",") if n.strip()]
            if not chat_names:
                _cp("❌ chat_names 为空且 .env 中未配置 FEISHU_CHAT_NAMES", _C.RED)
                sys.exit(1)

        _cp("\n" + "═" * 62, _C.CYAN)
        _cp("  🚀 飞书群消息监听器（用户身份版）已启动", _C.BOLD)
        _cp(f"  目标群：{', '.join(chat_names)}", _C.CYAN)
        _cp(f"  轮询间隔：{poll_interval} 秒  |  按 Ctrl+C 停止", _C.GRAY)
        _cp(f"  消息回调：{'已设置' if callback else '未设置（仅控制台输出）'}", _C.GRAY)
        _cp("═" * 62 + "\n", _C.CYAN)

        token = self.get_valid_token()
        chat_id_map = self.resolve_chat_ids(token, chat_names)  # {chat_id: 显示名}

        _cp("监听中的群：", _C.CYAN)
        for cid, name in chat_id_map.items():
            _cp(f"  • {name}  ({cid})", _C.GREEN)
        _cp("")

        # 预加载群成员名字到缓存（im:chat 权限即可，无需 contact 权限）
        self._preload_members(token, list(chat_id_map.keys()))

        now_ms = int(time.time() * 1000) - 5000
        latest_ts = {cid: now_ms for cid in chat_id_map}

        _cp("👂 开始监听，等待新消息...\n", _C.CYAN)

        try:
            while True:
                token = self.refresh_token_if_needed() or self.get_valid_token()
                for chat_id, chat_name in chat_id_map.items():
                    try:
                        new_msgs, new_ts = self.fetch_new_messages(token, chat_id, latest_ts[chat_id])
                        latest_ts[chat_id] = new_ts
                        for m in new_msgs:
                            downloaded: dict[str, str] = {}
                            try:
                                _img_dir = FileUtil.recookPath(f'{self.cache_dir}/{chat_name}/')
                                FileUtil.create_dir(_img_dir)
                                downloaded = self._print_message(m, chat_name, token, download_images, _img_dir)
                            except Exception as print_err:
                                _cp(f"[错误] 消息打印异常: {print_err}", _C.RED)
                                _cp(traceback.format_exc(), _C.RED)
                            if callback:
                                try:
                                    callback(self._build_msg_dict(m, chat_name, token, downloaded), chat_name)
                                except Exception as cb_err:
                                    _cp(f"[错误] 回调函数执行异常: {cb_err}", _C.RED)
                    except Exception as e:
                        _cp(f"[错误] 群 {chat_name} 轮询异常: {e}", _C.RED)
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            _cp("\n\n  👋 监听已停止。", _C.CYAN)

    # ------------------------------------------------------------------
    # 公开方法：列出所有群聊
    # ------------------------------------------------------------------

    def list_chats(self) -> list[dict]:
        """
        获取当前用户加入的所有群聊列表，并打印到终端。

        Returns:
            群聊信息列表，每项包含 name / chat_id / chat_type 等字段
        """
        token = self.get_valid_token()
        _cp("\n正在获取你加入的群列表...\n", _C.GRAY)

        all_chats: list[dict] = []
        page_token = None

        while True:
            params: dict = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            try:
                resp = self._get(f"{_FEISHU_API}/im/v1/chats", token, params=params)
            except RuntimeError as e:
                _cp(f"❌ 获取群列表失败:\n  {e}", _C.RED)
                return []

            if resp.get("code") != 0:
                _cp(f"❌ 获取群列表失败 (code={resp.get('code')}): {resp.get('msg')}", _C.RED)
                return []

            data = resp.get("data", {})
            items = data.get("items") or []
            all_chats.extend(items)

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        if not all_chats:
            _cp("⚠️  没有找到任何群聊。", _C.YELLOW)
            return all_chats

        _cp(f"共找到 {len(all_chats)} 个群聊：\n", _C.CYAN)
        _cp(f"{'序号':<5} {'群名称':<35} {'类型':<8} {'chat_id'}", _C.BOLD)
        _cp("-" * 90, _C.GRAY)
        for i, chat in enumerate(all_chats, 1):
            name = (chat.get("name") or "（未命名）")[:33]
            chat_id = chat.get("chat_id", "")
            chat_type = chat.get("chat_type", "")
            print(f"{i:<5} {name:<35} {chat_type:<8} {chat_id}")

        _cp("\n将群名传入 start(chat_names=[...]) 即可开始监听", _C.GRAY)
        return all_chats

    # ------------------------------------------------------------------
    # 公开方法：Token 管理
    # ------------------------------------------------------------------

    def get_valid_token(self) -> str:
        """
        获取有效的 user_access_token。
        - 本地有效 → 直接返回
        - 快过期   → 自动刷新后返回
        - 已过期   → 弹浏览器重新授权后返回
        """
        token = self.refresh_token_if_needed()
        if token:
            return token
        _cp("  ⚠️  需要重新授权（首次使用或 refresh_token 已过期）", _C.YELLOW)
        token = self._do_oauth()
        if not token:
            _cp("  ❌ 授权失败，程序退出", _C.RED)
            sys.exit(1)
        return token

    def refresh_token_if_needed(self) -> str | None:
        """
        检查本地 token，若即将过期则自动刷新。
        返回有效 token 字符串，或 None（需重新授权）。
        """
        token_data = self._load_token()
        if not token_data:
            return None

        now = time.time()
        expires_at = token_data.get("access_token_expires_at", 0)

        if now < expires_at - 300:  # 提前 5 分钟刷新
            return token_data["user_access_token"]

        refresh_tok = token_data.get("refresh_token", "")
        refresh_expires_at = token_data.get("refresh_token_expires_at", 0)

        if not refresh_tok or now >= refresh_expires_at:
            return None  # refresh_token 也过期，需重新授权

        _cp("  🔄 access_token 即将过期，正在自动刷新...", _C.GRAY)
        try:
            tenant_token = self._get_tenant_access_token()
            resp = self._post_json(
                _FEISHU_REFRESH_URL,
                {"grant_type": "refresh_token", "refresh_token": refresh_tok},
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            if resp.get("code", -1) != 0:
                _cp(f"  ❌ 刷新失败: {resp}", _C.RED)
                return None

            d = resp.get("data", resp)
            new_data = {
                "user_access_token": d["access_token"],
                "refresh_token": d["refresh_token"],
                "access_token_expires_at": now + d.get("expires_in", 7200),
                "refresh_token_expires_at": now + d.get("refresh_expires_in", 2592000),
            }
            self._save_token(new_data)
            _cp("  ✅ Token 刷新成功", _C.GREEN)
            return new_data["user_access_token"]
        except Exception as e:
            _cp(f"  ❌ 刷新异常: {e}", _C.RED)
            return None

    # ------------------------------------------------------------------
    # 公开方法：群名 → chat_id 解析
    # ------------------------------------------------------------------

    def resolve_chat_ids(self, token: str, target_names: list[str]) -> dict[str, str]:
        """
        根据群名列表查找对应的 chat_id。
        支持精确匹配和模糊匹配（包含关键词）。

        Args:
            token:        user_access_token
            target_names: 要查找的群名关键词列表

        Returns:
            {chat_id: 群显示名} 字典
        """
        _cp("  正在拉取群列表，解析 chat_id...", _C.GRAY)

        all_chats: list[dict] = []
        page_token = None

        while True:
            params: dict = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            try:
                resp = self._get(f"{_FEISHU_API}/im/v1/chats", token, params=params)
            except RuntimeError as e:
                _cp(f"  ❌ 获取群列表请求失败:\n  {e}", _C.RED)
                sys.exit(1)

            if resp.get("code") != 0:
                _cp(f"  ❌ 获取群列表失败 (code={resp.get('code')}): {resp.get('msg')}", _C.RED)
                _cp(f"  完整响应: {json.dumps(resp, ensure_ascii=False)}", _C.RED)
                sys.exit(1)

            data = resp.get("data", {})
            items = data.get("items") or []
            all_chats.extend(items)

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        # name → chat_id 映射
        name_map: dict[str, str] = {
            chat["name"]: chat["chat_id"]
            for chat in all_chats
            if chat.get("name") and chat.get("chat_id")
        }

        result: dict[str, str] = {}  # chat_id → 显示名
        for target in target_names:
            if target in name_map:  # 精确匹配
                result[name_map[target]] = target
                continue
            matches = [(n, cid) for n, cid in name_map.items() if target in n]
            if len(matches) == 1:
                n, cid = matches[0]
                _cp(f"  ⚡ '{target}' 模糊匹配到群：{n}", _C.YELLOW)
                result[cid] = n
            elif len(matches) > 1:
                _cp(f"  ⚠️  '{target}' 匹配到多个群，请使用更精确的名称：", _C.YELLOW)
                for n, cid in matches:
                    _cp(f"       - {n} ({cid})", _C.YELLOW)
            else:
                _cp(f"  ⚠️  未找到群：'{target}'（确认群名正确且你已加入该群）", _C.YELLOW)

        if not result:
            _cp("❌ 没有匹配到任何群，程序退出", _C.RED)
            sys.exit(1)

        return result

    # ------------------------------------------------------------------
    # 公开方法：拉取新消息
    # ------------------------------------------------------------------

    def fetch_new_messages(
            self,
            token: str,
            chat_id: str,
            since_ts_ms: int,
    ) -> tuple[list[dict], int]:
        """
        拉取指定群 since_ts_ms 之后的新消息。

        Args:
            token:       user_access_token
            chat_id:     群 chat_id
            since_ts_ms: 上次最新消息的毫秒时间戳

        Returns:
            (新消息列表, 最新消息毫秒时间戳)
        """
        start_time = str(since_ts_ms // 1000)
        try:
            resp = self._get(
                f"{_FEISHU_API}/im/v1/messages",
                token,
                params={
                    "container_id_type": "chat",
                    "container_id": chat_id,
                    "start_time": start_time,
                    "page_size": 50,
                },
            )
        except Exception as e:
            _cp(f"[警告] 请求失败: {e}", _C.RED)
            return [], since_ts_ms

        if resp.get("code") != 0:
            code = resp.get("code")
            if code == 99991671:
                _cp("[警告] Token 已失效，将在下次轮询时自动刷新", _C.YELLOW)
            else:
                _cp(f"[警告] 获取消息失败: code={code}, msg={resp.get('msg')}", _C.RED)
            return [], since_ts_ms

        # 飞书 API 返回的消息已按时间正序排列（旧消息在前），无需反转
        items = resp.get("data", {}).get("items") or []

        new_latest = since_ts_ms
        new_msgs = []
        for m in items:
            ts_ms = int(m.get("create_time", "0"))  # create_time 已是毫秒
            if ts_ms > since_ts_ms:
                new_msgs.append(m)
                if ts_ms > new_latest:
                    new_latest = ts_ms

        return new_msgs, new_latest

    # ------------------------------------------------------------------
    # 私有方法：OAuth 授权流程
    # ------------------------------------------------------------------

    def _do_oauth(self) -> str | None:
        """打开浏览器完成 OAuth，返回 user_access_token，失败返回 None"""
        redirect_uri = f"http://localhost:{self.redirect_port}/callback"
        params = urllib.parse.urlencode({
            "app_id": self.app_id,
            "redirect_uri": redirect_uri,
            "scope": _OAUTH_SCOPE,
            "response_type": "code",
            "state": "feishu_monitor",
        })
        auth_url = f"{_FEISHU_AUTHORIZE_URL}?{params}"

        _OAuthCallbackHandler.code = None
        _OAuthCallbackHandler.error = None
        server = HTTPServer(("localhost", self.redirect_port), _OAuthCallbackHandler)
        server.timeout = 1

        _cp(f"\n  🌐 正在打开浏览器进行飞书账号授权...", _C.CYAN)
        _cp(f"  如浏览器未自动打开，请手动访问：\n  {auth_url}\n", _C.GRAY)
        webbrowser.open(auth_url)

        deadline = time.time() + 120
        while time.time() < deadline:
            server.handle_request()
            if _OAuthCallbackHandler.code or _OAuthCallbackHandler.error:
                break
        server.server_close()

        if _OAuthCallbackHandler.error:
            _cp(f"  ❌ 授权失败: {_OAuthCallbackHandler.error}", _C.RED)
            return None
        if not _OAuthCallbackHandler.code:
            _cp("  ❌ 授权超时，未收到回调", _C.RED)
            return None

        _cp("  ✅ 授权码获取成功，正在换取 Token...", _C.GREEN)
        try:
            tenant_token = self._get_tenant_access_token()
            resp = self._post_json(
                _FEISHU_TOKEN_URL,
                {"grant_type": "authorization_code", "code": _OAuthCallbackHandler.code},
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
        except Exception as e:
            _cp(f"  ❌ 换取 Token 异常: {e}", _C.RED)
            return None

        if resp.get("code", -1) != 0:
            _cp(f"  ❌ 换取 Token 失败: {json.dumps(resp, ensure_ascii=False)}", _C.RED)
            return None

        d = resp.get("data", resp)
        now = time.time()
        token_data = {
            "user_access_token": d["access_token"],
            "refresh_token": d["refresh_token"],
            "access_token_expires_at": now + d.get("expires_in", 7200),
            "refresh_token_expires_at": now + d.get("refresh_expires_in", 2592000),
        }
        self._save_token(token_data)
        _cp("  ✅ Token 获取并保存成功\n", _C.GREEN)
        return token_data["user_access_token"]

    # ------------------------------------------------------------------
    # 私有方法：消息打印
    # ------------------------------------------------------------------

    def _print_message(
            self,
            msg: dict,
            chat_name: str,
            token: str,
            download_images: bool,
            image_save_dir: str,
    ) -> dict[str, str]:
        """
        打印消息到终端，若 download_images=True 则下载图片。

        Returns:
            downloaded: {image_key: 绝对路径} 字典，仅包含本次实际下载成功的图片
        """
        msg_type = msg.get("msg_type", "unknown")
        body = msg.get("body")
        content_str = (body.get("content", "{}") if isinstance(body, dict) else "{}")
        sender = msg.get("sender")
        sender = sender if isinstance(sender, dict) else {}
        sender_id = sender.get("id", "?")
        sender_type = sender.get("sender_type", "")
        create_time = self._fmt_time(msg.get("create_time", "0"))
        create_time4file = self._fmt_time(msg.get("create_time", "0"), True)
        msg_id = msg.get("message_id", "")

        display = self._parse_content(msg_type, content_str)
        downloaded: dict[str, str] = {}  # image_key → 绝对路径

        # 先从 mentions 里把名字顺手写入缓存（mentions 天然带 name 字段，不需要额外请求）
        mentions_raw = msg.get("mentions") or []
        for m in mentions_raw:
            if isinstance(m, dict):
                mid = (m.get("id") or {})
                mopen_id = mid.get("open_id", "") if isinstance(mid, dict) else ""
                mname = m.get("name", "")
                if mopen_id and mname and mopen_id not in self._sender_cache:
                    self._sender_cache[mopen_id] = mname

        sender_name = sender_id
        if sender_type == "user" and sender_id.startswith("ou_"):
            sender_name = self._get_sender_name(token, sender_id)

        _cp("─" * 62, _C.GRAY)
        _cp(f"  群：{chat_name}", _C.CYAN)
        _cp(f"  时间：{create_time}  |  ID：{msg_id[:20]}...", _C.GRAY)
        if sender_type == "app":
            _cp("  发送者：[机器人]", _C.MAGENTA)
        else:
            _cp(f"  发送者：{sender_name}", _C.BLUE)

        if msg_type == "image":
            _cp(f"  🖼️  {display}", _C.YELLOW)
            if download_images:
                try:
                    image_key = json.loads(content_str).get("image_key", "")
                    if image_key:
                        prefix = f"{create_time4file}_{sender_name}" if sender_name else create_time
                        saved = self.download_image(token, msg_id, image_key, prefix, image_save_dir)
                        if saved:
                            abs_path = str(Path(saved).resolve())
                            downloaded[image_key] = abs_path
                            _cp(f"      ✅ 已保存：{abs_path}", _C.GREEN)
                except Exception:
                    pass
        elif msg_type == "post":
            _cp(f"  📝 {display}", _C.GREEN)
            if download_images:
                # 富文本中可能内嵌多张图片，逐一下载
                image_keys = self._extract_post_image_keys(content_str)
                for idx, image_key in enumerate(image_keys):
                    prefix = f"{create_time4file}_{sender_name}_p{idx + 1}" if sender_name else f"{create_time}_p{idx + 1}"
                    try:
                        saved = self.download_image(token, msg_id, image_key, prefix, image_save_dir)
                        if saved:
                            abs_path = str(Path(saved).resolve())
                            downloaded[image_key] = abs_path
                            _cp(f"      ✅ 内嵌图片已保存：{abs_path}", _C.GREEN)
                    except Exception:
                        pass
        elif msg_type == "text":
            _cp(f"  📝 {display}", _C.GREEN)
        else:
            _cp(f"  📎 {display}", _C.YELLOW)

        mentions = msg.get("mentions") or []
        if mentions:
            names = []
            for m in mentions:
                if isinstance(m, dict):
                    name = m.get("name") or (m.get("id") or {}).get("open_id", "?")
                    names.append(name)
                elif isinstance(m, str):
                    names.append(m)
            if names:
                _cp(f"  提及：{' '.join('@' + n for n in names)}", _C.GRAY)

        if msg.get("parent_id"):
            _cp(f"  ↩️  回复：{msg['parent_id'][:20]}...", _C.GRAY)

        return downloaded

    # ------------------------------------------------------------------
    # 私有方法：消息内容解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_content(msg_type: str, content_str: str) -> str:
        try:
            content = json.loads(content_str)
        except Exception:
            return f"[解析失败] {content_str[:80]}"

        if msg_type == "text":
            return content.get("text", "")

        elif msg_type == "image":
            return f"[图片] image_key={content.get('image_key', '')}"

        elif msg_type == "post":
            lines = []

            def _extract_post_lines(lang_content: dict) -> None:
                """从单个语言内容块中提取文字行"""
                title = lang_content.get("title", "")
                if title:
                    lines.append(f"[标题] {title}")
                for row in lang_content.get("content", []):
                    if not isinstance(row, list):
                        # 防御：某些情况 row 是字符串或其他类型
                        if isinstance(row, str) and row.strip():
                            lines.append(row.strip())
                        continue
                    row_text = ""
                    for elem in row:
                        if not isinstance(elem, dict):
                            continue
                        tag = elem.get("tag", "")
                        if tag == "text":
                            row_text += elem.get("text", "")
                        elif tag == "a":
                            href = elem.get("href", "")
                            text = elem.get("text", href)
                            row_text += f"[链接:{text}]" if not text else text
                        elif tag == "at":
                            row_text += f"@{elem.get('user_name', elem.get('user_id', ''))}"
                        elif tag == "img":
                            row_text += f"[图片:{elem.get('image_key', '')}]"
                        elif tag == "emotion":
                            row_text += f"[表情:{elem.get('emoji_type', '')}]"
                    if row_text.strip():
                        lines.append(row_text)

            # 飞书富文本结构有两种形态：
            # 形态1: {"post": {"zh_cn": {"title": ..., "content": [...]}}}
            # 形态2: {"zh_cn": {"title": ..., "content": [...]}}  （无外层 "post"）
            # 形态3: {"title": ..., "content": [...]}              （根就是语言内容）
            post_data = content.get("post") or content
            if isinstance(post_data, dict):
                # 判断是语言分组还是直接内容
                has_lang_key = any(k in post_data for k in ("zh_cn", "en_us", "ja_jp"))
                if has_lang_key:
                    lang_content = None
                    for lang in ("zh_cn", "en_us"):
                        if lang in post_data:
                            lang_content = post_data[lang]
                            break
                    if lang_content is None:
                        lang_content = next(iter(post_data.values()), None)
                    if isinstance(lang_content, dict):
                        _extract_post_lines(lang_content)
                else:
                    # 根就是内容块
                    _extract_post_lines(post_data)

            return "\n      ".join(lines) if lines else "[富文本(空)]"

        elif msg_type == "file":
            return f"[文件] {content.get('file_name', '未知')} ({content.get('size', '?')} bytes)"

        elif msg_type == "audio":
            return f"[语音] {content.get('duration', '?')}ms"

        elif msg_type == "video":
            return f"[视频] {content.get('duration', '?')}ms"

        elif msg_type == "sticker":
            return "[表情包]"

        elif msg_type == "share_chat":
            return f"[分享群名片] chat_id={content.get('chat_id', '')}"

        elif msg_type == "share_user":
            return "[分享用户名片]"

        elif msg_type == "system":
            return f"[系统消息] {content.get('content', {}).get('text', '')}"

        else:
            return f"[{msg_type}] {content_str[:100]}"

    # ------------------------------------------------------------------
    # 私有方法：提取富文本中所有内嵌图片的 image_key
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_post_image_keys(content_str: str) -> list[str]:
        """
        从 post 类型消息的 content JSON 中提取所有 img 元素的 image_key。
        支持三种富文本结构形态，返回去重后的 key 列表（保持顺序）。
        """
        keys: list[str] = []
        seen: set[str] = set()

        def _scan_lang_content(lang_content: dict) -> None:
            for row in lang_content.get("content", []):
                if not isinstance(row, list):
                    continue
                for elem in row:
                    if isinstance(elem, dict) and elem.get("tag") == "img":
                        key = elem.get("image_key", "")
                        if key and key not in seen:
                            keys.append(key)
                            seen.add(key)

        try:
            content = json.loads(content_str)
        except Exception:
            return keys

        post_data = content.get("post") or content
        if not isinstance(post_data, dict):
            return keys

        has_lang_key = any(k in post_data for k in ("zh_cn", "en_us", "ja_jp"))
        if has_lang_key:
            lang_content = None
            for lang in ("zh_cn", "en_us"):
                if lang in post_data:
                    lang_content = post_data[lang]
                    break
            if lang_content is None:
                lang_content = next(iter(post_data.values()), None)
            if isinstance(lang_content, dict):
                _scan_lang_content(lang_content)
        else:
            _scan_lang_content(post_data)

        return keys

    # ------------------------------------------------------------------
    # 私有方法：构建回调用的标准消息字典
    # ------------------------------------------------------------------

    def _build_msg_dict(
            self,
            msg: dict,
            chat_name: str,
            token: str,
            downloaded: dict[str, str] | None = None,
    ) -> dict:
        """
        将飞书原始消息 dict 整理为结构化字典，供回调函数使用。

        返回字段：
            msg_type          消息类型（text/post/image/...）
            msg_id            消息 ID
            create_time       时间字符串（已格式化，如 2026-03-28 23:35:47）
            sender_id         发送者 open_id
            sender_name       发送者姓名
            sender_type       发送者类型（user/app）
            chat_name         群名称
            content           解析后的可读文本内容
            image_key         纯图片消息时有效
            image_keys        富文本内嵌图片 key 列表（post 消息时有效）
            downloaded_images {image_key: 绝对路径}，仅包含本次已下载成功的图片；
                              若 download_images=False 或无图片则为空 dict
            raw               原始飞书消息 dict（完整字段）
        """
        msg_type = msg.get("msg_type", "unknown")
        body = msg.get("body")
        content_str = (body.get("content", "{}") if isinstance(body, dict) else "{}")
        sender = msg.get("sender")
        sender = sender if isinstance(sender, dict) else {}
        sender_id = sender.get("id", "?")
        sender_type = sender.get("sender_type", "")
        sender_name = sender_id
        if sender_type == "user" and sender_id.startswith("ou_"):
            sender_name = self._get_sender_name(token, sender_id)

        image_key = ""
        image_keys: list[str] = []
        if msg_type == "image":
            try:
                image_key = json.loads(content_str).get("image_key", "")
            except Exception:
                pass
        elif msg_type == "post":
            image_keys = self._extract_post_image_keys(content_str)

        downloaded = downloaded or {}
        if image_keys is None or len(image_keys) == 0:
            image_keys = list(downloaded.keys())

        return {
            "msg_type": msg_type,
            "msg_id": msg.get("message_id", ""),
            "create_time": self._fmt_time(msg.get("create_time", "0")),
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_type": sender_type,
            "chat_name": chat_name,
            "content": self._parse_content(msg_type, content_str),
            "image_key": image_key,  # 纯图片消息时有效
            "image_keys": image_keys,  # post 消息内嵌图片 key 列表
            "downloaded_images": downloaded or {},  # {image_key: 绝对路径}
            "raw": msg,
        }

    # ------------------------------------------------------------------
    # 私有方法：预加载群成员名字到缓存
    # ------------------------------------------------------------------

    def _preload_members(self, token: str, chat_ids: list[str]) -> None:
        """
        拉取群成员列表，将 open_id → name 写入 _sender_cache。
        使用 im:chat 权限即可，不依赖 contact 权限。
        """
        total = 0
        for chat_id in chat_ids:
            page_token = None
            while True:
                params: dict = {"member_id_type": "open_id", "page_size": 100}
                if page_token:
                    params["page_token"] = page_token
                try:
                    resp = self._get(
                        f"{_FEISHU_API}/im/v1/chats/{chat_id}/members",
                        token,
                        params=params,
                    )
                except Exception as e:
                    _cp(f"  [提示] 预加载群成员失败: {e}", _C.GRAY)
                    break

                if resp.get("code") != 0:
                    _cp(f"  [提示] 预加载群成员失败 code={resp.get('code')}: {resp.get('msg')}", _C.GRAY)
                    break

                data = resp.get("data", {})
                for member in data.get("items") or []:
                    open_id = member.get("member_id", "")
                    name = member.get("name", "")
                    if open_id and name and open_id not in self._sender_cache:
                        self._sender_cache[open_id] = name
                        total += 1

                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")

        if total:
            _cp(f"  ✅ 已预加载 {total} 位群成员姓名\n", _C.GRAY)

    # ------------------------------------------------------------------
    # 私有方法：发送者名称（带缓存）
    # ------------------------------------------------------------------

    def _get_sender_name(self, token: str, open_id: str) -> str:
        if open_id in self._sender_cache:
            return self._sender_cache[open_id]
        try:
            resp = self._get(
                f"{_FEISHU_API}/contact/v3/users/{open_id}",
                token,
                params={"user_id_type": "open_id"},
            )
            if resp.get("code") == 0:
                name = resp.get("data", {}).get("user", {}).get("name", "")
                if name:
                    self._sender_cache[open_id] = name
                    return name
            else:
                code = resp.get("code")
                if code == 99991679:
                    # 权限不足：contact:user.base:readonly 未开通，改用短 ID 兜底
                    # 只打印一次警告，之后从缓存返回短 ID
                    if open_id not in self._sender_cache:
                        _cp(f"[提示] 获取用户名需在飞书后台开通「获取用户基本信息」权限(contact:user.base:readonly)", _C.YELLOW)
                elif code is not None:
                    _cp(f"[提示] 查询用户名失败 code={code}: {resp.get('msg', '')}", _C.GRAY)
        except Exception as e:
            _cp(f"[提示] 查询用户名异常: {e}", _C.GRAY)

        # 兜底：显示 open_id 末 8 位，比完整 ID 可读一些
        short = f"用户_{open_id[-8:]}"
        self._sender_cache[open_id] = short
        return short

    # ------------------------------------------------------------------
    # 私有方法：图片下载
    # ------------------------------------------------------------------

    def download_image(self, token: str, message_id: str, image_key: str, prefix: str, save_dir: str) -> str:
        try:
            save_path = Path(save_dir)
            save_path.mkdir(parents=True, exist_ok=True)
            url = f"{_FEISHU_API}/im/v1/messages/{message_id}/resources/{image_key}?type=image"
            data = self._download_bytes(url, token)
            if not data:
                return ""
            prefix = f"{prefix}_" if prefix else ""
            file_name = f"{prefix}{image_key}.png"
            file_path = save_path / file_name
            file_path.write_bytes(data)
            return FileUtil.recookPath(str(file_path))
        except Exception as e:
            _cp(f"[提示] 图片下载失败: {e}", _C.GRAY)
            return ""

    # ------------------------------------------------------------------
    # 私有方法：tenant_access_token
    # ------------------------------------------------------------------

    def _get_tenant_access_token(self) -> str:
        resp = self._post_json(
            _FEISHU_TENANT_URL,
            {"app_id": self.app_id, "app_secret": self.app_secret},
        )
        if resp.get("code", -1) != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {resp}")
        return resp["tenant_access_token"]

    # ------------------------------------------------------------------
    # 私有方法：Token 持久化
    # ------------------------------------------------------------------

    def _save_token(self, token_data: dict) -> None:
        with open(str(self._token_file), "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False, indent=2)

    def _load_token(self) -> dict | None:
        if not self._token_file.exists():
            return None
        try:
            with open(str(self._token_file), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 私有方法：HTTP 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _get(url: str, token: str, params: dict | None = None) -> dict:
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(f"HTTP {e.code} {e.reason} — URL: {url}\n  响应体: {body}") from None

    @staticmethod
    def _download_bytes(url: str, token: str) -> bytes | None:
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 私有方法：工具函数
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_time(ts_str: str, for_filename: bool = False) -> str:
        try:
            ts = int(ts_str)
            if ts > 1e12:  # 毫秒转秒
                ts = ts / 1000
            if for_filename:
                return datetime.datetime.fromtimestamp(ts).strftime("%Y%m%d_%H%M%S")
            return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ts_str

    def _env(self, key: str, default: str = "") -> str:
        return os.environ.get(key) or default


# ══════════════════════════════════════════════════════════════════
#  直接运行入口（从 .env 读取配置）
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    monitor = FeishuMonitorByOAuth()

    monitor.start(
        chat_names=None,  # 空时自动从 .env 的 FEISHU_CHAT_NAMES 读取
        poll_interval=int(os.environ.get("FEISHU_POLL_INTERVAL", "5")),
        download_images=os.environ.get("FEISHU_DOWNLOAD_IMAGES", "true").lower() == "true",
    )
