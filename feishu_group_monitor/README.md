# 飞书群消息监听

实时轮询飞书群聊的新消息，打印到控制台。**无需公网服务器**，本地即可运行。

支持消息类型：文本、图片、富文本（含文字 +@+ 链接）、文件、语音、视频、系统消息等。

---

## 快速开始

### 第一步：安装依赖

```bash
pip install lark-oapi python-dotenv
```

### 第二步：创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/) → **开发者后台** → **创建企业自建应用**
2. 进入应用后，在 **凭证与基础信息** 页获取：
   - `App ID`（形如 `cli_xxxxxxxxxxxxxxx`）
   - `App Secret`

3. 在 **权限管理** → **消息与群组** 中开通以下权限：
   - `im:message`（获取与发送单聊、群组消息）
   - `im:message.group_at_msg`（接收群组中@机器人消息）
   - `im:resource`（可选，下载图片时需要）
   - `im:message.group_msg`（获取群组中所有消息（敏感权限））
   - `contact:user.basic_profile:readonly`（获取用户的基本信息）
   
4. 发布应用（版本审核 → 发布，企业内版本无需人工审核，立即生效）

5. 在飞书群聊中，邀请这个机器人加入群

### 第三步：配置应用凭证

**方式一：使用 `.env` 文件（推荐）**

在项目目录下创建 `.env` 文件：

```bash
# 飞书应用配置（敏感信息）
FEISHU_APP_ID=cli_你的 AppID
FEISHU_APP_SECRET=你的 AppSecret

# 要监听的群名称，多个群用逗号分隔
FEISHU_CHAT_NAMES=群名称 1，群名称 2
```

**方式二：使用系统环境变量**

```bash
# Windows PowerShell
$env:FEISHU_APP_ID="cli_xxx"
$env:FEISHU_APP_SECRET="xxx"
$env:FEISHU_CHAT_NAMES="群名称 1，群名称 2"
python your_script.py

# Linux/macOS
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_CHAT_NAMES="群名称 1，群名称 2"
python your_script.py
```

**方式三：在代码中直接传入**

```python
from feishu_group_monitor.FeishuMonitor import FeishuMonitor

# 直接传入凭证和群名
monitor = FeishuMonitor(app_id="cli_xxx", app_secret="xxx")
monitor.start_monitor(["群名称 1", "群名称 2"])
```

> **注意**：推荐使用 `.env` 文件或系统环境变量管理敏感信息，避免将 `app_id` 和 `app_secret` 提交到代码仓库。

### 第四步：查询群聊名称

```bash
python get_chat_list.py
```

### 第五步：启动监听

```bash
python monitor.py
```

---

## 目录结构

```
feishu_group_monitor/
├── FeishuMonitor.py    # 核心工具类（所有功能）
├── .env                # 环境变量文件（敏感信息，需添加到.gitignore）
├── .env.example        # 环境变量示例文件（可提交到 Git）
├── .gitignore          # Git 忽略配置
├── cache/              # 图片缓存目录（运行时自动创建）
│   └── {chat_name}/    # 每个群独立的图片文件夹
└── README.md
```

---

## 控制台输出示例

```
════════════════════════════════════════════════════════════
  🚀 飞书群消息监听器 已启动
  监听群：oc_xxxxxxxxxx
  轮询间隔：8 秒

────────────────────────────────────────────────────────────
  群：产品研发群
  时间：2026-03-26 21:55:03  |  消息ID：om_xxxxxxxx...
  发送者：ou_xxxxxxxxxx
  📝 大家好，今天的会议改到下午3点
────────────────────────────────────────────────────────────
  群：产品研发群
  时间：2026-03-26 21:56:10  |  消息ID：om_yyyyyyyy...
  发送者：ou_yyyyyyyyyy
  🖼️  [图片] image_key=img_xxxxxxxx
```

---

## 常见问题

**Q: 报错 `code=99991671, msg=...tenant_access_token...`**  
A: 检查 app_id / app_secret 是否正确，应用是否已发布。

**Q: 获取到消息但 sender 显示的是 user_id 不是名字**  
A: 飞书 `list message` 接口默认返回 open_id，程序会自动调用「获取用户信息」接口获取用户姓名并缓存。

**Q: 轮询拉不到消息**  
A: 确认机器人已被加入目标群聊，且应用已开通 `im:message` 权限并发布。

**Q: 如何监听多个群？**  
A: 在 `.env` 文件的 `FEISHU_CHAT_NAMES` 中填写多个群名，用逗号分隔；或在代码中传入群名列表。

**Q: 配置文件的优先级是怎样的？**  
A: 代码中传入的参数 > 系统环境变量 > .env 文件。推荐使用 `.env` 文件或系统环境变量管理敏感信息。

---

## 技术说明

- 使用 **飞书 IM v1 消息列表接口**（`GET /im/v1/messages`）轮询拉取
- 首次启动以当前时间为基准，只接收**启动后的新消息**，不补历史
- 每个群独立维护最新消息时间戳，避免重复打印
- 飞书 API 限频：100次/分钟（8秒一次轮询远未触达上限）
