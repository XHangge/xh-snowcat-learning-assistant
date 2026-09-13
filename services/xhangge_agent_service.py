# Author: xhangge
# This project is created by xhangge
"""
xhangge_agent_service —— 雪花喵 Agent（模块一）

Agent 和普通聊天的区别（大白话）：
普通聊天像"问路"——你问，它用嘴答；
Agent 像"雇了个跑腿的"——它能自己上网查、翻知识库、读写文件、跑命令，
干完活再向你汇报。

这个文件是 Agent 的"手和脚"：
- 七个工具（@tool 装饰的函数，模型可以自己决定什么时候调用）
- 安全围栏（改东西只准发生在用户选的工作目录里）
- 代码沙箱（跑命令有超时、有输出上限、有危险命令黑名单）
- 自进化笔记（Agent 能把经验写下来，下次任务开场就能看到）
- XhanggeAgentWorker：在后台线程里跑 Agent，把过程一步步汇报给界面

安全设计（三条线，层层设防）：
1. 围栏：所有修改类工具先检查路径是不是在工作目录里面，不是就拒绝
2. 沙箱：跑命令限定在工作目录 + 超时掐断 + 危险命令黑名单
3. 人工确认（HITL）：写文件/删文件/跑命令这三个高危动作，
   每一次都要弹窗让用户点同意才执行（用 LangChain 的
   HumanInTheLoopMiddleware，Agent 运行会真正"暂停"，点了才继续）
"""

import asyncio
import subprocess
import threading
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from config import xhangge_settings as xhangge_config
from config.xhangge_prompts import build_agent_system_prompt

# 步骤卡片上的小图标：工具汇报进度时带的"类型" → 界面上显示的 emoji
_XHANGGE_STEP_ICONS = {
    "search": "🔍",
    "kb": "📚",
    "read_file": "📄",
    "write_file": "✏️",
    "delete": "🗑",
    "command": "⌨️",
    "note": "📝",
    "hitl_ok": "✅",
    "hitl_no": "🚫",
}

# Agent 的自进化笔记文件（和数据库、向量库住在一起）
XHANGGE_AGENT_NOTES_PATH = xhangge_config.XHANGGE_DATA_DIR / "xhangge_agent_notes.md"
# 读文件工具的读取上限（太大会撑爆上下文）
_XHANGGE_READ_LIMIT = 60 * 1024
# 跑命令的输出上限（同样的道理）
_XHANGGE_CMD_OUTPUT_LIMIT = 4000
# 危险命令黑名单：不管用户同不同意都不跑。
# 这是最后一道保险——就算弹窗被误点，这些命令也伤不了系统。
_XHANGGE_BANNED_COMMANDS = (
    "rm -rf /", "rm -rf ~", "mkfs", "shutdown", "reboot",
    "dd if=", ":(){", "fork bomb", "chmod -R 777 /",
)


# ============================================================
# 自进化笔记（读写）
# ============================================================
def xhangge_load_agent_notes(max_chars=2000):
    """读出 Agent 攒下的经验笔记（最多带最近 max_chars 个字）。

    文件不存在（还没用过 Agent）就返回空字符串。
    只带最近的部分：笔记会一直长大，全塞进提示词会挤爆上下文。
    """
    try:
        if not XHANGGE_AGENT_NOTES_PATH.exists():
            return ""
        text = XHANGGE_AGENT_NOTES_PATH.read_text(encoding="utf-8").strip()
        return text[-max_chars:]
    except OSError:
        return ""


