# Author: xhangge
# This project is created by xhangge
"""
xhangge_chat_service —— 普通聊天服务（和大模型对话的"传令兵"）
负责把聊天记录发给模型，并把回答一块一块地（流式）传回界面，
实现"打字机效果"。

为什么需要后台线程（QThread）：
模型生成回答需要几十秒，如果在界面线程里直接等待，
整个窗口会卡死（不能拖动、不能点按钮）。
所以把"等待模型"这件事放到后台线程，界面始终保持流畅；
后台线程每收到一小段文字，就通过 Qt 信号（Signal）通知界面更新。

【这个文件改造过什么】
以前它自己用 requests 直接请求 Ollama 的 /api/chat。
现在改成统一走 services/xhangge_llm_router.py 拿到的 LangChain ChatModel，
好处是——用户在设置里切到在线 API（DeepSeek 等）之后，
这个文件一行都不用改就自动生效了，因为 LangChain 把两种后端
包装成了同一个接口（都有 .stream() 方法）。

对外的三个信号名（chunk_received / stream_finished / stream_error）
和以前完全一样，所以界面层的代码也不用改。
"""

import requests
from PySide6.QtCore import QThread, Signal

from config import xhangge_settings as xhangge_config
from services.xhangge_llm_router import xhangge_to_langchain_messages


