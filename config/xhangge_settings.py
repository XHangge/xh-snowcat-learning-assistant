# Author: xhangge
# This project is created by xhangge
"""
xhangge_settings —— 全局配置中心
这个文件负责存放整个项目的"可调参数"：
- 连接哪个模型、Ollama 服务地址
- 用户数据（数据库、向量库、文件副本、设置文件）保存在哪里
- 知识库的各种上限（几个库、单库多大、一个会话能绑几个）
- Agent 沙箱的安全参数
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
# 开源仓库地址（显示在设置窗口的「关于喵」页里，方便别人去点 star）
XHANGGE_GITHUB_URL = "https://github.com/XHangge/xh-snowcat-learning-assistant"

# ============================================================
# Ollama 本地大模型相关配置
# ============================================================
# Ollama 默认在本机 11434 端口提供 HTTP 服务
# 如果你的 Ollama 改过端口，只需要修改这里
OLLAMA_BASE_URL = "http://localhost:11434"
# 默认调用的本地模型名（用户可以在设置窗口里换成别的）
XHANGGE_MODEL_NAME = "qwen2.5:7b"
# 请求超时设置：(连接超时秒数, 读取超时秒数)
# 连接 5 秒连不上就报错；读取给足 600 秒，因为长回答生成需要时间
XHANGGE_REQUEST_TIMEOUT = (5, 600)

# 一键部署面板里可选的模型（都是消费级电脑跑得动的）
XHANGGE_PULLABLE_MODELS = [
    ("qwen2.5:7b", "通义千问 2.5 · 7B（推荐，约 4.7GB）"),
    ("qwen2.5:3b", "通义千问 2.5 · 3B（更快更省，约 1.9GB）"),
    ("qwen2.5:1.5b", "通义千问 2.5 · 1.5B（老电脑也能跑，约 1GB）"),
    ("deepseek-r1:7b", "DeepSeek R1 · 7B（会思考的推理模型，约 4.7GB）"),
    ("llama3.2:3b", "Llama 3.2 · 3B（英文更强，约 2GB）"),
    ("gemma2:2b", "Gemma 2 · 2B（谷歌出品，约 1.6GB）"),
]

# 本地模型 gguf 文件目录（放在项目文件夹下，手动下载的模型都存这里）
XHANGGE_LOCAL_MODEL_DIR = Path(__file__).resolve().parent.parent / "local_model"

# 各模型的 gguf 下载地址（HuggingFace，Q4_K_M 量化）。文件名/地址如有变动改这里即可。
XHANGGE_MODEL_GGUF_URLS = {
    "qwen2.5:7b": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf",
    "qwen2.5:3b": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
    "qwen2.5:1.5b": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    "deepseek-r1:7b": "https://huggingface.co/unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
    "llama3.2:3b": "https://huggingface.co/QuantFactory/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct.Q4_K_M.gguf",
    "gemma2:2b": "https://huggingface.co/QuantFactory/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it.Q4_K_M.gguf",
}

# Ollama 安装程序下载地址（按平台）
XHANGGE_OLLAMA_INSTALL_URLS = {
    "win32": "https://ollama.com/download/OllamaSetup.exe",
    "darwin": "https://ollama.com/download/Ollama-darwin.zip",
}

# ============================================================
# 知识库（RAG）相关配置
# ============================================================
# 做向量化用的模型：固定走本地 Ollama 的 bge-m3。
# 为什么不跟着"在线 API"开关变：各家在线接口的向量格式不统一，
# 而且把你的私人文档发到云端做向量化并不合适。
# 代价是——用知识库时 Ollama 必须开着。
XHANGGE_EMBED_MODEL = "bge-m3"
# bge-m3 输出的向量维度（建 Chroma collection 时要对上）
XHANGGE_EMBED_DIM = 1024
# 向量化时一次 HTTP 请求塞多少块（越大越省网络往返、导入越快）
XHANGGE_EMBED_BATCH = 64

# 最多能建几个知识库（硬限制，超了直接拒绝）
XHANGGE_MAX_KB_COUNT = 10
# 单个知识库的容量上限（硬限制）：30MB
XHANGGE_MAX_KB_BYTES = 30 * 1024 * 1024
# 一个会话最多能同时绑定几个知识库
# 为什么是 3：每多绑一个就多一轮检索，塞进上下文的片段也更多，
# 模型注意力会被稀释、速度变慢、回答反而更糊。3 个是"够用"和"不糊"的平衡点。
XHANGGE_MAX_KB_PER_SESSION = 3
# 支持拖进来的文件类型
XHANGGE_ALLOWED_DOC_EXTS = (".pdf", ".txt", ".md", ".docx")
# 切块参数：每块最多多少字、相邻块之间重叠多少字
# 重叠是为了避免一句话正好被切断，导致语义丢失
XHANGGE_CHUNK_SIZE = 512
XHANGGE_CHUNK_OVERLAP = 128
# bge-m3 的查询侧指令：查询和文档不对称，查询前加这句能明显提升检索相关度
XHANGGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
# 检索参数：每个知识库各取几段，最后全局保留几段
XHANGGE_TOP_K_PER_KB = 5
XHANGGE_TOP_K_FINAL = 8

# 混合检索 + 重排（RAG 优化）参数
XHANGGE_DENSE_TOP_K = 25       # 每个知识库"向量召回"取多少候选（供 RRF 融合）
XHANGGE_SPARSE_TOP_K = 25      # 每个知识库"BM25 关键词召回"取多少候选
XHANGGE_RRF_K = 60             # RRF 融合常数：越大两路越平权，越小越看重靠前名次
XHANGGE_RERANK_ENABLED = True  # 是否做二段重排（关掉则直接用融合分数）
XHANGGE_RERANK_POOL = 15       # 进入重排的候选数（重排完仍只取 XHANGGE_TOP_K_FINAL 段）
# 重排方式："llm"（本地大模型打分，开箱即用）或 "cross_encoder"（bge-reranker 交叉编码器，更准但需装依赖）
XHANGGE_RERANK_MODE = "llm"
# cross_encoder 模式用的重排模型（需 pip install sentence-transformers，首次会下载模型）
XHANGGE_RERANK_MODEL = "BAAI/bge-reranker-base"

# ============================================================
# Agent 相关配置
# ============================================================
# 沙箱里跑代码的超时秒数（跑太久就掐掉，防止死循环卡住）
XHANGGE_SANDBOX_TIMEOUT = 10
# 必须经过人工确认弹窗才能执行的高危工具
# （只读类操作如搜索、读文件、查知识库不在此列，否则会烦死人）
XHANGGE_HITL_TOOLS = (
    "xhangge_write_file",
    "xhangge_delete_file",
    "xhangge_run_command",
)
# Agent 一次任务最多允许循环多少步（防止它自己绕圈绕不出来）
XHANGGE_AGENT_MAX_STEPS = 25

# ============================================================
# 学习文档 Skill 相关配置
# ============================================================
# 生成学习文档 / 问答集时，最多带多少条历史消息当上下文。
# 为什么要有上限：问答集最多 50 题，上下文塞太多会挤占输出空间，
# 而且太久远的聊天内容通常和当前主题无关。30 条对一般学习对话足够了。
XHANGGE_SKILL_CONTEXT_MESSAGES = 30

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
# SQLite 数据库文件（保存会话、聊天记录、知识库元信息、模型配置）
DB_PATH = XHANGGE_DATA_DIR / "xhangge_chat.db"
# 设置文件（保存用户名/主题/学习模式等偏好，JSON 格式）
SETTINGS_PATH = XHANGGE_DATA_DIR / "xhangge_settings.json"
# 向量库目录（Chroma 的家，一个知识库对应一个 collection）
XHANGGE_CHROMA_DIR = XHANGGE_DATA_DIR / "xhangge_chroma"
# 导入文档的副本目录。
# 为什么要复制一份：如果只记住"文件在你桌面的哪个位置"，
# 你哪天整理桌面把它移走或删掉，知识库就会变成一堆找不到原文的向量。
# 复制一份到我们自己的地盘，知识库就永久自洽了。
XHANGGE_KB_FILES_DIR = XHANGGE_DATA_DIR / "xhangge_kb_files"
# 用户上传的头像（存成圆形裁剪好的 PNG，聊天气泡直接拿来用）
XHANGGE_USER_AVATAR = XHANGGE_DATA_DIR / "xhangge_user_avatar.png"

# ============================================================
# 猫娘立绘素材（雪花喵的拟人形象）
# ============================================================
# 素材放在项目的 assets/xhangge_catgirl/ 目录下
XHANGGE_CATGIRL_DIR = Path(__file__).resolve().parent.parent / "assets" / "xhangge_catgirl"
# 各用途对应的文件名
XHANGGE_CATGIRL_STAND = "stand.png"    # 站立：欢迎语、弹窗顶部、空状态
XHANGGE_CATGIRL_AVATAR = "avatar.png"  # 圆形头像：聊天气泡
XHANGGE_CATGIRL_RUN = ("run_1.png", "run_2.png")  # 跑步循环两相
XHANGGE_CATGIRL_TURN = "turn.png"      # 回头转身

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
        # ---- 下面是改造后新增的设置项 ----
        # 当前选用的本地 Ollama 模型名。
        # 只有在"没有激活任何在线 API 配置"时才生效
        # （本地和在线是互斥的，同时只能用一个）。
        "local_model": XHANGGE_MODEL_NAME,
        # Agent 的工作目录。必须由用户手动选择，
        # 空字符串表示还没选——此时"改文件""跑命令"两个工具会直接拒绝执行。
        # 这是安全考虑：不给 Agent 一个默认目录去乱翻用户的电脑。
        "agent_work_dir": "",
        # 联网搜索用哪个引擎：tavily（效果好，要 Key）/ ddgs（免费，不要 Key）
        "search_engine": "ddgs",
        # Tavily 的 API Key（没填就自动降级用 ddgs）
        "tavily_api_key": "",
        # 沙箱执行超时秒数（用户可在设置里调）
        "sandbox_timeout": XHANGGE_SANDBOX_TIMEOUT,
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


def xhangge_ensure_dirs():
    """确保所有需要的数据目录都存在（程序启动时调一次）。

    这段在干什么：
    把 ~/.xh_snowcat/ 以及它下面的向量库目录、文件副本目录
    都提前建好，后面各个模块就不用各自操心目录存不存在了。
    exist_ok=True 表示"已经有了就当没事发生"，可以反复调用。
    """
    for d in (XHANGGE_DATA_DIR, XHANGGE_CHROMA_DIR, XHANGGE_KB_FILES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def xhangge_catgirl_path(file_name):
    """拿到某张猫娘素材的完整路径。

    参数 file_name 用上面 XHANGGE_CATGIRL_* 那几个常量传进来。
    找不到文件时返回 None，调用方可以据此退回到 emoji 显示，
    这样即使素材缺失程序也不会崩。
    """
    p = XHANGGE_CATGIRL_DIR / file_name
    return p if p.exists() else None
