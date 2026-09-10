# Author: xhangge
# This project is created by xhangge
"""
main_window —— 主窗口（整个软件的"总调度中心"）
负责把各个零件组装到一起：
- 顶部：自定义标题栏（🐱 标题 + 置顶/侧边栏/最小化/最大化/关闭按钮）
- 左边：侧边栏（会话管理、用户名、主题、学习模式）
- 右边：聊天区（气泡对话 + 输入框）

为什么自己画标题栏：
去掉系统自带标题栏（无边框窗口）后，软件才能从头到脚都是
粉色圆角可爱风；最小化/最大化/关闭这些按钮就由我们自己画。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from core.database import XhanggeDatabase
from core.ollama_client import XhanggeChatWorker
from core.prompts import build_system_prompt
from ui.chat_area import XhanggeChatArea
from ui.dialogs import show_confirm_dialog, show_rename_dialog
from ui.sidebar import XhanggeSidebar
from ui.themes import XHANGGE_THEMES
from core import xhangge_config


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
        icon_label = QLabel("🐱")
        icon_label.setObjectName("TitleIcon")
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
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

        # ---- 窗口基本设置 ----
        self.setWindowTitle(xhangge_config.APP_NAME)
        self.resize(1100, 750)          # 默认窗口大小
        self.setMinimumSize(900, 600)   # 最小尺寸，防止缩太小按钮挤没了
        # 无边框：去掉系统默认的灰色标题栏（我们的粉色标题栏自己画）
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )

        # ---- 数据库 ----
        self.db = XhanggeDatabase()

        # ---- 界面组装 ----
        self._build_ui()

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
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部标题栏
        self.title_bar = XhanggeTitleBar(self)
        root.addWidget(self.title_bar)

        # 中间主体：侧边栏（左） + 聊天区（右）
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
        """把主窗口持有的设置整理一份给侧边栏（用于恢复界面状态）。"""
        return {
            "username": self.username,
            "theme": self.current_theme,
            "mode": self.current_mode,
        }

    def _connect_signals(self):
        """集中接线：谁发出信号，就由哪个函数响应。"""
        # 侧边栏的操作
        self.sidebar.new_session_requested.connect(self._new_session)
        self.sidebar.session_selected.connect(self._select_session)
        self.sidebar.session_rename_requested.connect(self._rename_session)
        self.sidebar.session_delete_requested.connect(self._delete_session)
        self.sidebar.username_changed.connect(self._on_username_changed)
        self.sidebar.theme_changed.connect(self._on_theme_changed)
        self.sidebar.mode_changed.connect(self._on_mode_changed)
        # 聊天区
        self.chat_area.send_requested.connect(self._on_send_requested)
        self.chat_area.stop_requested.connect(self._on_stop_requested)

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
        """用户发出一条消息：完整的"问雪花喵"流程。"""
        # 双保险：生成中不允许再发（按钮此时是"停止"）
        if self._worker is not None:
            return
        # 没有会话时先创建一个（理论上不会发生，保险）
        if self.current_session_id is None:
            self.current_session_id = self.db.create_session()

        # 1. 把用户消息存进数据库；如果这是会话的第一句，
        #    顺便把会话标题改成这句话的前 20 个字
        self.db.add_message(self.current_session_id, "user", text)
        self.db.ensure_session_title(self.current_session_id, text)

        # 2. 界面上显示用户气泡 + 开始一条新的雪花喵气泡
        self.chat_area.add_user_message(text)
        self.chat_area.begin_assistant_message()
        self.chat_area.set_streaming(True)
        # 生成期间禁止切换/新建/删除会话，防止状态混乱
        self.sidebar.set_controls_enabled(False)

        # 3. 组装发给模型的消息列表 = 系统提示词(人设+模式) + 本会话全部历史
        #    （把历史带上，模型才"记得"前面聊过什么 = 会话记忆）
        system_prompt = build_system_prompt(self.current_mode, self.username)
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in self.db.get_messages(self.current_session_id):
            api_messages.append(
                {"role": msg["role"], "content": msg["content"]}
            )

        # 4. 启动后台线程去请求模型（界面不卡）
        self._worker = XhanggeChatWorker(api_messages)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.stream_finished.connect(self._on_stream_finished)
        self._worker.stream_error.connect(self._on_stream_error)
        # 线程真正结束后自动清理对象，防止内存泄漏
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_chunk(self, piece):
        """收到一小段模型文字 → 追加到气泡（打字机效果）。"""
        self.chat_area.append_chunk(piece)

    def _on_stream_finished(self, full_text):
        """一条回答生成完毕（正常结束或用户中途停止）。"""
        self._worker = None
        # 把完整回答（含停止前的部分）存进数据库
        if full_text.strip():
            self.db.add_message(self.current_session_id, "assistant", full_text)
        # 收尾：气泡定稿、按钮恢复"发送"、侧边栏恢复可用
        self.chat_area.finish_assistant_message()
        self.chat_area.set_streaming(False)
        self.sidebar.set_controls_enabled(True)
        # 刷新会话列表（第一个问题会更新会话标题）
        self._refresh_sessions()

    def _on_stream_error(self, message):
        """请求出错了（连不上 Ollama 等）→ 显示友好错误。"""
        self._worker = None
        self.chat_area.set_error(message)
        self.chat_area.set_streaming(False)
        self.sidebar.set_controls_enabled(True)

    def _on_stop_requested(self):
        """用户点了"停止喵" → 通知后台线程停止生成。"""
        if self._worker is not None:
            self._worker.request_stop()

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
        self._refresh_sessions()

    def _select_session(self, session_id):
        """切换到用户点选的会话：加载它的历史聊天记录。"""
        if self._worker is not None:
            return
        if session_id == self.current_session_id:
            return  # 点的就是当前会话，不用动
        self.current_session_id = session_id
        self.chat_area.load_history(self.db.get_messages(session_id))

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
        """把主题 QSS 应用到整个应用程序（所有窗口一起换装）。"""
        qss = XHANGGE_THEMES.get(theme_key, XHANGGE_THEMES["pink"])
        QApplication.instance().setStyleSheet(qss)

    def _save_settings(self):
        """把当前设置写进设置文件，下次启动自动恢复。"""
        xhangge_config.save_xhangge_settings(
            {
                "username": self.username,
                "theme": self.current_theme,
                "mode": self.current_mode,
            }
        )

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