def _xhangge_chunk_text(chunk):
    """从一个流式片段里取出纯文字。

    为什么要专门写这个函数：
    不同厂商返回的 content 格式不完全一样——
    大多数是普通字符串，但有些会返回一个"内容块列表"，
    长这样：[{"type": "text", "text": "喵"}, ...]。
    直接当字符串用就会在界面上显示出一堆花括号，所以在这里统一压平成文字。
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # 只取文本块，工具调用之类的块在普通聊天里不会出现
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


class XhanggeChatWorker(QThread):
    """后台聊天工作线程：负责一次"发出问题 → 流式接收回答"的完整过程。

    使用方式（由主窗口调用）：
        llm = xhangge_get_llm(self.db)          # 在界面线程里取模型
        worker = XhanggeChatWorker(llm, messages)
        worker.chunk_received.connect(界面追加文字)     # 每收到一小段就调用
        worker.stream_finished.connect(回答完成的处理)   # 正常结束或被手动停止
        worker.stream_error.connect(出错的提示)         # 连不上模型等错误
        worker.start()                                  # 启动后台线程

    为什么模型实例要在界面线程里取好再传进来，而不是在线程里自己取：
    取模型这一步要读数据库（查用户选的是本地还是在线）。
    SQLite 的连接对象不能跨线程用，在后台线程里读同一个连接会报错。
    而取模型本身很快（只是读配置、造对象，不发网络请求），
    放在界面线程里做完全不会卡，所以这样分工最省事也最安全。
    """

    # ---- Qt 信号定义（后台线程 → 界面线程 的"传话筒"）----
    # 每收到一小段回答文字就发一次（参数：这一小段文字）
    chunk_received = Signal(str)
    # 回答结束（参数：完整的回答全文；用户中途停止时也走这里，带已生成的部分）
    stream_finished = Signal(str)
    # 出错了（参数：给用户看的友好中文错误信息）
    stream_error = Signal(str)

    def __init__(self, llm, messages, backend_label="", parent=None):
        """初始化工作线程。

        参数：
            llm           —— LangChain ChatModel 对象，
                             由 services/xhangge_llm_router.py 造好传进来
            messages      —— 发给模型的消息列表，格式：
                             [{"role": "system", "content": 系统提示词},
                              {"role": "user", "content": "问题"}, ...]
            backend_label —— 当前后端的可读名称，只在报错时拼进提示里，
                             让用户知道是哪个后端出的问题
        """
        super().__init__(parent)
        self.llm = llm
        self.messages = messages
        self.backend_label = backend_label
        # 用户是否请求了"停止生成"
        self._stop_requested = False

    # --------------------------------------------------------
    # 对外方法
    # --------------------------------------------------------
    def request_stop(self):
        """请求停止生成（界面上的"停止喵"按钮调用）。

        这段在干什么：
        只是把标志立起来。下面 run() 里的循环每收到一小段就检查一次这个标志，
        发现被立起来了就 break 跳出循环。

        为什么这样就能真的停下来：
        .stream() 返回的是一个"生成器"。跳出 for 循环时 Python 会关掉这个生成器，
        底层那条 HTTP 连接也跟着断开，模型那边就不会再往我们这儿发东西了。
        （以前用 requests 时要自己 close() 响应对象，换成 LangChain 之后
        它内部会帮我们收拾，所以这里不用再手动关连接。）
        """
        self._stop_requested = True

    # --------------------------------------------------------
    # 线程主体（worker.start() 之后，这段代码在后台线程里运行）
    # --------------------------------------------------------
    def run(self):
        full_text = ""  # 累积模型的完整回答

        try:
            # ---- 1. 把消息翻译成 LangChain 的格式 ----
            lc_messages = xhangge_to_langchain_messages(self.messages)

            # ---- 2. 流式请求：边生成边收，不等模型全部想完 ----
            for chunk in self.llm.stream(lc_messages):
                # 用户点了停止，立刻退出循环
                if self._stop_requested:
                    break
                piece = _xhangge_chunk_text(chunk)
                if piece:
                    full_text += piece               # 累积到全文
                    self.chunk_received.emit(piece)  # 通知界面：追加这一小段

            # ---- 3. 正常收尾（包括用户中途停止的情况）----
            # 把已生成的完整文字（可能是全部，也可能是停止前的部分）交给界面保存
            self.stream_finished.emit(full_text)

        except Exception as e:
            # 这里统一捕获所有异常。
            # 为什么不像以前那样分门别类地 except：
            # 换成 LangChain 之后，同一种问题在不同后端会抛出不同的异常类
            # （本地 Ollama 抛 httpx 的错，在线 API 抛 openai 的错），
            # 一个个列出来既列不全也没必要。
            # 改成统一捕获，再从错误文字里认出最常见的几种情况给出人话提示。
            self.stream_error.emit(self._xhangge_friendly_error(e))

    def _xhangge_friendly_error(self, error):
        """把技术性的报错翻译成用户看得懂的话。

        为什么要翻译：直接把 "APIConnectionError: Connection refused" 甩给用户，
        他只会一脸茫然。认出常见情况并给出"接下来该做什么"才有用。
        """
        text = str(error)
        low = text.lower()
        name = type(error).__name__

        # ---- 情况一：连不上服务 ----
        connect_hints = ("connection", "connect", "refused", "unreachable",
                         "name or service not known", "timed out", "timeout")
        if any(h in low for h in connect_hints):
            if self.backend_label.startswith("本地"):
                return (
                    "喵呜呜！连不上 Ollama 喵 😿\n\n"
                    "请检查一下：\n"
                    "1. Ollama 是否已经启动？（终端里运行：ollama serve）\n"
                    "2. 服务地址是否正确？（当前配置："
                    + xhangge_config.OLLAMA_BASE_URL + "）"
                )
            return (
                "连不上在线 API 喵 😿\n\n"
                "请检查一下：\n"
                "1. 网络是不是断了？\n"
                "2. 设置里的「接口地址」填对了吗？\n"
                "（当前用的是：" + (self.backend_label or "在线 API") + "）"
            )

        # ---- 情况二：钥匙不对 ----
        if any(h in low for h in ("401", "unauthorized", "invalid api key",
                                  "authentication")):
            return (
                "API Key 好像不对喵 🔑😿\n\n"
                "去设置 → 🧠 模型喵 里重新填一下 Key，\n"
                "填完可以点「🔌 测试连接喵」先验一下再用～"
            )

        # ---- 情况三：模型名字不对 / 模型没下载 ----
        if any(h in low for h in ("404", "not found", "does not exist",
                                  "model not found")):
            if self.backend_label.startswith("本地"):
                model = self.backend_label.replace("本地", "").strip()
                return (
                    "找不到模型「" + model + "」喵 😿\n\n"
                    "去设置 → 🧠 模型喵 里点「⬇️ 一键下载喵」就能装好，\n"
                    "或者在终端里运行：ollama pull " + model
                )
            return (
                "在线 API 说找不到这个模型喵 😿\n\n"
                "去设置 → 🧠 模型喵 里检查一下「模型名称」有没有打错～"
            )

        # ---- 情况四：额度用完了 / 请求太频繁 ----
        if any(h in low for h in ("429", "rate limit", "quota",
                                  "insufficient balance")):
            return (
                "在线 API 那边不让继续了喵 😿\n\n"
                "常见原因是额度用完了，或者请求太频繁被限流了。\n"
                "等一会儿再试，或者去设置里换成本地模型先顶一下～"
            )

        # ---- 其它没认出来的错误 ----
        if len(text) > 200:
            text = text[:200] + "…"
        return "发生了没见过的错误喵 😿（" + name + "）\n" + text


def check_ollama_status(base_url=None, model=None):
    """检查 Ollama 服务和模型是否就绪（程序启动时调用）。

    这段在干什么：
    1. 访问 Ollama 的 /api/tags 接口，拿到本机已安装的模型列表
    2. 返回两个布尔值：(服务是否在线, 指定模型是否已下载)

    返回：
        (True, True)   —— 一切就绪
        (True, False)  —— Ollama 在运行，但要用的模型还没下载
        (False, False) —— Ollama 没在运行
    """
    base_url = base_url or xhangge_config.OLLAMA_BASE_URL
    model = model or xhangge_config.XHANGGE_MODEL_NAME
    try:
        resp = requests.get(base_url + "/api/tags", timeout=3)
        if not resp.ok:
            return False, False
        # 解析模型列表，例如 ["qwen2.5:7b", "bge-m3:latest"]
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        # 名字完全相同，或是同名带变体后缀（如 qwen2.5:7b-q4）都算可用
        model_ready = any(n == model or n.startswith(model + "-") for n in names)
        return True, model_ready
    except requests.RequestException:
        # 连不上、超时等一切网络问题，都视为服务不在线
        return False, False
