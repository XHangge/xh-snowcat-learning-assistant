# Author: xhangge
# This project is created by xhangge
"""
xhangge_main_window —— 主窗口（整个软件的"总调度中心"）
负责把各个零件组装到一起：
- 顶部：自定义标题栏（🐱 标题 + 置顶/侧边栏/最小化/最大化/关闭按钮）
- 左边：侧边栏（会话管理、用户名、主题、学习模式）
- 右边：聊天区（气泡对话 + 输入框）

为什么自己画标题栏：
去掉系统自带标题栏（无边框窗口）后，软件才能从头到脚都是
粉色圆角可爱风；最小化/最大化/关闭这些按钮就由我们自己画。
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
)
from pathlib import Path

from config import xhangge_settings as xhangge_config
from config.xhangge_prompts import build_rag_context_section, build_system_prompt
from gui.xhangge_avatars import xhangge_apply_paw_cursor, xhangge_catgirl_label, xhangge_hand_cursor
from gui.xhangge_chat_area import XhanggeChatArea
from gui.xhangge_dialogs import (
    XhanggeExportProgressDialog,
    show_confirm_dialog,
    show_hitl_dialog,
    show_rename_dialog,
    show_warning_dialog,
)
from gui.xhangge_kb_page import XhanggeKbDialog
from gui.xhangge_resize import XhanggeResizeHelper
from gui.xhangge_settings_page import XhanggeSettingsDialog
from gui.xhangge_sidebar import XhanggeSidebar
from gui.xhangge_themes import XHANGGE_THEMES
from models.xhangge_db import XhanggeDatabase
from services.xhangge_agent_service import XhanggeAgentWorker
from services.xhangge_chat_service import XhanggeChatWorker
from services.xhangge_kb_service import xhangge_retrieve
from services.xhangge_llm_router import (
    xhangge_get_backend_label,
    xhangge_get_llm,
    xhangge_reload_llm,
)
from services.xhangge_skill_service import (
    XHANGGE_SKILL_DB_TYPES,
    build_skill_messages,
    xhangge_detect_skill,
)


def xhangge_time_stamp():
    """返回"年月日_时分"格式的时间戳（给导出文件名用，例如 20260911_1432）"""
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M")


class XhanggeTitleBar(QFrame):
    """自定义标题栏：可以拖动窗口、双击最大化，右侧一排功能按钮。"""

    def __init__(self, window):
        super().__init__(window)
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)
        self._window = window      # 主窗口引用（拖动时要移动它）
        self._drag_pos = None      # 拖动时记录鼠标和窗口的相对位置

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(6)

        # ---- 左侧：图标 + 软件名 ----
        # 图标位用猫娘圆形头像（加载不出来才显示 🐱 emoji 兜底）
        icon_label = xhangge_catgirl_label(24)
        title_label = QLabel(xhangge_config.APP_NAME)
        title_label.setObjectName("TitleLabel")
        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addStretch(1)  # 弹簧：把后面所有按钮推到最右边

        # ---- 右侧：功能按钮（从左到右） ----

        def make_button(text, tooltip, checkable=False, object_name="TitleBtn"):
            """小工具函数：造一个标题栏按钮"""
            btn = QPushButton(text)
            btn.setObjectName(object_name)
            btn.setFixedSize(40, 28)
            btn.setToolTip(tooltip)
            btn.setCursor(xhangge_hand_cursor())
            btn.setCheckable(checkable)
            layout.addWidget(btn)
            return btn

        # 窗口置顶开关（可按下的开关按钮）
        self.pin_btn = make_button("📌", "窗口置顶：固定在桌面最上层", checkable=True)
        self.pin_btn.clicked.connect(window.xhangge_toggle_always_on_top)
        # 侧边栏开/关
        self.sidebar_btn = make_button("☰", "打开/关闭侧边栏", checkable=True)
        self.sidebar_btn.setChecked(True)  # 默认显示侧边栏
        self.sidebar_btn.clicked.connect(window.xhangge_toggle_sidebar)
        # 知识库管理（模块五：建库 / 导文件 / 绑定到会话）
        self.kb_btn = make_button("📚", "知识库：导入资料、绑定到当前会话")
        self.kb_btn.clicked.connect(window.xhangge_open_kb_window)
        # 设置窗口（模型 / Agent / 搜索 / 关于）
        self.settings_btn = make_button("⚙️", "设置：模型、Agent、搜索")
        self.settings_btn.clicked.connect(window.xhangge_open_settings)
        # 最小化
        min_btn = make_button("—", "最小化")
        min_btn.clicked.connect(window.showMinimized)
        # 最大化 / 还原
        self.max_btn = make_button("▢", "最大化 / 还原")
        self.max_btn.clicked.connect(window.xhangge_toggle_maximize)
        # 关闭（悬停变红的那个，样式单独定义在 themes.py）
        close_btn = make_button("✕", "关闭", object_name="CloseBtn")
        close_btn.clicked.connect(window.close)

    # ---------------- 拖动窗口 ----------------
    def mousePressEvent(self, event):
        """按下鼠标：记下"鼠标位置 - 窗口左上角"的偏移量。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self._window.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        """按住鼠标移动：窗口跟着鼠标走（新位置 = 鼠标位置 - 偏移量）。"""
        if self._drag_pos is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._window.move(
                event.globalPosition().toPoint() - self._drag_pos
            )

    def mouseReleaseEvent(self, event):
        """松开鼠标：结束拖动。"""
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        """双击标题栏：最大化/还原（和很多软件的习惯一致）。"""
        self._window.xhangge_toggle_maximize()


