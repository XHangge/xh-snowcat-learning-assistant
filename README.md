# snowcat · XH雪花喵学习助手 v1.0

snowcat（XH雪花喵学习助手）是一款运行在自己电脑上的 AI 学习助手。可爱的猫娘「雪花喵」snowcat 可以陪你聊天答疑，还能自己动手查资料、翻你的自定义知识库、整理学习文档、还有帮你写文件和跑代码。

所有数据默认只保存在本机sqlite，不需要登录，也不会自动上传云端。

作者：Made by xhangge 💖

## v1.0 都有什么

v1.0 是一次大升级！一共五大模块：

### 1. 💬 普通聊天 + 三种学习模式

- 云端api自己配即可喵！本地 Ollama 跑 `qwen2.5:7b` 或其它本地，回答逐字打出（打字机效果），等待时不卡界面。
- 三种学习模式（左侧边栏最下方切换）：
  - **简单说**：最简单最直白最一针见血的说明白。
  - **仔细说**：给你往死里掰开揉碎了讲并且扩展的讲
  - **教XX~**：固定三段——先最通俗易懂最直白的讲，再上专业术语的讲，最后给 3 个延伸问题给你扩展。
- 多会话管理：新建 / 切换 / 重命名 / 删除

### 2. 📖 学习文档 Skill（把聊天变成复习资料）

- 输入框上方点「📖 学习文档喵」，或者消息里直接说「生成学习文档」「浅浅学喵」。
- 四种产物：
  - 📄 普通学习文档（结构化的 md）
  - 🌸 浅浅学喵：10–20 题问答集
  - 📖 中中学喵：20–30 题
  - 🎓 重重学喵：30–50 题
- 只整理「聊过的内容」，不凭空编造；之前生成过的旧资料不会被打包抄进新文档。
- 每份资料下方有「💾 导出喵」按钮，一键存成 `.md` 文件（选目录 → 可爱进度条 → 导出成功喵）。

### 3. 📚 知识库 RAG（让雪花喵翻你的私人文档）

- 点标题栏 📚 打开知识库窗口：建库（最多 10 个）、导入文件（拖拽或选文件都行，支持 pdf / txt / md / docx）。
- 单库容量 30MB；每个会话最多绑定 3 个库；绑定后打开「🔍 回答时翻知识库」，提问会自动检索最相关的资料片段再作答。
- 检索用的向量化模型是本地 Ollama 的 `bge-m3`——所以**用知识库时 Ollama 要开着**。
- 删文件按「文件」精确删（只删保存的副本）。

### 4. 🤖 Agent 模式（雪花喵自己动手干活）

- 输入框上方点开「🤖 Agent 喵」胶囊开关进入（每个会话各自记住自己的模式）。
- 七个工具：联网搜索（DuckDuckGo 免费可用，Tavily 可选不过要自己配 apikey）、查知识库、读文件、写文件、删文件、跑命令、经验笔记。
- **三道防线，hitp＆sandbox 机制实现 snowcatharness**：
  1. 所有改文件、跑命令只发生在你在设置里选的「工作目录」里，越界直接拦下；
  2. 命令有关机级黑名单 + 超时掐断；
  3. 写文件 / 删文件 / 跑命令每一次都会**弹窗让你点同意**（不同意就放弃，模型会老实汇报）。
- 干活过程实时显示在「行动卡片」上（🔍 搜索了什么、✏️ 写了什么、⌨️ 跑了什么）。
- 自进化：Agent 觉得有用的经验会记进笔记，下次任务开场自动带上。

### 5. ⚙️ 模型随便换（本地 / 在线二选一）

- **本地**：设置 → 🧠 模型喵 → 选模型 → 没下载的点「⬇️ 一键下载喵」（带可爱进度条）。
- **在线**：填 OpenAI 兼容接口（DeepSeek、通义千问、Moonshot 等都行）→ 点「保存并使用」会**先真实测试一次**，通过才启用——地址打错、Key 不对都不会把你卡死，本地模型继续顶上。
- 本地和在线互斥，切换即时生效，不用重启。
- 设置窗还有：🎨 外观（三套主题即时换肤）、👤 我的信息（昵称 + 上传圆形头像）、🤖 Agent（工作目录、沙箱超时）、🔍 搜索（引擎和 Key）、ℹ️ 关于。

