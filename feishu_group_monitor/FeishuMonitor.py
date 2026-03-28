"""
飞书群聊监听工具类
支持:
1. 根据群名自动获取 chat_id
2. 实时监听群消息（轮询方式）
3. 支持文本、图片、富文本等多种消息类型
4. 可选下载图片到本地，保存到 ./cache/{chat_name}/ 目录
5. 支持消息回调，检测到新消息时回调指定函数

使用前提，具体见 README.md:
1. 在飞书开放平台创建应用，获取 app_id / app_secret
2. 开通权限:im:message（读取消息），im:message.group_at_msg（群消息）
   以及 im:resource（下载图片，可选）
3. 将机器人加入目标群聊
4. 初始化 FeishuMonitor 时传入参数或使用 .env 文件配置

示例用法:
    # 方式一：直接传入凭证
    monitor = FeishuMonitor(app_id="cli_xxx", app_secret="xxx")
    
    # 方式二：从 .env 文件读取（推荐）
    monitor = FeishuMonitor()
    
    # 启动监听（不传 callback 则只打印到控制台）
    # 消息打印可以参考 monitor.print_message(...)
    # 解析消息内容可调用 msg_dict:dict = monitor.parse_msg(msg)
    # 图片类消息可进行下载: monitor.download_image(...)
    def my_callback(msg, chat_name):
        print(f"收到消息：{msg}")

    monitor.start_monitor(["群名称 1", "群名称 2"], callback=my_callback)
    
    # 停止监听
    monitor.stop_monitor()
"""

import datetime
import json
import os
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable, Any

import lark_oapi as lark
from dotenv import load_dotenv
from lark_oapi.api.contact.v3 import GetUserRequest
from lark_oapi.api.im.v1 import (
    ListChatRequest,
    ListMessageRequest,
    GetMessageResourceRequest,
)

from util.FileUtil import FileUtil
from util.CommonUtil import CommonUtil


