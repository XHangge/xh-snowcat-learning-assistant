# XH雪花喵学习助手

XH雪花喵学习助手是一款运行在电脑上的本地 AI 学习软件，使用 Ollama 在本机运行 `qwen2.5:7b` 模型，为啥不用更好的，你可以自己配，，，主包先用这个了，，，，

所有聊天内容默认保存在自己的电脑上，不需要登录，也不会自动上传到云端，是不是很方便喵😁

作者：XHangge

## 功能展示（第一次上传请见谅，，🥺🥺）

### 1. 本地 AI 对话

- 使用本地 Ollama 调用 `qwen2.5:7b` 模型。
- 回答会逐段出现，像打字一样，等待时不会卡住界面。
- 当前会话的历史消息会一起发送给模型，因此雪花喵能够记住本次会话前面聊过的内容。

### 2. 三种学习模式

- **简单说喵～**：用一两句话快速说明最重要的内容，如果是什么简单翻译和名词解释啥的用这个。
- **仔细说喵～**：详细解释知识点，并联系相关内容举一反三，如果是详细了解的事件用这个。
- **教杂狗喵～**：固定分为三段：先用小朋友也能听懂的方式解释，再用专业语言解释，最后给出 3 个延伸问题，深度学习一个很大的知识用这个。

### 3. 雪花喵人设

雪花喵就是是一只可爱的猫咪涅～所以被骂杂狗也不要生气呦～。

### 4. 会话管理

- 使用 SQLite 保存聊天记录。
- 不同会话彼此隔离。
- 可以新建会话、切换会话、重命名会话和删除会话。
- 每个会话第一次提问后，会自动使用问题的前 20 个字作为标题。
- 关闭软件后再次打开，历史记录仍然存在。

### 5. 桌面界面

- 粉色、亮色、暗色三套主题。
- 可以设置用户名；不设置时默认称呼为“杂狗”。
- 可以把窗口固定在其它软件上方。
- 左侧边栏可以打开或关闭。
- 提供可替换的 `assets/icon.png` 占位图标。
- 每次启动会显示支持 xhangge 点 star 的提示弹窗。

## 环境要求

建议使用以下环境：

- macOS 或 Windows
- Python 3.10 或更高版本
- Ollama
- Ollama 模型 `qwen2.5:7b`
- 能够运行 7B 模型的内存和磁盘空间，配置低别跑了，，，，会卡死的

本项目在 macOS Sequoia、Apple Silicon、Python 3.9.6 环境下已经实际测试通过。新电脑建议安装 Python 3.10 或更高版本，以获得更好的第三方库兼容性，，，，

## 安装 Ollama 和模型

### 第一步：安装 Ollama

打开 Ollama 官方下载页面：

<https://ollama.com/download>

根据自己的系统下载安装程序，然后按照安装向导完成安装。

### 第二步：下载模型

打开终端（Windows 用户可以打开 PowerShell），运行：

```bash
ollama pull qwen2.5:7b
```

第一次下载需要一些时间，因为模型文件比较大。看到下载完成或命令返回到输入提示符，通常就表示成功。

### 第三步：检查模型

运行：

```bash
ollama list
```

如果列表中出现 `qwen2.5:7b`，说明模型已经安装好。

Ollama 通常会在后台运行。如果软件提示无法连接 Ollama，可以手动启动服务：

```bash
ollama serve
```

## 安装项目依赖

先把项目下载到电脑，并打开终端进入项目文件夹，请用自己的目录，这里只是主包个人目录示例

### macOS

```bash
cd <你自己的目录喵>
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

每条命令的作用：

1. `cd`：进入项目文件夹。
2. `python3 -m venv .venv`：创建一个只属于本项目的 Python 小环境。
3. `source .venv/bin/activate`：打开这个小环境。
4. `python -m pip install --upgrade pip`：更新安装工具。
5. `python -m pip install -r requirements.txt`：安装项目需要的所有依赖。

### Windows PowerShell

```powershell
cd <你自己的目录喵>
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果 PowerShell 提示不允许执行脚本，可以只对当前用户执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新执行激活命令：

```powershell
.venv\Scripts\Activate.ps1
```

## 运行软件

### macOS

如果当前终端已经激活虚拟环境，运行：

```bash
python main.py
```

也可以不激活虚拟环境，直接运行项目自带的 Python：

```bash
<你自己的目录喵>/xh-snowcat-learning-assistant/.venv/bin/python main.py
```

以后再次启动软件，最简单的完整命令是：

```bash
cd <你自己的目录喵>/xh-snowcat-learning-assistant
.venv/bin/python main.py
```
以主包放在桌面的目录为例：
```bash
cd /Users/xhangge/Desktop/personal_proj/xh-snowcat-learning-assistant
.venv/bin/python main.py
```