### 界面

- 圆角矩形窗口 + 三套主题（粉色 / 亮色 / 暗色），粉发猫娘形象贯穿全软件（头像、图标、启动画面）。
- 启动时有 splash 画面：猫娘大头像 + 「snowcat～」粉色艺术字。
- 聊天区自动吸底：打开会话停在最新消息，流式输出自动跟随；你往上翻历史时会暂停跟随，不打扰阅读。

## 环境要求

- macOS（Apple Silicon 实测通过，不过版本比较低只能有部分功能）或 Windows
- Python **3.10 或更高**（3.12.7 实测通过；LangGraph 系列要求 ≥3.10）
- Ollama + 两个模型：`qwen2.5:7b`（对话）和 `bge-m3`（知识库向量化）
- 能跑 7B 模型的内存和磁盘

## 安装 Ollama 和模型

### 第一步：安装 Ollama

去 <https://ollama.com/download> 下载对应系统的安装包，按向导装好。

### 第二步：下载两个模型

打开终端运行：

```bash
ollama pull qwen2.5:7b #或者其它也都行
ollama pull bge-m3
```

模型文件比较大（qwen2.5:7b 约 4.7GB），第一次需要等一会。也可以在软件里点「⬇️ 一键下载喵」。

### 第三步：检查

```bash
ollama list
```

列表里出现 `qwen2.5:7b` 和 `bge-m3` 就绪。Ollama 平时在后台常驻；软件提示连不上时可以手动启动：

```bash
ollama serve
```

## 安装项目依赖

先把项目下载到电脑，打开终端进入项目文件夹。

### macOS

```bash
cd /path/to/xh-snowcat-learning-assistant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

每条命令的作用：

1. `cd`：进入项目文件夹。
2. `python3 -m venv .venv`：创建只属于本项目的 Python 虚拟环境。
3. `source .venv/bin/activate`：激活它。
4. `python -m pip install --upgrade pip`：升级安装工具。
5. `python -m pip install -r requirements.txt`：装齐全部依赖（版本都已锁定）。

### Windows PowerShell

```powershell
cd C:\Users\你的用户名\Desktop\xh-snowcat-learning-assistant
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果 PowerShell 提示不允许执行脚本，先对当前用户执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 运行软件

### macOS（推荐：双击启动）

项目里自带一个叫 **snowcat** 的启动器（`snowcat.app`），双击它即可：

- 菜单栏和 Dock 会显示 **snowcat** 和猫娘图标（而不是「Python」）；
- 它会自动用项目的虚拟环境原生（arm64）运行，双击和命令行行为完全一致。

把 `snowcat.app` 拖进程序坞、或在桌面创建替身，就是你的快捷方式。

命令行启动也可以：

```bash
cd /path/to/xh-snowcat-learning-assistant
.venv/bin/python main.py
```

### Windows PowerShell

```powershell
python main.py
```

（没激活虚拟环境时用 `.venv\Scripts\python.exe main.py`）

## 运行成功的表现

1. 先看到启动画面：悬浮的猫娘大头像 + 「snowcat～」粉色艺术字；
2. 出现「支持 xhangge 请帮忙点个 star 喵」弹窗；
3. 圆角的主窗口出现（默认粉色主题）；
4. 输入「什么是光合作用？」按 Enter，雪花喵开始逐字回答。

Ollama 没开也不会崩溃，会有友好的提示弹窗告诉你怎么办。

## 快速上手