class FeishuMonitor:
    """飞书群聊监听工具类"""

    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None, poll_interval: int = 5, download_images: bool = True):
        """
        初始化工具类
        
        Args:
            app_id: 飞书应用 App ID，如果为 None 则从 .env 文件读取
            app_secret: 飞书应用 App Secret，如果为 None 则从 .env 文件读取
            poll_interval: 轮询间隔（秒），默认 5 秒
            download_images: 是否下载图片，默认 True
        """
        self.cache_dir = FileUtil.create_cache_dir(None, __file__)

        # 加载 .env 文件中的环境变量
        env_path = Path(__file__).parent / ".env"
        load_dotenv(dotenv_path=env_path)
        print(f'dot_env_path={env_path}')

        self.config_path = None
        self.client = None
        self.chat_names: Dict[str, str] = {}  # chat_id -> 群名
        self.chat_ids: Dict[str, str] = {}  # 群名 -> chat_id
        self.latest_ts: Dict[str, int] = {}  # chat_id -> 最新消息时间戳
        self.user_cache: Dict[str, str] = {}  # user_id -> 用户姓名缓存
        self.cfg = {}
        self._monitor_thread: Optional[threading.Thread] = None  # 监听线程
        self._stop_event = threading.Event()  # 停止事件

        # 优先使用传入的参数，如果没有则从环境变量读取
        self.app_id = app_id or os.getenv("FEISHU_APP_ID", "").strip()
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET", "").strip()

        if not self.app_id or self.app_id == "YOUR_APP_ID":
            raise ValueError("Invalid app_id: 请传入 app_id 或在 .env 文件中配置 FEISHU_APP_ID")
        if not self.app_secret:
            raise ValueError("Invalid app_secret: 请传入 app_secret 或在 .env 文件中配置 FEISHU_APP_SECRET")

        self.cfg = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
            "poll_interval": poll_interval,
            "download_images": download_images,
        }

        self._init_client()

    # ─────────────────────────────────────────────
    # 终端颜色支持
    # ─────────────────────────────────────────────
    class C:
        RESET = "\033[0m"
        BOLD = "\033[1m"
        CYAN = "\033[96m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        RED = "\033[91m"
        GRAY = "\033[90m"
        MAGENTA = "\033[95m"
        BLUE = "\033[94m"

    def cprint(self, text, color=C.RESET):
        """彩色打印"""
        print(f"{color}{text}{self.C.RESET}")

    # ─────────────────────────────────────────────
    # 配置加载
    # ─────────────────────────────────────────────

    def _init_client(self):
        """初始化飞书客户端"""
        self.client = (
            lark.Client.builder()
            .app_id(self.cfg["app_id"])
            .app_secret(self.cfg["app_secret"])
            .build()
        )

    # ─────────────────────────────────────────────
    # 核心功能:根据群名获取 chat_id
    # ─────────────────────────────────────────────
    def get_all_chats(self) -> List:
        """获取机器人所在的所有群聊"""
        page_token = None
        all_chats = []

        while True:
            req_builder = ListChatRequest.builder().page_size(100)
            if page_token:
                req_builder = req_builder.page_token(page_token)

            resp = self.client.im.v1.chat.list(req_builder.build())

            if not resp.success():
                self.cprint(f"❌ 获取群列表失败:code={resp.code}, msg={resp.msg}", self.C.RED)
                return []

            items = resp.data.items or []
            all_chats.extend(items)

            if not resp.data.has_more:
                break
            page_token = resp.data.page_token

        return all_chats

    def resolve_chat_ids(self, chat_names: List[str]) -> bool:
        """
        根据群名列表解析出对应的 chat_id
            
        Args:
            chat_names: 要监听的群名称列表
            
        Returns:
            bool: 是否成功解析所有群名
        """
        self.cprint("\n正在根据群名解析 chat_id...", self.C.CYAN)

        # 获取所有群聊
        all_chats = self.get_all_chats()

        if not all_chats:
            self.cprint("⚠️  机器人未加入任何群聊", self.C.YELLOW)
            return False

        # 构建群名到 chat_id 的映射
        success_count = 0
        for chat_name in chat_names:
            found = False
            for chat in all_chats:
                if chat.name == chat_name:
                    self.chat_ids[chat_name] = chat.chat_id
                    self.chat_names[chat.chat_id] = chat_name
                    self.cprint(f"  ✓ {chat_name} -> {chat.chat_id}", self.C.GREEN)
                    found = True
                    success_count += 1
                    break

            if not found:
                self.cprint(f"  ✗ 未找到群名：{chat_name}", self.C.RED)
                self.cprint(f"    提示：请确认机器人已加入该群，且群名正确", self.C.GRAY)

        if success_count == 0:
            self.cprint("\n❌ 未找到任何配置的群聊，请检查群名是否正确", self.C.RED)
            return False

        self.cprint(f"\n成功解析 {success_count}/{len(chat_names)} 个群聊\n", self.C.CYAN)
        return success_count == len(chat_names)

    # ─────────────────────────────────────────────
    # 获取用户信息（带缓存）
    # ─────────────────────────────────────────────
    def get_user_name(self, user_id: str) -> Optional[str]:
        """
        根据 user_id 获取用户姓名，使用缓存避免重复请求
        
        Args:
            user_id: 用户的 open_id 或 user_id
            
        Returns:
            用户姓名，如果获取失败则返回 None
        """
        # 先查缓存
        if user_id in self.user_cache:
            return self.user_cache[user_id]

        try:
            # 调用飞书 API 获取用户信息
            req = GetUserRequest.builder().user_id(user_id).build()
            resp = self.client.contact.v3.user.get(req)

            if resp.success() and resp.data:
                # 优先使用 name，其次使用 nickname
                user_name = resp.data.user.name or resp.data.user.nickname
                if user_name:
                    self.user_cache[user_id] = user_name
                    return user_name
        except Exception as e:
            self.cprint(f"❌ 获取用户信息失败:{e}", self.C.RED)

        return None

    # ─────────────────────────────────────────────
    # 消息内容解析
    # ─────────────────────────────────────────────
    def parse_message_content(self, msg_type: str, content_str: str) -> str:
        """将飞书消息 content JSON 解析为可读文本"""
        try:
            content = json.loads(content_str)
        except Exception:
            return f"[解析失败] {content_str[:100]}"

        if msg_type == "text":
            return content.get("text", "")

        elif msg_type == "image":
            image_key = content.get("image_key", "")
            return f"[图片] image_key={image_key}"

        elif msg_type == "post":
            lines = []
            
            # 飞书 post 消息的结构可能是：{"post": {...}} 或直接就是内容对象
            post_data = content.get("post", {})
            
            lang_content = None
            
            if not post_data and content.get("content"):
                # 如果 content 直接包含内容（扁平结构）
                lang_content = content
            else:
                # 标准结构：尝试多种可能的语言键
                for lang in ("zh_cn", "en_us", "ja_jp"):
                    if lang in post_data:
                        lang_content = post_data[lang]
                        break
                
                # 如果找不到指定语言，尝试第一个值
                if lang_content is None and post_data:
                    lang_content = next(iter(post_data.values()))

            if lang_content:
                title = lang_content.get("title", "")
                if title:
                    lines.append(f"[标题] {title}")
                
                content_rows = lang_content.get("content", [])
                
                for row_idx, row in enumerate(content_rows):
                    row_text = ""
                    # row 可能是一个列表，包含多个元素
                    if isinstance(row, list):
                        for elem in row:
                            tag = elem.get("tag", "")
                            if tag == "text":
                                text = elem.get("text", "")
                                if text:
                                    row_text += text
                            elif tag == "a":
                                href = elem.get("href", "")
                                text = elem.get("text", "")
                                row_text += f"[{text}]({href})"
                            elif tag == "at":
                                user_name = elem.get("user_name", elem.get("user_id", ""))
                                row_text += f"@{user_name}"
                            elif tag == "img":
                                image_key = elem.get("image_key", "")
                                row_text += f"[图片:{image_key}]"
                            elif tag == "media":
                                file_key = elem.get("file_key", "")
                                row_text += f"[媒体:{file_key}]"
                            elif tag == "emotion":
                                emoji_type = elem.get("emoji_type", "")
                                row_text += f"[表情:{emoji_type}]"
                            else:
                                # 其他标签也尝试获取文本
                                text = elem.get("text", "")
                                if text:
                                    row_text += text
                    
                    if row_text.strip():
                        lines.append(row_text)
            
            # 如果解析结果为空，打印原始内容便于调试
            if not lines:
                return "[富文本 (空)]"
            
            return "\n".join(lines)

        elif msg_type == "file":
            return f"[文件] 文件名={content.get('file_name', '未知')} 大小={content.get('size', '?')}B"

        elif msg_type == "audio":
            return f"[语音] 时长={content.get('duration', '?')}ms"

        elif msg_type == "video":
            return f"[视频] 时长={content.get('duration', '?')}ms"

        elif msg_type == "sticker":
            return f"[表情包] file_key={content.get('file_key', '')}"

        elif msg_type == "share_chat":
            return f"[分享群名片] chat_id={content.get('chat_id', '')}"

        elif msg_type == "share_user":
            return f"[分享用户名片] user_id={content.get('user_id', '')}"

        elif msg_type == "system":
            text = content.get("content", {}).get("text", "")
            return f"[系统消息] {text}"

        else:
            return f"[{msg_type}] {content_str[:120]}"

    # ─────────────────────────────────────────────
    # 下载图片（可选）
    # ─────────────────────────────────────────────
    def download_image(self, message_id: str, image_key: str, chat_name: str, prefix: str = None, base_dir: str = None) -> str:
        """
        下载图片到本地，返回保存路径；失败则返回空字符串
        @param message_id: 消息id
        @param image_key:
        @param chat_name: 群聊名
        @param prefix: 下载保存图片时, 要添加的前缀信息
        @param base_dir: 图片要保存的根目录路径, 若为空,则使用self.cache_dir, 然后会自动根据群聊名称创建子目录
        """
        try:
            # 保存图片到 ./cache/{chat_name}/ 目录
            base_dir = self.cache_dir if CommonUtil.isNoneOrBlank(base_dir) else base_dir
            save_dir = f'{base_dir}/{chat_name}'
            FileUtil.create_dir(base_dir)

            req = (
                GetMessageResourceRequest.builder()
                .message_id(message_id)
                .file_key(image_key)
                .type("image")
                .build()
            )
            resp = self.client.im.v1.message_resource.get(req)

            if not resp.success():
                return ""

            prefix = f"{prefix}_" if prefix else ""
            file_name = f"{prefix}{image_key}.png"
            file_path = FileUtil.recookPath(f'{save_dir}/{file_name}')
            with open(str(file_path), "wb") as f:
                f.write(resp.file.read())
            return str(file_path)
        except Exception as e:
            self.cprint(f"❌ 下载图片失败:{e}", self.C.RED)
            return ""

    # ─────────────────────────────────────────────
    # 格式化时间
    # ─────────────────────────────────────────────
    @staticmethod
    def format_time(ts_ms: str, for_filename: bool = False) -> str:
        """
        格式化时间戳
        @param for_filename: True-生成无空格的时间信息, 用于保存的图片文件名
        """
        try:
            ts = int(ts_ms) / 1000
            dt = datetime.datetime.fromtimestamp(ts)
            if for_filename:
                return dt.strftime("%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ts_ms

    def parse_msg(self, msg) -> Dict[str, Any]:
        msg_type = msg.msg_type or "unknown"
        content_str = msg.body.content if msg.body else "{}"
        sender_id = msg.sender.id if msg.sender else "?"
        # 尝试从多个可能的属性中获取发送者姓名
        sender_name = self.get_user_name(sender_id)
        create_time = self.format_time(msg.create_time or "0")
        msg_id = msg.message_id or ""

        display_content = self.parse_message_content(msg_type, content_str)
        image_key = ''
        if msg_type == "image":
            self.cprint(f"  🖼️  {display_content}", self.C.YELLOW)
            if self.cfg.get("download_images"):
                try:
                    content_json = json.loads(content_str)
                    image_key = content_json.get("image_key", "")
                except Exception:
                    pass

        return {
            "msg_type": msg_type,  # 'text' 'post' 'image'
            "create_time": create_time,  # "2022-01-01 00:00:00"
            "sender_name": sender_name,  # 发送者姓名, 比如: "张三"
            "content": display_content,  # 文本消息内容
            "sender_id": sender_id,  # 发送者id
            "msg_id": msg_id,  # 消息id
            "image_key": image_key,  # 图片消息时有效, 可用于下载图片, 见 download_image(...)
        }

    # ─────────────────────────────────────────────
    # 打印消息
    # ─────────────────────────────────────────────
    def print_message(self, msg, chat_name: str):
        """打印消息详情"""
        msg_dict: dict = self.parse_msg(msg)
        msg_type = msg_dict.get("msg_type", "")
        create_time = msg_dict.get("create_time", "")
        display_content = msg_dict.get("content", "")
        sender_id = msg_dict.get("sender_id", "")
        msg_id = msg_dict.get("msg_id", "")
        image_key = msg_dict.get("image_key", "")

        sender_type = msg.sender.sender_type if msg.sender else ""
        # 尝试从多个可能的属性中获取发送者姓名
        sender_name = self.get_user_name(sender_id)
        create_time4file = self.format_time(msg.create_time or "0", True)

        mentions = []
        if msg.mentions:
            for m in msg.mentions:
                name = m.name or m.id.open_id or "?"
                mentions.append(f"@{name}")

        sep = "─" * 60
        self.cprint(sep, self.C.GRAY)
        self.cprint(f"  群:{chat_name}", self.C.CYAN)
        self.cprint(f"  时间:{create_time}  |  消息 ID:{msg_id[:16]}...", self.C.GRAY)

        # 优先显示发送者姓名，如果没有则显示 ID
        if sender_type == "app":
            display_sender = f"[机器人] {sender_name or sender_id}"
        else:
            display_sender = sender_name or sender_id

        self.cprint(f"  发送者:{display_sender}", self.C.BLUE)

        if msg_type in ("text", "post"):
            self.cprint(f"  📝 {display_content}", self.C.GREEN)
        elif msg_type == "image":
            self.cprint(f"  🖼️  {display_content}", self.C.YELLOW)
            if self.cfg.get("download_images"):
                try:
                    if image_key:
                        prefix = f"{create_time4file}_{sender_name}" if sender_name else create_time
                        saved = self.download_image(msg_id, image_key, chat_name, prefix)
                        if saved:
                            self.cprint(f"      ✅ 已保存：{saved}", self.C.GREEN)
                        else:
                            self.cprint("      ⚠️ 图片下载失败", self.C.YELLOW)
                except Exception:
                    pass
        else:
            self.cprint(f"  📎 {display_content}", self.C.YELLOW)

        if mentions:
            self.cprint(f"  提及:{' '.join(mentions)}", self.C.GRAY)

        if msg.parent_id:
            self.cprint(f"  ↩️  回复消息:{msg.parent_id[:16]}...", self.C.GRAY)
        if msg.upper_message_id:
            self.cprint(f"  🔁 转发自:{msg.upper_message_id[:16]}...", self.C.GRAY)

    # ─────────────────────────────────────────────
    # 拉取最新消息
    # ─────────────────────────────────────────────
    def fetch_new_messages(self, chat_id: str, since_ts_ms: int) -> Tuple[List, int]:
        """
        拉取 chat_id 群内 since_ts_ms（毫秒时间戳）之后的消息。
        返回 (messages_list, latest_ts_ms)
        """
        start_ts = since_ts_ms // 1000
        current_ts = int(time.time())

        if start_ts > current_ts:
            start_ts = current_ts - 10

        start_time = str(start_ts)
        end_time = str(current_ts)

        req = (
            ListMessageRequest.builder()
            .container_id_type("chat")
            .container_id(chat_id)
            .start_time(start_time)
            .end_time(end_time)
            .page_size(50)
            .build()
        )

        resp = self.client.im.v1.message.list(req)

        if not resp.success():
            self.cprint(f"[警告] 获取群 {self.chat_names.get(chat_id, chat_id)} 消息失败:{resp.msg}", self.C.RED)
            return [], since_ts_ms

        items = resp.data.items or []
        # 飞书 API 返回的消息已按时间正序排列（旧消息在前，新消息在后），无需反转

        new_latest = since_ts_ms
        new_messages = []
        for msg in items:
            msg_ts = int(msg.create_time or 0) * 1000
            if msg_ts > since_ts_ms:
                new_messages.append(msg)
                if msg_ts > new_latest:
                    new_latest = msg_ts

        return new_messages, new_latest

    # ─────────────────────────────────────────────
    # 启动监听
    # ─────────────────────────────────────────────
    def start_monitor(self, chat_names: Optional[List[str]] = None, callback: Optional[Callable] = None):
        """
        启动群聊消息监听

        Args:
            chat_names: 要监听的群名称列表，如果为 None 则从 .env 文件读取 FEISHU_CHAT_NAMES
            callback: 消息回调函数，接收 (msg, chat_name) 两个参数，如果为 None 则只打印到控制台
        """
        # 如果没有传入群名列表，尝试从环境变量读取
        if chat_names is None or len(chat_names) == 0:
            chat_names_raw = os.getenv("FEISHU_CHAT_NAMES", "").strip()
            if not chat_names_raw:
                raise ValueError("未指定要监听的群名：请传入 chat_names 参数或在 .env 文件中配置 FEISHU_CHAT_NAMES")
            # 按逗号分割群名
            chat_names = [name.strip() for name in chat_names_raw.split(",") if name.strip()]
            if not chat_names:
                raise ValueError("FEISHU_CHAT_NAMES 为空：请在 .env 文件中填写有效的群名称")

        if not self.resolve_chat_ids(chat_names):
            return

        self.cprint("\n" + "═" * 60, self.C.CYAN)
        self.cprint("  🚀 飞书群消息监听器 已启动", self.C.BOLD)
        self.cprint(f"  监听群：{', '.join(chat_names)}", self.C.CYAN)
        self.cprint(f"  轮询间隔：{self.cfg['poll_interval']} 秒", self.C.CYAN)
        self.cprint(f"  图片保存：{'开启' if self.cfg['download_images'] else '关闭'}")
        self.cprint(f"  消息回调：{'已设置' if callback else '未设置（仅控制台输出）'}")
        self.cprint("  按 Ctrl+C 停止\n", self.C.GRAY)
        self.cprint("═" * 60 + "\n", self.C.CYAN)

        now_ms = int(time.time() * 1000) - 5000
        for chat_id in self.chat_ids.values():
            self.latest_ts[chat_id] = now_ms

        self.cprint(f"正在监听以下群聊：", self.C.CYAN)
        for chat_name, chat_id in self.chat_ids.items():
            self.cprint(f"  • {chat_name} ({chat_id})", self.C.GREEN)
        self.cprint("")

        # 重置停止事件
        self._stop_event.clear()

        try:
            while not self._stop_event.is_set():
                for chat_name, chat_id in self.chat_ids.items():
                    try:
                        new_msgs, new_ts = self.fetch_new_messages(chat_id, self.latest_ts[chat_id])
                        self.latest_ts[chat_id] = new_ts

                        for msg in new_msgs:
                            # 打印消息
                            self.print_message(msg, chat_name)

                            # 如果有回调函数，则调用回调
                            if callback:
                                try:
                                    callback(msg, chat_name)
                                except Exception as e:
                                    self.cprint(f"[错误] 回调函数执行失败：{e}", self.C.RED)

                    except Exception as e:
                        self.cprint(f"[错误] 群 {chat_name} 轮询异常：{e}", self.C.RED)

                time.sleep(self.cfg["poll_interval"])

        except KeyboardInterrupt:
            self.cprint("\n\n  👋 监听已停止。", self.C.CYAN)

    # ─────────────────────────────────────────────
    # 辅助方法:列出所有群聊
    # ─────────────────────────────────────────────
    def list_all_chats(self):
        """列出机器人所在的所有群聊（用于调试）"""
        all_chats = self.get_all_chats()

        if not all_chats:
            self.cprint("⚠️  机器人未加入任何群聊", self.C.YELLOW)
            return

        self.cprint(f"\n共找到 {len(all_chats)} 个群聊:\n", self.C.CYAN)
        self.cprint(f"{'序号':<5} {'群名称':<30} {'chat_id':<30}", self.C.GREEN)
        self.cprint("-" * 70, self.C.GRAY)

        for i, chat in enumerate(all_chats, 1):
            name = (chat.name or "（未命名）")[:28]
            self.cprint(f"{i:<5} {name:<30} {chat.chat_id:<30}", self.C.RESET)

        self.cprint("\n将对应群的名称填入 config.ini 的 [monitor] > chat_names 即可开始监听", self.C.CYAN)


if __name__ == "__main__":
    """列出所有群聊"""
    monitor = FeishuMonitor()
    monitor.list_all_chats()
    monitor.start_monitor()