def _xhangge_append_agent_note(content):
    """往笔记文件末尾追加一条带时间戳的经验。"""
    from datetime import datetime

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    XHANGGE_AGENT_NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(XHANGGE_AGENT_NOTES_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n- [{stamp}] {content.strip()}\n")


# ============================================================
# 路径围栏（所有会改动磁盘的工具都要过这一关）
# ============================================================
def _xhangge_guard_path(work_dir, raw_path, must_be_file=None):
    """检查一个路径是不是安全可用。

    参数：
        work_dir     —— 用户在设置里选的工作目录（Path 或 None=没选）
        raw_path     —— 模型给的路径（可能是相对路径、带 ~ 的路径）
        must_be_file —— True 要求是个文件 / False 要求是目录 / None 不检查
    返回：
        (Path 对象, "")     —— 安全，可以用
        (None, 错误说明)     —— 危险或不存在，把错误说明返回给模型
    """
    if work_dir is None:
        return None, (
            "用户还没在设置里选工作目录喵。"
            "请提醒用户去「⚙️ 设置 → 🤖 Agent 喵」选择一个文件夹，"
            "在这之前所有改文件、跑命令的操作都用不了。"
        )

    p = Path(raw_path).expanduser()
    # 相对路径 = 工作目录里面的路径
    if not p.is_absolute():
        p = work_dir / p
    # resolve() 把 ./ 和 ../ 和软链接都展开成真实位置，防止"绕路"越界
    resolved = p.resolve()
    wd = work_dir.resolve()

    # 核心检查：路径必须等于工作目录本身，或者在它里面
    if resolved != wd and wd not in resolved.parents:
        return None, (
            f"路径「{raw_path}」在工作目录外面喵，"
            "我只能动工作目录里面的东西（这是保护用户电脑的规矩）。"
            f"工作目录是：{wd}"
        )
    if must_be_file is True and not resolved.is_file():
        return None, f"「{raw_path}」不是文件喵（可能不存在，或者是个文件夹）"
    if must_be_file is False and not resolved.is_dir():
        return None, f"「{raw_path}」不是文件夹喵"
    return resolved, ""


# ============================================================
# 工具工厂：给一次 Agent 运行造一套工具
# ============================================================
# 为什么是"工厂"而不是直接写死七个函数：
# 工具需要知道"这次运行"的现场信息（哪个会话、哪个工作目录、
# 进度怎么汇报给界面）。用闭包把这些信息包进去，每次运行现造一套。
def xhangge_build_tools(db, session_id, settings, report_step):
    """造一套 Agent 工具。

    参数：
        db          —— 数据库（知识库工具要查会话绑定了哪些库）
        session_id  —— 当前会话 id
        settings    —— 用户设置（搜索引擎、Key、沙箱超时）
        report_step —— 汇报进度的回调（icon, text），由界面提供
    返回：工具对象列表（LangChain @tool 格式）
    """
    from langchain_core.tools import tool

    # 工作目录：空字符串 = 用户还没选。
    # 注意不能写 Path("")：Python 里 Path("") 等于 Path(".")（当前目录），
    # 既是"真"的、也真的存在，"没选"的判断就永远不成立了——
    # 实测就因为这个把文件写进了软件启动目录喵。
    # 所以这里用 None 表示"没选"。
    raw_work_dir = (settings.get("agent_work_dir", "") or "").strip()
    work_dir = Path(raw_work_dir) if raw_work_dir else None

    def step(icon, text):
        """给界面汇报一步，汇报失败也不影响干活。"""
        try:
            report_step(icon, text)
        except Exception:
            pass

    # ---------------- 联网搜索 ----------------
    @tool
    def xhangge_search_web(query: str) -> str:
        """联网搜索资料。返回若干条结果的标题、链接和摘要。需要查最新信息、公开知识时用。"""
        step("search", f"联网搜索：{query}")
        try:
            results = _xhangge_do_search(query, settings)
        except Exception as e:
            return (
                "联网搜索失败了喵，很可能是当前网络访问不了外网（搜索引擎连不上）。\n"
                "可以：① 用「写文件」+「执行命令」自己写个小脚本抓取"
                "（这两步会弹窗请用户确认）；② 改用知识库里的资料；"
                "③ 直接按已有知识回答，并提醒用户检查网络喵。\n"
                f"（原因：{type(e).__name__}）"
            )
        if not results:
            return (
                "联网搜索没搜到结果喵，可能是当前网络访问不了外网。\n"
                "可以试试换关键词，或者用「写文件」+「执行命令」自己写脚本抓取"
                "（需要用户确认），也可以改用知识库里的资料喵。"
            )
        lines = []
        for i, r in enumerate(results[:5], start=1):
            lines.append(
                f"{i}. {r.get('title', '无标题')}\n   链接：{r.get('href', '无')}\n"
                f"   摘要：{r.get('body', '')[:200]}"
            )
        return "\n".join(lines)

    # ---------------- 查知识库 ----------------
    @tool
    def xhangge_search_kb(query: str) -> str:
        """检索用户自己的知识库（他的笔记、文档）。用户提到"我的资料/我的笔记/知识库"时优先用这个。"""
        from services.xhangge_kb_service import xhangge_retrieve

        kb_ids = db.xhangge_get_session_kb_ids(session_id)
        if not kb_ids:
            return (
                "这个会话还没有绑定任何知识库喵。"
                "请提醒用户点标题栏 📚 绑定知识库，"
                "或者改用联网搜索。"
            )
        step("kb", f"查知识库：{query}")
        try:
            chunks = xhangge_retrieve(db, query, kb_ids)
        except Exception as e:
            return f"知识库检索出错喵（可能 Ollama 没开）：{type(e).__name__}"
        if not chunks:
            return "知识库里没找到相关内容喵，试试联网搜索？"
        parts = []
        for i, c in enumerate(chunks, start=1):
            parts.append(f"【{i}】来自《{c.file_name}》：{c.text}")
        return "\n\n".join(parts)

    # ---------------- 读文件 ----------------
    @tool
    def xhangge_read_file(path: str) -> str:
        """读取工作目录里的一个文本文件的内容。只读不改，不需要用户批准。"""
        target, err = _xhangge_guard_path(work_dir, path, must_be_file=True)
        if err:
            return err
        step("read_file", f"读文件：{target.name}")
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"读不了喵：{e}"
        if len(text) > _XHANGGE_READ_LIMIT:
            text = text[:_XHANGGE_READ_LIMIT] + "\n…（太长，只取前 60KB）"
        return text or "（文件是空的喵）"

    # ---------------- 写文件（高危：要用户点同意） ----------------
    @tool
    def xhangge_write_file(path: str, content: str) -> str:
        """在工作目录里创建或覆盖一个文本文件。会弹出确认窗口让用户点同意。"""
        target, err = _xhangge_guard_path(work_dir, path)
        if err:
            return err
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"写入失败喵：{e}"
        step("write_file", f"写入文件：{target.name}（{len(content)} 字）")
        return f"已写入「{target.name}」喵（{len(content)} 个字符）。"

    # ---------------- 删文件（高危：要用户点同意） ----------------
    @tool
    def xhangge_delete_file(path: str) -> str:
        """删除工作目录里的一个文件（只删文件，不删文件夹）。会弹出确认窗口让用户点同意。"""
        target, err = _xhangge_guard_path(work_dir, path, must_be_file=True)
        if err:
            return err
        try:
            target.unlink()
        except OSError as e:
            return f"删除失败喵：{e}"
        step("delete", f"删除了文件：{target.name}")
        return f"已删除「{target.name}」喵。"

    # ---------------- 跑命令（高危：要用户点同意） ----------------
    @tool
    def xhangge_run_command(command: str) -> str:
        """在工作目录里执行一条 shell 命令（比如 python xxx.py、pip list）。会弹出确认窗口让用户点同意。超时会被掐断。"""
        low = command.lower()
        for banned in _XHANGGE_BANNED_COMMANDS:
            if banned in low:
                return (
                    f"命令「{command}」被安全黑名单拦下了喵。"
                    "这种会伤到系统的命令我不能跑。"
                )
        if work_dir is None:
            return (
                "用户还没在设置里选工作目录喵，跑命令需要先选一个"
                "（⚙️ 设置 → 🤖 Agent 喵）。"
            )
        step("command", f"执行命令：{command}")
        try:
            proc = subprocess.run(
                command,
                shell=True,              # 要支持 python x.py / pip install 这种组合命令
                cwd=str(work_dir),       # 关进工作目录里跑
                capture_output=True,
                text=True,
                timeout=int(settings.get(
                    "sandbox_timeout", xhangge_config.XHANGGE_SANDBOX_TIMEOUT
                )),
            )
        except subprocess.TimeoutExpired:
            return (
                "命令超时被掐断了喵（这是保护机制）。"
                "如果它本来就要跑很久，请提醒用户在设置里调大超时时间。"
            )
        except OSError as e:
            return f"命令启动失败喵：{e}"
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out) > _XHANGGE_CMD_OUTPUT_LIMIT:
            out = out[:_XHANGGE_CMD_OUTPUT_LIMIT] + "\n…（输出太长被截断）"
        return f"退出码 {proc.returncode}\n{out or '（没有输出）'}"

    # ---------------- 自进化笔记 ----------------
    @tool
    def xhangge_note_learning(content: str) -> str:
        """把这次任务里学到的经验教训记到你的笔记本里。下次任务开始时你会看到这些笔记。写用户数据不算经验，别记。"""
        if not content.strip():
            return "内容是空的喵，没记。"
        try:
            _xhangge_append_agent_note(content[:500])
        except OSError as e:
            return f"笔记写不进去喵：{e}"
        step("note", f"记了一条经验笔记")
        return "记好了喵，下次任务开场我就能看到它～"

    return [
        xhangge_search_web,
        xhangge_search_kb,
        xhangge_read_file,
        xhangge_write_file,
        xhangge_delete_file,
        xhangge_run_command,
        xhangge_note_learning,
    ]