1. **聊天**：随便问，左侧边栏换学习模式试试三种讲法。
2. **学习文档**：聊两轮后点「📖 学习文档喵」→ 浅浅学喵，得到一份问答集，点「💾 导出喵」存成文件。
3. **知识库**：点 📚 → 新建库 → 拖一个 pdf/txt 进去 → 绑定到当前会话 → 打勾「回答时翻知识库」→ 问文件里的内容。
4. **Agent**：⚙️ 设置 → 🤖 Agent 喵 → 选一个工作目录（建议建个空文件夹）→ 聊天区点开「🤖 Agent 喵」→ 说「在工作目录里创建一个学习计划.txt」→ 确认弹窗点同意/拒绝都试试。
5. **换模型**：⚙️ 设置 → 🧠 模型喵 → 一键下载别的本地模型，或填在线 API。

## 项目结构说明（目前架构有点乱，后续会对当前架构进行优化，现在能跑就行，，，，）

```text
xh-snowcat-learning-assistant/
├── main.py                       # 程序入口（splash → 主窗口 → 启动检查 + 状态预探测）
├── requirements.txt              # 依赖清单（版本锁定）
├── snowcat.spec                  # PyInstaller 打包配置（含体积优化排除表）
├── snowcat.app/                  # macOS 双击启动器（菜单栏显示 snowcat）
├── local_model/                  # 本地 gguf 模型目录（「一键部署」下载到这里）
├── assets/
│   ├── icon.png / icon.icns      # 应用图标（猫娘）
│   ├── xhangge_splash_text.png   # 启动画面艺术字
│   ├── xhangge_cursor_*.png      # 粉色光标（猫爪 / 小手 / I型 / 双向箭头 / 对勾）
│   └── xhangge_catgirl/          # 猫娘形象素材（头像/立绘/跑步动画）
├── config/                       # 配置层：全局参数 + 全部提示词
│   ├── xhangge_settings.py       #   路径、上限、默认值、gguf 下载地址
│   └── xhangge_prompts.py        #   人设、学习模式、技能、Agent、RAG、重排模板
├── models/                       # 数据层：SQLite + 数据结构
│   ├── xhangge_db.py             #   会话/消息/知识库/模型配置 全部表操作
│   └── xhangge_schemas.py        #   数据类（知识库信息、检索片段等）
├── services/                     # 服务层：所有 AI 逻辑（界面不碰这些）
│   ├── xhangge_chat_service.py   #   聊天线程（流式 + 错误翻译）
│   ├── xhangge_llm_router.py     #   模型路由（本地/在线互斥、热切换）
│   ├── xhangge_ollama_deploy.py  #   Ollama 安装 / 模型下载 / 状态探测（带缓存）
│   ├── xhangge_skill_service.py  #   学习文档技能（关键词识别、消息组装）
│   ├── xhangge_kb_service.py     #   知识库（解析/语义切块/混合检索+重排/删除）
│   └── xhangge_agent_service.py  #   Agent（七工具、围栏、沙箱、HITL）
├── gui/                          # 界面层：只负责显示和转发事件
│   ├── xhangge_main_window.py    #   主窗口（圆角、调度、信号中枢、主题淡入淡出）
│   ├── xhangge_chat_area.py      #   聊天气泡、输入栏、工具条、吸底滚动
│   ├── xhangge_sidebar.py        #   侧边栏（会话列表 + 学习模式）
│   ├── xhangge_settings_page.py  #   ⚙️ 设置窗口（六页）
│   ├── xhangge_kb_page.py        #   📚 知识库窗口 + 绑定会话弹窗
│   ├── xhangge_dialogs.py        #   各类可爱弹窗（含 HITL 确认）
│   ├── xhangge_themes.py         #   三套主题（模板 + 配色生成）
│   ├── xhangge_cute_progress.py  #   可爱进度条
│   ├── xhangge_avatars.py        #   圆形头像工具 + 粉色光标
│   ├── xhangge_resize.py         #   无边框窗口拖边缘调整大小
│   └── xhangge_splash.py         #   启动画面
└── tools/                        # 工具
    ├── xhangge_eval.py           #   RAG 检索召回评测脚本
    └── xhangge_eval_data.py      #   评测语料 + 100 条 QA
```

分层规矩：`gui` 只显示和转发；AI 逻辑全在 `services`；数据全在 `models`；参数和提示词全在 `config`。想改行为先去对应层找，不会迷路喵。

