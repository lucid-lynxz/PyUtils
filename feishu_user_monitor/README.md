# 飞书群消息监听（用户身份版）

以**你自己的飞书账号**身份读取群消息，**无需机器人入群**。  
可监听你加入的任意群，包括：外部群、无管理权限的群、跨企业群等。

---

## 飞书应用配置（首次必做）

### 第一步：创建应用

1. 前往 [飞书开放平台](https://open.feishu.cn/) → **创建企业自建应用**
2. 获取 `App ID` 和 `App Secret`（在「凭证与基础信息」页面）

---

### 第二步：申请权限

进入应用 → **权限管理** → 搜索并开通以下权限：

| 权限标识 | 后台中文名 | 用途 |
|----------|-----------|------|
| `im:chat` | 获取与更新群组信息 | 拉取群列表、解析群名 |
| `im:message` | 获取与发送单聊、群组消息 | 读取群消息（核心权限）|
| `im:message:readonly` | 读取单聊、群组消息 | 读取群消息（只读备选）|
| `contact:user.base:readonly` | 获取用户基本信息 | 显示发送者姓名（可选）|

> ⚠️ **权限变更后必须重新发布应用才能生效**（见第三步）

---

### 第三步：安全设置

进入应用 → **安全设置** → 重定向 URL 中添加：

```
http://localhost:9721/callback
```

> 如果你修改了 `FEISHU_REDIRECT_PORT`，端口号要对应修改。

---

### 第四步：发布应用

进入应用 → **应用发布** → 创建版本 → 提交发布。

> ⚠️ **每次修改权限后都需要重新发布**，否则新权限不生效。  
> 自建应用发布审核通常秒过（企业管理员审批）。

---

### 第五步：重新授权（权限变更后必做）

修改了应用权限并重新发布后，本地缓存的 token 是旧权限换取的，需要删掉重新授权：

```bash
# 删除旧 token
rm feishu_user_monitor/.token.json
# Windows:
del feishu_user_monitor\.token.json
```

然后重新运行，会自动弹出浏览器进行授权。

---

## 配置方式

### 创建 `.env` 文件

```bash
cp feishu_user_monitor/.env.example feishu_user_monitor/.env
```

编辑 `.env`：

```env
FEISHU_APP_ID=cli_你的AppID
FEISHU_APP_SECRET=你的AppSecret

# 直接运行 monitor.py 时填写群名（支持逗号分隔多个）
FEISHU_CHAT_NAMES=产品研发群,客户支持群

# 以下为可选配置
# FEISHU_POLL_INTERVAL=8          # 轮询间隔（秒），默认 8
# FEISHU_DOWNLOAD_IMAGES=false    # 是否下载图片，默认 false
# FEISHU_IMAGE_SAVE_DIR=./downloaded_images
# FEISHU_REDIRECT_PORT=9721       # OAuth 回调端口，默认 9721
```

> **优先级**：函数参数 > `os.environ` 环境变量 > `.env` 文件

---

## 使用方式

### 方式一：直接运行（从 .env 读取配置）

```bash
python feishu_user_monitor/FeishuMonitorByOAuth.py
```

首次运行自动弹出浏览器，用你的飞书账号登录授权即可。

### 方式二：实例化 FeishuMonitorByOAuth 类（推荐）

```python
from feishu_user_monitor.FeishuMonitorByOAuth import FeishuMonitorByOAuth

monitor = FeishuMonitorByOAuth(
    app_id     = "cli_xxx",   # 可选，不传则读 .env
    app_secret = "xxx",       # 可选，不传则读 .env
)

# 可选：定义消息回调
def on_message(msg: dict, chat_name: str):
    print(f"[{chat_name}] {msg['sender_name']}: {msg['content']}")
    # msg 字段说明：
    #   msg_type    消息类型（text/post/image/...）
    #   msg_id      消息 ID
    #   create_time 时间字符串（如 2026-03-28 23:35:47）
    #   sender_id   发送者 open_id
    #   sender_name 发送者姓名
    #   sender_type 发送者类型（user/app）
    #   chat_name   群名称
    #   content     解析后的可读文本内容
    #   image_key         纯图片消息时有效
    #   image_keys        富文本内嵌图片 key 列表（post 消息时有效）
    #   downloaded_images {image_key: 绝对路径}，仅包含本次已下载成功的图片
    #                     若 download_images=False 或无图片则为空 dict
    #   raw               原始飞书消息 dict（完整字段）

# 开始监听
monitor.start(
    chat_names      = ["产品研发群", "客户支持群"],  # 群名，支持模糊匹配
    poll_interval   = 8,                             # 轮询间隔（秒），默认 8
    download_images = False,                         # 是否下载图片，默认 False
    image_save_dir  = "./downloaded_images",         # 图片保存目录
    callback        = on_message,                    # 可选，不传则只打印到控制台
)
```

**FeishuMonitorByOAuth 类主要方法：**

| 方法 | 说明 |
|------|------|
| `start(chat_names, callback, ...)` | 启动消息监听（阻塞，Ctrl+C 停止），callback 可选 |
| `list_chats()` | 列出你加入的所有群（含 chat_id） |
| `get_valid_token()` | 获取有效 token，自动触发 OAuth 或刷新 |
| `fetch_new_messages(token, chat_id, since_ts_ms)` | 拉取指定群的新消息 |
| `resolve_chat_ids(token, target_names)` | 群名 → chat_id 解析 |

### 查看你加入的群（确认群名）

```python
from feishu_user_monitor.FeishuMonitorByOAuth import FeishuMonitorByOAuth

FeishuMonitorByOAuth().list_chats()
```

---

## 目录结构

```
feishu_user_monitor/
├── FeishuMonitorByOAuth.py  # 核心工具类（OAuth + 监听 + 群管理全功能）
├── .env.example             # 配置模板（复制为 .env 使用）
├── .env                     # 你的配置（勿提交 git）
├── .token.json              # 自动生成，存储 token（勿提交 git）
└── README.md
```

---

## Token 机制

| Token | 有效期 | 处理方式 |
|-------|--------|----------|
| `user_access_token` | 2 小时 | 程序自动刷新，无感知 |
| `refresh_token` | 30 天 | 30 天内无需重新扫码 |

> `refresh_token` 过期后需删除 `.token.json` 重新授权。

---

## 常见问题

**Q: 报错 `99991679` 权限不足？**  
A: 检查应用是否已开通所需权限（见上方权限表），并**重新发布应用**。发布后删除 `.token.json` 重新运行以获取带新权限的 token。

**Q: 报错 `230001 end_time is earlier than start_time`？**  
A: 通常是 token 状态异常，删除 `.token.json` 重新运行即可。

**Q: 群名匹配不到？**  
A: 运行 `get_chat_list.py` 查看实际群名，支持模糊匹配（群名包含关键词即可）。

**Q: 报错 Token 无效 / 需要重新授权？**  
A: 删除 `.token.json`，重新运行触发浏览器授权。

**Q: 外部群、跨企业群能监听吗？**  
A: 能，只要你的飞书账号在群里即可，无需机器人权限。

**Q: 修改轮询间隔需要停止程序吗？**  
A: 需要，`Ctrl+C` 停止后修改 `.env` 中的 `FEISHU_POLL_INTERVAL` 再重启。