def _xhangge_do_search(query, settings):
    """真正执行联网搜索：按设置选引擎，Tavily 失败自动退回 DuckDuckGo。

    返回结果列表（每条是 {title, href, body} 字典）。
    """
    engine = settings.get("search_engine", "ddgs")
    api_key = (settings.get("tavily_api_key", "") or "").strip()

    if engine == "tavily" and api_key:
        try:
            return _xhangge_search_tavily(query, api_key)
        except Exception:
            pass  # Tavily 挂了不报错，悄悄退回免费的 DuckDuckGo
    return _xhangge_search_ddgs(query)


def _xhangge_search_ddgs(query):
    """DuckDuckGo 搜索（免费、不需要 Key）。

    显式指定 backend="duckduckgo" + 短超时：ddgs 9.x 默认 backend="auto"
    会去试 startpage 等一堆引擎，在国内网络下挨个超时，搜一次卡半分钟。
    指定后端 + 短超时让它快速失败，失败交给上层转成友好提示，别让 Agent 干等。
    """
    from ddgs import DDGS

    with DDGS(timeout=8) as ddgs:
        return list(ddgs.text(query, max_results=5, backend="duckduckgo"))


def _xhangge_search_tavily(query, api_key):
    """Tavily 搜索（专为 AI 设计的结果，需要 Key）。"""
    resp = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": 5},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": r.get("title", ""), "href": r.get("url", ""),
         "body": r.get("content", "")}
        for r in data.get("results", [])
    ]


