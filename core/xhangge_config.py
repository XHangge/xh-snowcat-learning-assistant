# Author: xhangge
# This project is created by xhangge
"""
xhangge_config —— 全局配置中心
这个文件负责存放整个项目的"可调参数"：
- 连接哪个模型、Ollama 服务地址
- 用户数据（数据库、设置文件）保存在哪里
- 用户设置（用户名/主题/学习模式）的读取和保存

其它所有文件需要这些信息时，都从这里导入，做到"改一处，全局生效"。
"""

import json
import os
from pathlib import Path

# ============================================================
# 应用基本信息
# ============================================================
# 软件名称（显示在窗口标题上）
APP_NAME = "XH雪花喵学习助手"
# 作者水印（开源项目署名）
APP_AUTHOR = "xhangge"

# ============================================================
# Ollama 本地大模型相关配置
# ============================================================
# Ollama 默认在本机 11434 端口提供 HTTP 服务
# 如果你的 Ollama 改过端口，只需要修改这里
OLLAMA_BASE_URL = "http://localhost:11434"
# 要调用的本地模型名（需要先执行 ollama pull qwen2.5:7b 下载好）
XHANGGE_MODEL_NAME = "qwen2.5:7b"
# 请求超时设置：(连接超时秒数, 读取超时秒数)
# 连接 5 秒连不上就报错；读取给足 600 秒，因为长回答生成需要时间
XHANGGE_REQUEST_TIMEOUT = (5, 600)

# ============================================================
# 默认用户名
# ============================================================
# 用户没有设置名字时，雪花喵就叫他"杂狗"（爱称喵）
DEFAULT_USERNAME = "杂狗"

# ============================================================
# 数据保存目录
# ============================================================
# 所有用户数据都放在用户主目录下的 ~/.xh_snowcat/ 文件夹里
# 用 pathlib 的 Path.home() 可以自动兼容 macOS 和 Windows 的路径写法
XHANGGE_DATA_DIR = Path.home() / ".xh_snowcat"
# SQLite 数据库文件（保存所有会话和聊天记录）
DB_PATH = XHANGGE_DATA_DIR / "xhangge_chat.db"
# 设置文件（保存用户名/主题/学习模式等偏好，JSON 格式）
SETTINGS_PATH = XHANGGE_DATA_DIR / "xhangge_settings.json"

# ============================================================
# 会话标题规则
# ============================================================
# 每个会话的默认标题；等用户发出第一个问题后，自动取问题前 20 个字替换
DEFAULT_SESSION_TITLE = "新会话喵"
# 标题最大长度（字符数）
SESSION_TITLE_MAX_LEN = 20


def load_xhangge_settings():
    """读取用户设置。

    这段在干什么：
    1. 如果设置文件不存在，返回一份默认设置（粉色主题 + 简单说喵模式）
    2. 如果存在，把文件里的 JSON 读出来，和默认值合并——
       这样以后程序新增设置项时，旧设置文件也不会缺字段报错
    """
    # 默认设置：用户名默认为空（空就代表用默认值"杂狗"）
    default_settings = {
        "username": "",     # 用户昵称，空字符串表示未设置
        "theme": "pink",    # 界面主题：pink 粉色 / light 亮色 / dark 暗色
        "mode": "simple",   # 学习模式：simple / detailed / teach
    }
    try:
        if SETTINGS_PATH.exists():
            # 读取 JSON 文件并转成字典
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 用文件里的值覆盖默认值（dict.update 会合并两个字典）
            default_settings.update(saved)
    except (json.JSONDecodeError, OSError):
        # 文件损坏或读不出来时，静默使用默认值，不让程序崩溃
        pass
    return default_settings


def save_xhangge_settings(settings):
    """保存用户设置到 JSON 文件。

    这段在干什么：
    1. 先确保数据目录 ~/.xh_snowcat 存在（不存在就创建）
    2. 把设置字典写成 JSON 文件（ensure_ascii=False 保证中文原样显示）
    """
    try:
        # parents=True：如果父目录不存在，连父目录一起创建
        XHANGGE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError:
        # 写入失败（比如磁盘满了）也不让程序崩溃，只是设置不会被记住
        pass


def get_font_families():
    """根据操作系统返回合适的字体列表。

    这段在干什么：
    macOS 和 Windows 自带的中文字体不一样，这里按系统挑字体，
    Qt 会按列表顺序依次查找，找到第一个可用的就使用。
    """
    if sys_is_macos():
        # macOS：苹方（PingFang SC）> 冬青黑体 > 无衬线兜底
        return ["PingFang SC", "Hiragino Sans GB", "Helvetica Neue"]
    if sys_is_windows():
        # Windows：微软雅黑 > 黑体 > 无衬线兜底
        return ["Microsoft YaHei", "SimHei", "Segoe UI"]
    # Linux 等其它系统
    return ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "sans-serif"]


def sys_is_macos():
    """判断当前是不是 macOS 系统"""
    return os.name == "posix" and sys_platform() == "darwin"


def sys_is_windows():
    """判断当前是不是 Windows 系统"""
    return os.name == "nt"


def sys_platform():
    """获取操作系统标识（内部小工具函数，方便上面两个函数复用）"""
    import sys
    return sys.platform