### Windows PowerShell

```powershell
python main.py
```

如果没有激活虚拟环境，可以直接运行：

```powershell
.venv\Scripts\python.exe main.py
```

## 运行成功的表现

启动后应该依次看到：

1. 一个写着“支持 xhangge 请帮忙点个 star 喵”的启动弹窗，求🙏star哦谢谢！。
2. 粉色风格的 XH雪花喵学习助手主窗口。
3. 左侧的会话列表、用户名设置、主题选择和学习模式选择。（还有本人随便的测试对话）
4. 底部的输入框。
5. 输入“什么是光合作用？”并按 Enter 后，雪花喵开始逐段回答。

如果模型没有启动，软件会弹出提示，不会因为无法连接而直接崩溃。

## 项目结构说明

```text
xh-snowcat-learning-assistant/
├── main.py                  # 程序入口，负责启动 Qt 应用和主窗口
├── requirements.txt         # Python 依赖清单
├── .gitignore               # Git 不需要上传的文件清单
├── README.md                # 项目说明文档
├── LICENSE                  # MIT 开源协议
├── assets/
│   └── icon.png             # 软件图标占位图，可以替换成自己的图片
├── core/
│   ├── __init__.py          # core Python 包标记文件
│   ├── xhangge_config.py    # 模型、路径、默认设置等全局配置
│   ├── prompts.py           # 雪花喵人设和三种学习模式提示词
│   ├── database.py           # SQLite 数据库操作
│   └── ollama_client.py      # Ollama 请求和流式输出线程
└── ui/
    ├── __init__.py          # ui Python 包标记文件
    ├── themes.py            # 粉色、亮色、暗色主题
    ├── dialogs.py            # 启动、重命名、确认等弹窗
    ├── sidebar.py            # 左侧边栏和会话列表
    ├── chat_area.py          # 聊天气泡、输入框和流式显示
    └── main_window.py        # 主窗口和各模块之间的调度
```

## 数据保存位置

程序会自动创建 `.xh_snowcat` 文件夹保存数据：

- macOS/Linux：`~/.xh_snowcat/`
- Windows：`C:\Users\你的用户名\.xh_snowcat\`

里面主要有：

- `xhangge_chat.db`：聊天会话和消息记录。
- `xhangge_settings.json`：用户名、主题和学习模式等设置。

这些文件只保存在本机。如果删除它们，聊天历史和用户设置也会被删除，请先备份重要内容。

## 也可以自己找自己喜欢的喵娘去软件图标喵
方法：
1. 准备一张 PNG 图片。
2. 把它重命名为 `icon.png`。
3. 用它替换项目中的 `assets/icon.png`。
4. 重新启动程序，或重新打包程序。

建议使用正方形图片哦～，例如 256 x 256 像素。

## 打包成桌面程序

打包前先进入项目目录并激活虚拟环境，然后确认已经安装依赖：

```bash
python -m pip install -r requirements.txt
```

### macOS 打包

```bash
pyinstaller --noconfirm --windowed --name "XH雪花喵学习助手" --add-data "assets:assets" main.py
```

完成后，可以在 `dist/` 文件夹里找到：

```text
dist/XH雪花喵学习助手.app
```

### Windows 打包

在 PowerShell 中运行：

```powershell
pyinstaller --noconfirm --windowed --name "XH雪花喵学习助手" --add-data "assets;assets" main.py
```

完成后，可以在下面的位置找到程序：

```text
dist\XH雪花喵学习助手\XH雪花喵学习助手.exe
```

注意：macOS 和 Windows 的程序需要分别在对应系统上打包，不能指望在 Mac 上直接生成可运行的 Windows 程序。打包后的程序仍然需要用户自己安装 Ollama 和 `qwen2.5:7b`，模型不会被打进安装包。

## 常见问题

### 1. 提示无法连接 Ollama

先确认 Ollama 正在运行：

```bash
ollama serve
```

然后确认模型存在：

```bash
ollama list
```

如果没有模型，运行：

```bash
ollama pull qwen2.5:7b
```

### 2. 提示找不到 `PySide6`

确认已经进入项目目录，并且使用了虚拟环境里的 Python：

```bash
python -m pip install -r requirements.txt
```

macOS 也可以直接使用：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

### 3. 窗口打开后马上关闭

不要双击源代码文件，先打开终端，再运行：

```bash
python main.py
```

这样错误信息会留在终端里，方便定位。

### 4. 第一次回答比较慢

第一次运行模型时，Ollama 需要把模型加载到内存中。等待一会儿是正常现象，后续回答通常会更快。

## 开源协议

本项目使用 MIT License。你可以自由使用、修改和再发布，但请保留原作者的版权声明。

## 作者

Made by xhangge