class XhanggeMainWindow(QMainWindow):
    """主窗口：组装所有控件 + 处理所有业务逻辑。"""

    def __init__(self, settings):
        super().__init__()

        # ---- 保存当前状态 ----
        # 完整的设置字典。
        # 为什么要整份留着：设置文件里除了用户名/主题/模式，
        # 还有模型、Agent 工作目录、搜索引擎这些新增项。
        # 如果保存时只写自己关心的那三项，其余项就会被整份覆盖掉，
        # 表现出来就是「在设置窗改好的东西，一换主题就没了」。
        self.xhangge_all_settings = dict(settings)
        # 用户名（空字符串 = 未设置，发消息时会用默认值"杂狗"）
        self.username = settings.get("username", "")
        # 当前学习模式（simple / detailed / teach）
        self.current_mode = settings.get("mode", "simple")
        # 当前主题（pink / light / dark）
        self.current_theme = settings.get("theme", "pink")
        # 当前会话 id
        self.current_session_id = None
        # 正在工作的模型线程（None = 空闲）
        self._worker = None
        # 正在跑的学习技能标识（None = 这次是普通聊天）。
        # 生成完成后要靠它判断"这算一次技能使用"，写进流水表。
        self._active_skill = None
        # 上次导出 .md 时选的文件夹（这次导出默认从那里开始）。
        # 只存在内存里，重启软件回到用户主目录。
        self._last_export_dir = ""

        # ---- 窗口基本设置 ----
        # 任务栏/系统标题显示 snowcat（软件内部界面仍用 APP_NAME 中文品牌名）
        self.setWindowTitle("snowcat")
        self.resize(1100, 750)          # 默认窗口大小
        self.setMinimumSize(900, 600)   # 最小尺寸，防止缩太小按钮挤没了
        # 无边框：去掉系统默认的灰色标题栏（我们的粉色标题栏自己画）
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        # 背景透明：整个窗口变成"圆角矩形"的关键一步。
        # 窗口本体不再画不透明的方形底，露出透明四角；
        # 真正的圆角矩形+描边由里面的 MainWindowFrame 画（见 _build_ui）。
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # ---- 数据库 ----
        self.db = XhanggeDatabase()

        # ---- 界面组装 ----
        self._build_ui()
        # 无边框窗口：装上"拖边缘/角调整大小"的能力（否则只能靠那个看不见的小抓手）
        self._resize_helper = XhanggeResizeHelper(self)
        # 鼠标在主窗口上时显示粉色猫爪指针
        xhangge_apply_paw_cursor(self)

        # ---- 启动时恢复：选中最近的一个会话（没有就新建一个） ----
        sessions = self.db.list_sessions()
        if sessions:
            self.current_session_id = sessions[0]["id"]
        else:
            self.current_session_id = self.db.create_session()
        # 把该会话的历史聊天记录显示出来
        self.chat_area.load_history(
            self.db.get_messages(self.current_session_id)
        )
        self._refresh_sessions()

    # ============================================================
    # 界面组装
    # ============================================================
    def _build_ui(self):
        """搭建整体界面结构：标题栏在上，侧边栏和聊天区在下。"""
        # 最外层的"圆角矩形卡片"：窗口本体是透明的，
        # 由它画出底色、细描边和 14px 圆角（样式在 themes.py 的
        # QFrame#MainWindowFrame 规则里，三套主题共用模板自动生成）
        frame = QFrame()
        frame.setObjectName("MainWindowFrame")
        self.setCentralWidget(frame)

        root = QVBoxLayout(frame)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部标题栏（它的 QSS 自带左上/右上圆角，和框架拼成完整圆角）
        self.title_bar = XhanggeTitleBar(self)
        root.addWidget(self.title_bar)

        # 中间主体：侧边栏（左，左下圆角） + 聊天区（右，右下圆角）
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = XhanggeSidebar(self._settings_for_sidebar())
        self.chat_area = XhanggeChatArea()

        body.addWidget(self.sidebar)
        body.addWidget(self.chat_area, 1)  # 参数 1 = 聊天区占据剩余空间
        root.addLayout(body)

        # 右下角的"拖拽调整大小"小把手（无边框窗口没有系统边框可拖，
        # 靠这个小把手从右下角拉伸窗口）
        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(16, 16)
        self._size_grip.raise_()  # 永远浮在最上层，不被聊天区盖住

        # ---- 接线：把各个零件的信号连到对应的处理函数 ----
        self._connect_signals()

    def _settings_for_sidebar(self):
        """把主窗口持有的设置整理一份给侧边栏（用于恢复界面状态）。

        侧边栏瘦身后只用得到"学习模式"（用户名/主题搬去了 ⚙️ 设置），
        但整份传过去也没关系，多出来的键它自己忽略喵。
        """
        return {
            "mode": self.current_mode,
        }

    def _connect_signals(self):
        """集中接线：谁发出信号，就由哪个函数响应。"""
        # 侧边栏的操作
        self.sidebar.new_session_requested.connect(self._new_session)
        self.sidebar.session_selected.connect(self._select_session)
        self.sidebar.session_rename_requested.connect(self._rename_session)
        self.sidebar.session_delete_requested.connect(self._delete_session)
        self.sidebar.mode_changed.connect(self._on_mode_changed)
        # 聊天区
        self.chat_area.send_requested.connect(self._on_send_requested)
        self.chat_area.stop_requested.connect(self._on_stop_requested)
        # 学习文档技能（输入框上方的「📖 学习文档喵」按钮）
        self.chat_area.skill_requested.connect(self._on_skill_requested)
        # 导出技能产出为 .md 文件（气泡下的「💾 导出喵」按钮）
        self.chat_area.export_requested.connect(self._on_export_requested)
        # Chat / Agent 模式切换（工具条上的胶囊按钮）
        self.chat_area.mode_switched.connect(self._on_mode_switched)

    # ============================================================
    # 窗口控制（标题栏按钮的动作用）
    # ============================================================
    def xhangge_toggle_maximize(self):
        """最大化 / 还原窗口。"""
        if self.isMaximized():
            self.showNormal()
            self.title_bar.max_btn.setText("▢")  # 还原后按钮显示"最大化"图标
        else:
            self.showMaximized()
            self.title_bar.max_btn.setText("❐")  # 最大化后按钮显示"还原"图标

    def xhangge_toggle_always_on_top(self, checked):
        """窗口置顶开关。

        这段在干什么：
        WindowStaysOnTopHint 是 Qt 的窗口标志，加上后窗口永远在别的软件上面，
        方便边看网课/文档边和雪花喵学习喵。
        注意：改窗口标志后必须再 show() 一次才生效。
        """
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()

    def xhangge_toggle_sidebar(self, checked):
        """侧边栏显示/隐藏开关。"""
        self.sidebar.setVisible(checked)

    def resizeEvent(self, event):
        """窗口大小变化：让右下角的拖拽把手始终待在右下角。"""
        super().resizeEvent(event)
        self._size_grip.move(self.width() - 18, self.height() - 18)

    # ============================================================
    # 发送消息 / 接收回答（核心流程）
    # ============================================================
    def _on_send_requested(self, text):
        """用户发出一条消息：完整的"问雪花喵"流程。

        入口处先看一眼关键词：如果用户是在喊学习技能
        （比如"把刚才讲的生成浅浅学喵"），就走技能流程而不是普通聊天。
        """
        # 双保险：生成中不允许再发（按钮此时是"停止"）
        if self._worker is not None:
            return
        # 没有会话时先创建一个（理论上不会发生，保险）
        if self.current_session_id is None:
            self.current_session_id = self.db.create_session()

        # ---- 关键词识别：这条消息是在喊技能吗？ ----
        skill_key = xhangge_detect_skill(text)

        # 1. 把用户消息存进数据库；如果这是会话的第一句，
        #    顺便把会话标题改成这句话的前 20 个字
        self.db.add_message(self.current_session_id, "user", text)
        self.db.ensure_session_title(self.current_session_id, text)

        # 2. 界面上显示用户气泡 + 开始一条新的雪花喵气泡
        self.chat_area.add_user_message(text)
        if skill_key is not None:
            # 技能流程：气泡提示改成"正在整理"，让用户知道不是普通回答
            self._start_skill_stream(skill_key)
            return

        # ---- 会话状态一次读齐：模式 + 知识库检索开关/绑定 ----
        state = self.db.xhangge_get_session_state(self.current_session_id)

        # ---- Agent 模式：交给能自己动手干活的 Agent 线程 ----
        # （Agent 查资料靠自己调工具，不走聊天前的自动检索注入）
        if state.chat_mode == "agent":
            work_dir = (self.xhangge_all_settings.get("agent_work_dir", "") or "").strip()
            if work_dir:
                self._start_agent_stream(text)
                return
            # 防御：会话还停在 agent 模式，但工作区被清掉了 → 退回普通聊天
            show_warning_dialog(
                self,
                "工作区不见了喵",
                "这个会话还是 Agent 模式，但工作目录被清掉了喵。\n"
                "雪花喵先按普通聊天回答，去「⚙️ 设置 → 🤖 Agent 喵」"
                "重新选个工作目录再开 Agent 喵～",
            )
            self.db.xhangge_set_session_mode(self.current_session_id, "chat")
            self.chat_area.set_mode("chat")
            # 不 return，继续往下走普通聊天流程

        self.chat_area.begin_assistant_message()
        self._enter_streaming_ui_state()

        # 3. 组装发给模型的消息列表 = 系统提示词(人设+模式) + 本会话全部历史
        #    （把历史带上，模型才"记得"前面聊过什么 = 会话记忆）
        system_prompt = build_system_prompt(self.current_mode, self.username)

        # ---- 3.5 知识库检索（RAG，模块五）----
        # 这个会话开了检索开关、又绑定了库 → 先去库里找资料，
        # 找到的片段包装好拼在系统提示词后面。
        # 没开开关 / 没绑库 / 什么都没收着 → 拿到空字符串，等于没这回事。
        if state.rag_enabled and state.kb_ids:
            try:
                # 检索用的是用户刚发的这句话（本地向量化，通常零点几秒）
                chunks = xhangge_retrieve(self.db, text, state.kb_ids)
            except Exception as e:
                # 最常见：Ollama 没开（向量化模型 bge-m3 跑在本地 Ollama 里）
                self._on_stream_error(
                    "翻知识库没成功喵 😿\n\n"
                    "知识库检索需要本地 Ollama 开着"
                    "（向量化模型 " + xhangge_config.XHANGGE_EMBED_MODEL
                    + " 跑在那里喵）。\n\n"
                    "1. 终端里运行：ollama serve\n"
                    "2. 或者点标题栏 📚 把「回答时翻知识库」关掉喵\n\n"
                    "（" + type(e).__name__ + "）"
                )
                return
            rag_section = build_rag_context_section(chunks)
            if rag_section:
                system_prompt += rag_section

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in self.db.get_messages(self.current_session_id):
            api_messages.append(
                {"role": msg["role"], "content": msg["content"]}
            )
        self._start_chat_worker(api_messages)

    # ============================================================
    # Agent 模式（模块一）
    # ============================================================
    def _start_agent_stream(self, text):
        """启动一次 Agent 任务（Agent 模式下用户发消息走这里）。

        和普通聊天的区别：先立一张"步骤卡片"（Agent 正在做什么，
        一步步显示），回答气泡照常流式打字。Agent 的系统提示词、
        工具、人工确认都由 services 层的 XhanggeAgentWorker 负责。
        """
        # 步骤卡片先立起来（在回答气泡上面）
        self.chat_area.begin_agent_steps()
        self.chat_area.begin_assistant_message(
            hint="*雪花喵出动喵... 🤖🐾*"
        )
        self._enter_streaming_ui_state()
        # Agent 运行期间让「Agent 喵」按钮保持可点，用户再点一下就能停止任务
        # （set_streaming 默认会把按钮灰掉，这里单独放回来）
        self.chat_area.set_mode_btn_enabled(True)

        # Agent 的上下文 = 本会话全部历史（含刚存的这条消息），
        # 系统提示词（人设+任务书+经验笔记）由 worker 自己组装
        history = self.db.get_messages(self.current_session_id)
        self._worker = XhanggeAgentWorker(
            self.db, self.current_session_id, history,
            self.xhangge_all_settings,
        )
        # 前三个信号和普通聊天同名同义，处理函数直接复用
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.stream_error.connect(self._on_stream_error)
        # Agent 特有的两个：步骤汇报 + 人工确认请求
        self._worker.step_received.connect(self._on_agent_step)
        self._worker.hitl_requested.connect(self._on_hitl_requested)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_agent_step(self, icon, text):
        """Agent 汇报了一步 → 加进步骤卡片。"""
        self.chat_area.add_agent_step(icon + " " + text)

    def _on_hitl_requested(self, tool_name, label, target, preview):
        """Agent 停下来请求人工确认（此刻 Agent 线程正在等待）。

        弹确认窗（模态）：用户点了按钮才返回，
        把结果喂回 worker，Agent 才会继续跑或放弃这个操作。
        """
        approve = show_hitl_dialog(self, label, target, preview)
        if self._worker is not None:
            self._worker.provide_hitl_decision(
                approve, "" if approve else "用户不同意喵"
            )

    def _on_mode_switched(self, mode_key):
        """用户切了 Chat / Agent。

        两条门控规则：
        1. 想开 Agent 但没有工作区 → 弹提示，保持 chat 不激活；
        2. Agent 正在跑时切回 chat → 直接中断当前 Agent 任务。
        """
        # 关掉 Agent（切回 chat）：如果 Agent 正在跑，先中断它
        if mode_key == "chat" and isinstance(self._worker, XhanggeAgentWorker):
            self._worker.request_stop()
            self.db.xhangge_set_session_mode(self.current_session_id, "chat")
            return

        # 想开 Agent：先查工作区，没有就拦住
        if mode_key == "agent":
            work_dir = (self.xhangge_all_settings.get("agent_work_dir", "") or "").strip()
            if not work_dir:
                show_warning_dialog(
                    self,
                    "还没选工作区喵",
                    "Agent 要先在「⚙️ 设置 → 🤖 Agent 喵」里选一个工作目录，\n"
                    "她才敢帮你改文件、跑命令喵～\n\n"
                    "选好工作区之后，再回来点「🤖 Agent 喵」就能开啦。",
                )
                # 保持 chat 模式：把按钮弹回去（set_mode 内部屏蔽信号，不会死循环）
                self.chat_area.set_mode("chat")
                self.db.xhangge_set_session_mode(self.current_session_id, "chat")
                return

        self.db.xhangge_set_session_mode(self.current_session_id, mode_key)

    # ============================================================
    # 后台线程的启动 / 收尾（普通聊天和学习技能共用）
    # ============================================================
    def _enter_streaming_ui_state(self):
        """进入"生成中"的界面状态：按钮变停止、侧边栏锁住。

        普通聊天和技能生成都要做这一套，抽出来共用。
        """
        self.chat_area.set_streaming(True)
        # 生成期间禁止切换/新建/删除会话，防止状态混乱
        self.sidebar.set_controls_enabled(False)

    def _start_chat_worker(self, api_messages):
        """启动后台线程去请求模型（界面不卡）。

        模型实例在这里（界面线程）取好再交给线程：
        取的这一步要读数据库判断"用本地还是在线"，而 SQLite 连接不能跨线程用。
        好在这一步只是读配置造对象，不发网络请求，放在界面线程里不会卡。
        """
        try:
            llm = xhangge_get_llm(self.db)
            backend_label = xhangge_get_backend_label(self.db)
        except Exception as e:
            # 造模型实例本身就失败了（比如在线配置的地址格式不合法）。
            # 这时候线程还没起来，直接把气泡变成错误提示收尾。
            self._on_stream_error(
                "没能准备好模型喵 😿\n"
                "去设置 → 🧠 模型喵 里检查一下配置～\n\n"
                "（" + type(e).__name__ + "）" + str(e)[:200]
            )
            return
        self._worker = XhanggeChatWorker(llm, api_messages, backend_label)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.stream_error.connect(self._on_stream_error)
        # 线程真正结束后自动清理对象，防止内存泄漏
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    # ============================================================
    # 学习文档技能（模块四）
    # ============================================================
    def _on_skill_requested(self, skill_key):
        """用户点了工具条上的「📖 学习文档喵」按钮里的某一档。"""
        # 生成中不允许叠加（按钮已灰掉，这里再挡一道）
        if self._worker is not None:
            return
        if self.current_session_id is None:
            self.current_session_id = self.db.create_session()

        # 按钮触发时没有"用户消息"，技能的素材就是本会话已有的聊天。
        # 一条聊天都没有 → 没东西可整理，友好提醒而不是硬生成。
        # （和下面生成时用同一个"排除技能产出"的口径：
        #   只生成过资料但没聊过天，也算没素材喵）
        history = self.db.get_messages(
            self.current_session_id, exclude_skill=True
        )
        if not history:
            show_warning_dialog(
                self,
                "还没有可以整理的内容喵",
                "这个会话里还没聊过东西喵～\n\n"
                "先问雪花喵几个问题，\n"
                "再来点「📖 学习文档喵」把学到的整理成资料喵 ✨",
            )
            return
        self._start_skill_stream(skill_key)

    def _start_skill_stream(self, skill_key):
        """启动一次技能生成（按钮和关键词两条路都汇到这里）。

        参数 skill_key：技能标识（doc / qa_shallow / qa_medium / qa_deep）

        这段在干什么：
        1. 从数据库读出本会话的聊天记录（关键词触发时，
           用户那句"生成浅浅学喵"已经存进去了，正好当素材的一部分）
        2. 交给 services 层组装成消息（人设+任务书+历史+开工指令）
        3. 后面的启动流程和普通聊天完全一样——复用同一个线程类
        """
        self._active_skill = skill_key

        # 素材 = "聊过的内容"。exclude_skill=True 把之前生成的
        # 文档/问答集排除掉——实测不排除的话，模型会把旧问答集
        # 整段抄进新文档里喵。
        history = self.db.get_messages(
            self.current_session_id, exclude_skill=True
        )
        api_messages = build_skill_messages(history, skill_key, self.username)

        # 气泡先亮出"正在整理"的提示，用户才知道这次不是普通回答
        self.chat_area.begin_assistant_message(
            hint="*雪花喵正在翻看聊天记录、"
            + ("整理学习文档" if skill_key == "doc" else "出问答集")
            + "喵... 📚🐾*"
        )
        self._enter_streaming_ui_state()
        self._start_chat_worker(api_messages)

    def _on_chunk(self, piece):
        """收到一小段模型文字 → 追加到气泡（打字机效果）。"""
        self.chat_area.append_chunk(piece)

    def _on_stream_finished(self, full_text):
        """一条回答生成完毕（正常结束或用户中途停止）。"""
        # Agent 跑完要把步骤卡片收尾（聊天模式没开过卡片，收尾是无害的）
        if isinstance(self._worker, XhanggeAgentWorker):
            self.chat_area.finish_agent_steps(ok=True)
        self._worker = None
        # 把完整回答（含停止前的部分）存进数据库
        if full_text.strip():
            # 正在跑学习技能 → 存的时候打上 is_skill 标记，
            # 以后生成新资料时会被 exclude_skill 筛出去
            self.db.add_message(
                self.current_session_id, "assistant", full_text,
                is_skill=self._active_skill is not None,
            )
            # 如果这次跑的是学习技能 → 记一条使用流水
            # （放在"有内容"的分支里：一个字都没生成就不算用过技能）
            if self._active_skill is not None:
                skill_type, depth = XHANGGE_SKILL_DB_TYPES[self._active_skill]
                self.db.xhangge_add_skill_task(
                    self.current_session_id, skill_type, depth
                )
        # 技能状态复位（普通聊天时它本来就是 None，复位无害）。
        # 先记下这次是不是技能产出，复位后还要用来给气泡挂导出按钮。
        was_skill = self._active_skill is not None
        self._active_skill = None
        # 收尾：气泡定稿（技能产出挂「💾 导出喵」按钮）、按钮恢复"发送"、侧边栏恢复可用
        self.chat_area.finish_assistant_message(exportable=was_skill)
        self.chat_area.set_streaming(False)
        self.sidebar.set_controls_enabled(True)
        # 刷新会话列表（第一个问题会更新会话标题）
        self._refresh_sessions()

    def _on_stream_error(self, message):
        """请求出错了（连不上 Ollama 等）→ 显示友好错误。"""
        # Agent 出错也要把步骤卡片收尾（聊天模式没开过卡片，无害）
        if isinstance(self._worker, XhanggeAgentWorker):
            self.chat_area.finish_agent_steps(ok=False)
        self._worker = None
        self._active_skill = None
        self.chat_area.set_error(message)
        self.chat_area.set_streaming(False)
        self.sidebar.set_controls_enabled(True)

    def _on_stop_requested(self):
        """用户点了"停止喵" → 通知后台线程停止生成。"""
        if self._worker is not None:
            self._worker.request_stop()

    # ============================================================
    # 导出技能产出为 .md 文件（「💾 导出喵」按钮）
    # ============================================================
    def _on_export_requested(self, content):
        """用户点了某条技能产出气泡下的「💾 导出喵」。

        流程（按用户确认的需求）：
        1. 弹出"选导出目录"对话框——可以点取消，也可以直接关掉，都不导出
        2. 点了确定 → 把内容写成一个 .md 文件（文件名自动起）
        3. 弹可爱进度条（和下载模型的进度条同一个组件）从 0 跑到 100
        4. 跑完显示"导出成功喵～"和存到了哪里

        参数 content：那条消息的 Markdown 原文
        """
        # ---- 1. 选目录（getExistingDirectory 自带"取消"按钮和右上角关闭，
        #         用户用哪种方式放弃都返回空字符串）----
        start_dir = self._last_export_dir or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "选一个文件夹存放导出的资料喵～", start_dir
        )
        if not folder:
            return  # 用户取消 / 直接关掉了窗口，什么都不做

        # ---- 2. 起文件名：会话标题 + 日期时间，重名几乎不可能 ----
        title = self.db.get_session_title(self.current_session_id) or "学习资料"
        # 把文件系统不欢迎的字符（/ \ : * ? " < > |）换成 _
        safe_title = "".join(
            c if c not in '\\/:*?"<>|' else "_" for c in title
        ).strip() or "学习资料"
        stamp = xhangge_time_stamp()
        file_path = Path(folder) / ("雪花喵学习资料_" + safe_title + "_" + stamp + ".md")

        # ---- 3. 先把文件写好（写文件是瞬间的事，先写后动画最稳）----
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as e:
            show_warning_dialog(
                self,
                "导出没成功喵",
                "文件写不进去喵 😿\n\n"
                "常见原因：\n"
                "1. 选的文件夹没有写入权限\n"
                "2. 磁盘满了\n\n（" + str(e) + "）",
            )
            return
        self._last_export_dir = folder

        # ---- 4. 可爱进度条跑完一程，再报"导出成功喵～" ----
        dlg = XhanggeExportProgressDialog(self, self.current_theme)
        dlg.center_on_parent()
        # 注意：文件此刻已经落盘了，动画纯粹是给用户的可爱反馈
        dlg.xhangge_start(
            lambda: dlg.xhangge_show_result(
                True, "已存到：\n" + str(file_path)
            )
        )
        dlg.exec()

    # ============================================================
    # 会话管理
    # ============================================================
    def _refresh_sessions(self):
        """从数据库重新读取会话列表，刷新侧边栏显示。"""
        sessions = self.db.list_sessions()
        self.sidebar.refresh_sessions(sessions, self.current_session_id)

    def _new_session(self):
        """新建会话：建库记录、清空聊天区、刷新列表。"""
        if self._worker is not None:
            return
        self.current_session_id = self.db.create_session()
        self.chat_area.clear_chat()
        # 新会话从聊天模式开始（模式是每个会话各自的设置）
        self.chat_area.set_mode("chat")
        self._refresh_sessions()

    def _select_session(self, session_id):
        """切换到用户点选的会话：加载它的历史聊天记录。"""
        if self._worker is not None:
            return
        if session_id == self.current_session_id:
            return  # 点的就是当前会话，不用动
        self.current_session_id = session_id
        self.chat_area.load_history(self.db.get_messages(session_id))
        # 恢复这个会话上次的 Chat/Agent 模式（每个会话各自记住自己的模式）
        self.chat_area.set_mode(
            self.db.xhangge_get_session_state(session_id).chat_mode
        )

    def _rename_session(self, session_id):
        """重命名会话（右键菜单触发）：弹窗输入新名字。"""
        if self._worker is not None:
            return
        current_title = self.db.get_session_title(session_id) or ""
        new_title = show_rename_dialog(self, current_title)
        if new_title:  # 用户点取消时返回 None，不做事
            self.db.rename_session(session_id, new_title)
            self._refresh_sessions()

    def _delete_session(self, session_id):
        """删除会话（右键菜单触发）：先确认，防止误删。"""
        if self._worker is not None:
            return
        title = self.db.get_session_title(session_id) or "这个会话"
        confirmed = show_confirm_dialog(
            self,
            "删除会话喵？",
            "「" + title + "」和它的全部聊天记录都会消失喵，\n确定要删除吗？",
        )
        if not confirmed:
            return
        self.db.delete_session(session_id)
        # 如果删的是当前会话 → 切到最新的会话；一个不剩就新建
        if session_id == self.current_session_id:
            sessions = self.db.list_sessions()
            if sessions:
                self.current_session_id = sessions[0]["id"]
                self.chat_area.load_history(
                    self.db.get_messages(self.current_session_id)
                )
            else:
                self.current_session_id = self.db.create_session()
                self.chat_area.clear_chat()
        self._refresh_sessions()

    # ============================================================
    # 用户设置（用户名 / 主题 / 模式）
    # ============================================================
    def _on_username_changed(self, name):
        """用户改了昵称：记住它（下次提问就生效）。"""
        self.username = name.strip()
        self._save_settings()

    def _on_theme_changed(self, theme_key):
        """用户换了主题：立刻给整个软件换皮肤。"""
        self.current_theme = theme_key
        self._apply_theme(theme_key)
        self._save_settings()

    def _on_mode_changed(self, mode_key):
        """用户换了学习模式：只影响下一条消息的回答方式。"""
        self.current_mode = mode_key
        self._save_settings()

    def _apply_theme(self, theme_key):
        """把主题 QSS 应用到整个应用程序，带淡入淡出过渡（而不是瞬间换肤）。"""
        qss = XHANGGE_THEMES.get(theme_key, XHANGGE_THEMES["pink"])

        # 淡出 → 换肤 → 淡入
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(1.0)
        self.setGraphicsEffect(effect)

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(100)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def _swap_and_fade_in():
            QApplication.instance().setStyleSheet(qss)
            fade_in = QPropertyAnimation(effect, b"opacity", self)
            fade_in.setDuration(150)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

            def _clear():
                # 只有这个 effect 还是当前 effect 时才清掉，
                # 避免快速切换主题时，旧动画误删新主题的 effect
                if self.graphicsEffect() is effect:
                    self.setGraphicsEffect(None)

            fade_in.finished.connect(_clear)
            fade_in.start()

        fade_out.finished.connect(_swap_and_fade_in)
        fade_out.start()

    def _save_settings(self):
        """把当前设置写进设置文件，下次启动自动恢复。

        注意这里是「先更新，再整份写出」：
        把界面上这三项的最新值盖到 self.xhangge_all_settings 上，
        然后把整份字典写出去。这样设置窗里改的模型、工作目录等等
        都会被原样保留，不会被这次保存冲掉。
        """
        self.xhangge_all_settings["username"] = self.username
        self.xhangge_all_settings["theme"] = self.current_theme
        self.xhangge_all_settings["mode"] = self.current_mode
        xhangge_config.save_xhangge_settings(self.xhangge_all_settings)

    # ============================================================
    # 设置窗口（标题栏 ⚙️ 按钮）
    # ============================================================
    def xhangge_open_settings(self):
        """打开设置窗口。"""
        # 生成回答的过程中不让开设置：万一这时候把模型换了，
        # 正在跑的那次请求就会处在一个半新半旧的状态里，容易出怪问题。
        if self._worker is not None:
            return

        dialog = XhanggeSettingsDialog(self, self.db, self.xhangge_all_settings)
        # 设置窗只管界面，落盘和实际生效都由主窗口来做（单一出口，不会打架）
        dialog.settings_saved.connect(self._on_settings_from_dialog)
        dialog.backend_changed.connect(self._on_backend_changed)
        # 🎨 外观页换主题 / 👤 我的信息页改用户名或头像 → 主窗口立刻生效
        dialog.theme_changed.connect(self._on_theme_changed)
        dialog.username_changed.connect(self._on_username_changed)
        dialog.avatar_changed.connect(self._on_avatar_changed)
        dialog.exec()

    def _on_avatar_changed(self):
        """用户上传/删除了头像 → 重新画当前会话的聊天气泡（换新头像）。"""
        # 头像是气泡渲染时取的，已经画出来的不会自己变；
        # 把历史重画一遍，所有用户头像就都换成新的了喵
        self.chat_area.load_history(
            self.db.get_messages(self.current_session_id)
        )

    def _on_settings_from_dialog(self, new_settings):
        """设置窗说「我这边改了这些」→ 合并进来并落盘。"""
        # update 而不是直接替换：设置窗只拿到了它关心的那些项，
        # 用 update 合并才不会把它没碰过的项弄丢。
        self.xhangge_all_settings.update(new_settings)
        xhangge_config.save_xhangge_settings(self.xhangge_all_settings)

    def _on_backend_changed(self):
        """模型后端换了（本地↔在线，或换了模型名）。

        这段在干什么：
        llm_router 里缓存着一个已经建好的模型连接对象，
        目的是每次聊天不用重新构造。但后端一换，缓存里那个就过期了。
        调 xhangge_reload_llm() 把缓存清掉，下次聊天时会按新配置重新建一个。
        """
        xhangge_reload_llm()

    def xhangge_open_kb_window(self):
        """打开知识库管理窗口（标题栏 📚 按钮）。"""
        # 生成中不让开：检索状态和正在生成的回答可能对不上
        if self._worker is not None:
            return
        dialog = XhanggeKbDialog(
            self, self.db, self.current_session_id, self.current_theme
        )
        dialog.exec()

    # ============================================================
    # 退出清理
    # ============================================================
    def closeEvent(self, event):
        """关闭窗口时：停掉还在生成的线程、关闭数据库，干干净净地退出。"""
        if self._worker is not None:
            self._worker.request_stop()
            # 最多等 3 秒，避免卡住退出
            self._worker.wait(3000)
            self._worker = None
        self.db.close()
        super().closeEvent(event)