## 数据保存位置

程序自动创建 `~/.xh_snowcat/`（Windows 在 `C:\Users\你的用户名\.xh_snowcat\`）：

| 文件 / 目录 | 内容 |
|---|---|
| `xhangge_chat.db` | 会话、消息、知识库档案、模型配置 |
| `xhangge_settings.json` | 主题、模式、工作目录等设置 |
| `xhangge_chroma/` | 知识库向量（ChromaDB） |
| `xhangge_kb_files/` | 导入文件的**副本**（删知识库只删这里的副本） |
| `xhangge_agent_notes.md` | Agent 的自进化经验笔记 |
| `xhangge_user_avatar.png` | 你上传的圆形头像 |

这些只在本机。删除它们会丢对应数据，请先备份重要内容。

## 打包成桌面程序

macOS（进入项目目录、激活虚拟环境后）：

```bash
pyinstaller snowcat.spec --noconfirm
```

完成后在 `dist/snowcat.app` 拿到自包含的应用（约 240MB），拷到别的 Mac（需同样装好 Ollama 和模型）也能跑。spec 里维护着一张「运行时不会加载」的重依赖排除表（onnxruntime、kubernetes、torch 等），能给包省下约 200MB。

Windows 用户可以用：

```powershell
pyinstaller --noconfirm --windowed --name snowcat --add-data "assets;assets" main.py
```

注意：打包产物仍需要用户自己安装 Ollama 和模型，模型不会打进安装包。

## 常见问题

### 1. 提示无法连接 Ollama

```bash
ollama serve
ollama list
```

没有模型就点设置里的「⬇️ 一键部署喵」，或在终端 `ollama pull qwen2.5:7b`。用知识库还需要 `bge-m3`。手动装 Ollama：Windows 在 cmd 运行 `irm https://ollama.com/install.ps1 | iex`，macOS 用 `brew install ollama`。

### 2. 在线 API 保存不上

「保存并使用」会先真实测试，失败会列出常见原因：

1. 接口地址少了结尾的 `/v1`（DeepSeek 应填 `https://api.deepseek.com/v1`）；
2. 模型名打错（DeepSeek 是 `deepseek-chat`）；
3. Key 不对或没额度。

测试不过就不会启用，本地模型继续可用，聊天不会被卡死。

### 3. 知识库检索不准 / 回答不好

- 确保已经「📎 绑定会话」把库绑到了当前会话，并在「当前会话喵」卡片打开了「🔍 回答时翻知识库」。
- 检索默认走「向量召回 + BM25 关键词 + RRF 融合 + 本地大模型重排」；想换更准的交叉编码器重排，改 `config/xhangge_settings.py` 里的 `XHANGGE_RERANK_MODE`。
- 导入新文档会自动按句子边界切块（不再硬切句子），如果之前导入过，删掉重导一次更准。

### 4. Agent 说「用户还没选工作目录」

这是安全设计：改文件、跑命令必须先在 ⚙️ 设置 → 🤖 Agent 喵 里选一个工作目录（建议专门建一个空文件夹），Agent 只能动这个目录里的东西。

### 5. 找不到 PySide6

确认在项目目录里、用的是虚拟环境的 Python，然后重装依赖：

```bash
python -m pip install -r requirements.txt
```

### 6. 双击源码文件打不开

不要双击 `.py` 文件。macOS 双击项目里的 `snowcat.app`，或按「运行软件」一节的命令行方式启动，报错信息才看得见。

### 7. 第一次回答慢 / 知识库导入慢

首次运行 Ollama 要把模型加载进内存；知识库导入要把文档切块并向量化（本地 bge-m3 逐批跑），大文件等一会儿是正常的。Ollama 和模型状态只在启动时、切换模型时各探测一次，设置窗直接读缓存，不会每次打开都卡一下。

## 开源协议

本项目使用 MIT License。你可以自由使用、修改和再发布，但请保留原作者的版权声明。

## 作者

Made by xhangge 💖

觉得雪花喵可爱的话，去 GitHub 仓库点一颗小星星喵 🌟