# ============================================================
# Agent 后台线程
# ============================================================
class XhanggeAgentWorker(QThread):
    """在后台线程里跑一次完整的 Agent 任务。

    使用方式（由主窗口调用）：
        worker = XhanggeAgentWorker(db, session_id, api_messages, settings)
        worker.chunk_received / stream_finished / stream_error  # 和聊天线程同名同义
        worker.step_received  # (icon, text) Agent 每做一步汇报一次
        worker.hitl_requested  # (tool_name, tool_label, target, preview)
        worker.start()

    人工确认（HITL）的配合方式：
        线程发出 hitl_requested 后会真正停下来等；
        界面弹确认窗，用户点完调用 worker.provide_hitl_decision(同意吗, 理由)，
        线程才会继续跑（或放弃这个操作）。
    """

    # 与聊天线程相同的三个信号（界面可以无缝复用同一套处理函数）
    chunk_received = Signal(str)
    stream_finished = Signal(str)
    stream_error = Signal(str)
    # Agent 特有：做了一步（图标，文字），界面显示成步骤卡片
    step_received = Signal(str, str)
    # Agent 特有：请求人工确认（工具名，中文名，目标，预览内容）
    hitl_requested = Signal(str, str, str, str)

    # 高危工具的中文名（确认弹窗和步骤卡片都用）
    _XHANGGE_HITL_LABELS = {
        "xhangge_write_file": "✏️ 写入/修改文件",
        "xhangge_delete_file": "🗑 删除文件",
        "xhangge_run_command": "⌨️ 执行命令",
    }

    def __init__(self, db, session_id, api_messages, settings, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_id = session_id
        self.api_messages = api_messages    # [{"role": ..., "content": ...}]
        self.settings = settings
        self._stop_requested = False
        # 人工确认的等待装置：线程停下来等，界面点完按钮唤醒它
        self._hitl_event = threading.Event()
        self._hitl_answer = None            # (同意吗, 理由)

    # ---------------- 对外方法（界面调用） ----------------
    def request_stop(self):
        """用户点了停止喵。"""
        self._stop_requested = True
        # 如果正卡在等人工确认，把等待也唤醒（视为拒绝），
        # 不然线程会永远停在 wait() 上退不出来。
        # ask_human 每次都会先清空再等，所以这里多设一次也不会误伤下一次。
        if not self._hitl_event.is_set():
            self._hitl_answer = (False, "用户点了停止喵")
            self._hitl_event.set()

    def provide_hitl_decision(self, approve, message=""):
        """界面拿到用户的确认结果后调用，唤醒等待中的 Agent。"""
        self._hitl_answer = (approve, message)
        self._hitl_event.set()

    # ---------------- 线程主体 ----------------
    def run(self):
        try:
            asyncio.run(self._xhangge_run_agent())
        except Exception as e:
            # 兜底：Agent 框架抛出的任何异常都翻译成友好提示，不让界面崩
            self.stream_error.emit(
                "Agent 出了点状况喵 😿\n（" + type(e).__name__ + "）"
                + str(e)[:200]
            )

    async def _xhangge_run_agent(self):
        """一次完整的 Agent 运行（含"中断→弹窗→恢复"的循环）。"""
        from langchain.agents import create_agent
        from langchain.agents.middleware import HumanInTheLoopMiddleware
        from langchain_core.messages import AIMessageChunk
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.types import Command
        from services.xhangge_llm_router import xhangge_get_llm

        # 1. 组装提示词：人设+任务书（带上经验笔记）+ 历史背景 + 本次问题
        notes = xhangge_load_agent_notes()
        system_prompt = build_agent_system_prompt(
            self.settings.get("username", ""), agent_notes=notes
        )

        # 历史的处理方式（重要，和普通聊天不一样）：
        # 普通聊天把历史当"对话消息"原样发给模型（会话记忆）；
        # Agent 不能这么做——之前轮次里"雪花喵的回答"全是
        # "我已经创建了 xx 文件"这类成功叙事，模型会照着这个
        # 模式继续编故事（谎报完成任务），而不是真的调工具。
        # 实测踩过的坑。所以历史要打包成"背景资料"塞进系统提示词，
        # 让模型的回答通道干干净净，只能靠真的调工具拿到新信息。
        if len(self.api_messages) > 1:
            lines = []
            for m in self.api_messages[:-1][-10:]:
                who = "用户" if m.get("role") == "user" else "雪花喵"
                lines.append(f"{who}：{m.get('content', '')}")
            background = "\n".join(lines)[-4000:]
            system_prompt += (
                "\n\n【之前的对话记录（只做背景参考，不是让你复述它）】\n"
                + background
            )

        # 本次用户的问题单独作为最后一条消息（Agent 唯一的"任务单"）
        from langchain_core.messages import HumanMessage

        current_text = (
            self.api_messages[-1].get("content", "") if self.api_messages else ""
        )
        lc_messages = [HumanMessage(content=current_text)]

        # 2. 造模型、造工具、装上"高危操作要人工确认"的中间件
        # fresh=True：Agent 每次任务现造一个新模型实例。
        # 不用缓存的原因：Agent 在 asyncio 循环里跑，循环每次任务
        # 都是新建的、跑完就关；缓存实例里的连接绑死在旧循环上，
        # 第二次任务必炸（Event loop is closed 喵）。
        # temperature=0：Agent 要的是"稳定地调对工具"，不是文采；
        # 高温度下 7B 模型会时而调工具、时而嘴上答应不干活喵。
        llm = xhangge_get_llm(self.db, fresh=True, temperature=0)
        tools = xhangge_build_tools(
            self.db, self.session_id, self.settings, self._xhangge_report_step
        )
        hitl = HumanInTheLoopMiddleware(
            {name: True for name in xhangge_config.XHANGGE_HITL_TOOLS}
        )
        agent = create_agent(
            llm,
            tools,
            system_prompt=system_prompt,
            middleware=[hitl],
            checkpointer=InMemorySaver(),  # 中断/恢复需要它保存现场
        )
        config = {"configurable": {"thread_id": f"xhangge-agent-{self.session_id}"}}

        # 3. 跑起来（可能中途停下来要确认，恢复后再继续，直到干完）
        inputs = {"messages": lc_messages}
        answer_text = ""
        while True:
            interrupt_info = None
            async for mode, chunk in agent.astream(
                inputs, config, stream_mode=["messages", "updates"]
            ):
                if mode == "messages":
                    msg, _meta = chunk
                    # 只把"模型说出来的字"流式给界面（打字机效果）。
                    # 正在拼参数的工具调用消息没有正文，自然会被跳过。
                    if isinstance(msg, AIMessageChunk):
                        content = getattr(msg, "content", "")
                        if isinstance(content, str) and content:
                            if not getattr(msg, "tool_call_chunks", None):
                                answer_text += content
                                self.chunk_received.emit(content)
                elif mode == "updates":
                    # updates 模式：每个节点结束时发一次它的状态更新。
                    # 高危工具触发中断时，更新里会出现 "__interrupt__"。
                    if isinstance(chunk, dict) and "__interrupt__" in chunk:
                        for intr in chunk["__interrupt__"]:
                            interrupt_info = intr

            if self._stop_requested:
                break

            if interrupt_info is not None:
                # ---- Agent 停下来等确认 ----
                decision = await self._xhangge_ask_human(interrupt_info)
                if decision is None:
                    # 用户直接关了确认窗（视为拒绝）或点了停止
                    decision = {
                        "decisions": [
                            {"type": "reject", "message": "用户没有确认喵"}
                        ]
                    }
                # 拒绝时告诉模型原因，它好调整方案而不是傻傻重试
                inputs = Command(resume=decision)
                continue

            break  # 没有中断了 = 任务干完了

        self.stream_finished.emit(answer_text)

    async def _xhangge_ask_human(self, interrupt):
        """弹窗问用户"同意吗"，等到用户点了才返回决定。

        返回 {"decisions": [{"type": "approve"}]} 或
             {"decisions": [{"type": "reject", "message": ...}]}；
        返回 None 表示没法问（视为拒绝）。

        为什么包一层 {"decisions": [...]}：LangChain 的中间件源码里
        写死了 `interrupt(请求)["decisions"]`——恢复时它要从这里取出
        决定列表，所以恢复载荷必须是这个形状（踩过坑才知道的喵）。

        原理：发 Qt 信号到界面线程 → 界面弹模态窗 → 用户点按钮 →
        界面调 provide_hitl_decision() → _hitl_event 置位 → 这里的
        wait() 返回。Agent 线程停下来干等，不会烧 CPU。
        """
        # 中断的载荷是 HITLRequest：{action_requests: [{name, args, ...}]}
        value = getattr(interrupt, "value", None)
        if not isinstance(value, dict):
            value = {}
        actions = value.get("action_requests") or []
        if actions:
            first = actions[0]
            tool_name = first.get("name", "未知工具")
            args = first.get("args", {}) or {}
        else:
            tool_name = "未知工具"
            args = {}

        # 目标和预览：按工具类型挑重点给用户看
        if tool_name == "xhangge_write_file":
            target = str(args.get("path", ""))
            preview = str(args.get("content", ""))[:600]
        elif tool_name == "xhangge_delete_file":
            target = str(args.get("path", ""))
            preview = ""
        elif tool_name == "xhangge_run_command":
            target = str(args.get("command", ""))
            preview = "将在工作目录里执行喵"
        else:
            target = str(args)
            preview = ""

        label = self._XHANGGE_HITL_LABELS.get(tool_name, tool_name)

        # 重置等待装置，发信号，然后原地等界面唤醒
        self._hitl_event.clear()
        self._hitl_answer = None
        self.hitl_requested.emit(tool_name, label, target, preview)
        self._hitl_event.wait()  # 界面点完按钮才会返回

        if self._stop_requested:
            return None
        approve, message = self._hitl_answer or (False, "")
        if approve:
            self._xhangge_report_step("hitl_ok", f"{label}：用户同意了喵")
            return {"decisions": [{"type": "approve"}]}
        self._xhangge_report_step("hitl_no", f"{label}：用户拒绝了喵")
        return {
            "decisions": [{"type": "reject", "message": message or "用户不同意"}]
        }

    def _xhangge_report_step(self, icon, text):
        """工具干活时汇报进度（在 Agent 线程里被调用，Qt 信号会自动排队送到界面线程）。

        icon 传的是类型标识（"search" / "kb" / ...），
        这里翻译成 emoji 再发，界面拿到就能直接拼在步骤卡片上。
        """
        self.step_received.emit(_XHANGGE_STEP_ICONS.get(icon, "🐾"), text)
