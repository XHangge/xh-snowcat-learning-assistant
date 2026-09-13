# Author: xhangge
# This project is created by xhangge
"""
chat_area —— 聊天区（软件的正中心）
负责：
1. 显示聊天气泡（用户消息在右、粉色；雪花喵回答在左、白底）
2. 流式打字机效果：模型每生成一小段文字，气泡就实时"长"出来一点
3. 底部输入框和发送/停止按钮
4. 欢迎语和历史记录加载

技术小知识：
- 模型的回答里常带 Markdown 格式（标题/列表/代码块），
  所以雪花喵的气泡用 QTextBrowser + setMarkdown() 渲染，能显示丰富的格式；
  用户的气泡用 QLabel 显示纯文本就够了。
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.xhangge_avatars import (
    xhangge_catgirl_label,
    xhangge_hand_cursor,
    xhangge_ibeam_cursor,
    xhangge_paw_cursor,
    xhangge_user_label,
)
from services.xhangge_skill_service import XHANGGE_SKILL_MENU

# 雪花喵回答前显示的"思考中"提示文字（Markdown 斜体语法）
THINKING_HINT = "*雪花喵思考中喵... 🐾*"


def _xhangge_button_press_animation(button):
    """给按钮加"猫爪按压"缩放回弹：按下缩小 8%，松开带弹性回弹。

    用几何动画模拟缩放（按钮在布局里，快速缩放视觉上就是"按压"感），
    按下 80ms 缩到 92%，松开 180ms 用 OutBack 曲线弹回（带一点过冲）。
    """
    original = {"geo": button.geometry()}

    def _scaled(factor):
        g = original["geo"]
        w = int(g.width() * factor)
        h = int(g.height() * factor)
        return QRect(
            g.x() + (g.width() - w) // 2,
            g.y() + (g.height() - h) // 2,
            w,
            h,
        )

    def _shrink():
        original["geo"] = button.geometry()  # 每次按下前记录当前几何
        anim = QPropertyAnimation(button, b"geometry", button)
        anim.setDuration(80)
        anim.setStartValue(_scaled(1.0))
        anim.setEndValue(_scaled(0.92))
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()

    def _restore():
        anim = QPropertyAnimation(button, b"geometry", button)
        anim.setDuration(180)
        anim.setStartValue(_scaled(0.92))
        anim.setEndValue(_scaled(1.0))
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.start()

    button.pressed.connect(_shrink)
    button.released.connect(_restore)


class XhanggeInputEdit(QTextEdit):
    """底部输入框：支持"回车发送、Shift+回车换行"。

    QTextEdit 默认回车是换行，这里重写按键事件改变行为，
    更符合大家使用聊天软件的习惯喵。
    """

    # 按下回车时发出的信号（输入框自己不发送消息，交给外层处理）
    enter_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 打字时显示粉色 I 型光标（QTextEdit 的编辑区是 viewport）
        self.viewport().setCursor(xhangge_ibeam_cursor())

    def keyPressEvent(self, event: QKeyEvent):
        """重写按键处理：这段在判断"按下的是哪个键"。

        - 普通回车（没按住 Shift）→ 发出 enter_pressed 信号（= 想发送）
        - Shift + 回车 → 正常换行（调用父类的默认处理）
        """
        is_enter = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if is_enter and not shift_held:
            self.enter_pressed.emit()
            return  # 不再交给父类处理（父类会把它当成换行）
        # 其它按键（包括 Shift+回车）走默认行为
        super().keyPressEvent(event)


class XhanggeMarkdownBubble(QTextBrowser):
    """雪花喵的回答气泡：能渲染 Markdown，而且高度自动跟随内容。

    为什么需要"高度自适应"：
    QTextBrowser 自带滚动条，默认高度固定，放进聊天气泡里
    会出现"气泡里套一个滚动条"的怪样子。
    这里监听文档尺寸变化，让气泡高度永远刚好包住内容。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 允许点击回答里的链接
        self.setOpenExternalLinks(True)
        # 鼠标在 AI 气泡上时显示猫爪（QTextBrowser 的编辑区默认是 I 型，
        # 但这里只读、不可输入，改成猫爪更统一；文字仍可选中复制）
        self.viewport().setCursor(xhangge_paw_cursor())
        # 关掉自己的滚动条（高度自适应后用不到）
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)  # 去掉 QTextBrowser 默认边框
        self.setReadOnly(True)                    # 只读（用户可以选中复制，但不能编辑）
        # 允许鼠标选中文字复制
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        # 监听"文档尺寸变化"：流式追加文字、窗口宽度变化时都会触发，
        # 一旦触发就重新计算自己该多高
        self.document().documentLayout().documentSizeChanged.connect(
            self._adjust_height
        )
        self.setFixedHeight(24)  # 初始最小高度

    def set_markdown_text(self, text):
        """设置气泡内容（text 是 Markdown 格式的字符串）"""
        # 把原文挂在控件身上。渲染出来的富文本没法还原回 Markdown，
        # 而「💾 导出喵」要导的是 Markdown 原文，所以这里留一份底。
        self.xhangge_raw_text = text
        self.setMarkdown(text)
        self._adjust_height()

    def _adjust_height(self, *args):
        """把控件高度调成"文档实际需要的高度 + 一点余量"。"""
        doc_height = int(self.document().size().height())
        # +16 是上下内边距的余量；max() 保证不会缩到看不见
        self.setFixedHeight(max(doc_height + 16, 24))


class XhanggeChatArea(QWidget):
    """聊天区整体：上方消息滚动区 + 下方输入栏。"""

    # ---- 对外信号 ----
    send_requested = Signal(str)   # 用户要发送一条消息（参数：消息文本）
    stop_requested = Signal()      # 用户要点"停止生成"
    skill_requested = Signal(str)  # 用户点了学习技能（参数：技能标识）
    # 用户要导出某条技能产出（参数：那条消息的 Markdown 原文）
    export_requested = Signal(str)
    # 用户切换了 Chat / Agent 模式（参数："chat" 或 "agent"）
    mode_switched = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # ChatAreaRoot：最外层画底色 + 右下圆角（配合主窗口圆角矩形）
        self.setObjectName("ChatAreaRoot")
        # 是否正处于"自动吸底"状态：
        # 打开会话时定位到最底部、流式输出时跟着往下滚；
        # 用户往上翻历史时自动暂停（别把正在看消息的人拽下去喵），
        # 滚回底部附近后自动恢复。
        self._stick_to_bottom = True
        # 是否正处于"模型生成中"状态（决定发送按钮显示"发送"还是"停止"）
        self._streaming = False
        # 正在流式输出中的气泡（回答完成后清空）
        self._active_bubble = None
        self._active_frame = None
        # 当前流式回答已累积的文字
        self._accumulated = ""
        # 所有气泡框，窗口改变大小时统一调整最大宽度
        self._bubble_frames = []

        # ============ 整体布局：上面滚动区 + 下面输入栏 ============
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 上：消息滚动区 ----
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("ChatScroll")
        self.scroll_area.setWidgetResizable(True)  # 内容自动填满滚动区宽度
        # 滚动条一直显示着比较好看？这里选按需显示
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # 滚动区里面的"容器"：所有聊天气泡竖着排在这里面
        self.chat_container = QWidget()
        self.chat_container.setObjectName("ChatContainer")
        self.message_layout = QVBoxLayout(self.chat_container)
        self.message_layout.setContentsMargins(20, 18, 20, 18)
        self.message_layout.setSpacing(14)
        # 末尾放一个"弹簧"（stretch）：消息少时把气泡顶到上面，
        # 消息多时它被压缩到没有，不影响布局
        self.message_layout.addStretch(1)

        self.scroll_area.setWidget(self.chat_container)
        root.addWidget(self.scroll_area, 1)  # 参数 1 = 占据所有剩余高度

        # ---- "自动吸底"的接线（修过的坑）----
        # 以前靠"插入消息后 singleShot(0) 滚一次"，但 Markdown 气泡
        # 渲染完高度还会异步再长一截，滚动发生时内容还没定稿，
        # 结果就是：打开会话不在底部、流式输出跟不上。
        # 现在改盯 rangeChanged：内容高度一变（包括气泡长高）就触发，
        # 只要还处于吸底状态就跟到底，时机天然正确。
        bar = self.scroll_area.verticalScrollBar()
        bar.rangeChanged.connect(self._on_range_changed)
        # 用户拖动/滚轮 → 判断离底部多远，决定吸底要不要继续
        bar.valueChanged.connect(self._on_scroll_value_changed)

        # ---- 中：输入框上方的工具条（药丸按钮一排） ----
        # 现在放「📖 学习文档喵」；以后 Agent 的「聊天/Agent」切换也放这里。
        # 为什么不放进输入栏那一行：输入框要占满宽度，按钮挤在一起会很小。
        # 独立一整行，按钮想加几个加几个。
        root.addWidget(self._build_tool_bar())

        # ---- 下：输入栏（输入框 + 发送按钮） ----
        input_bar = QWidget()
        input_bar.setObjectName("InputBar")  # 透明背景（让 ChatAreaRoot 的圆角露出来）
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 10, 16, 12)
        input_layout.setSpacing(10)

        self.input_edit = XhanggeInputEdit()
        self.input_edit.setObjectName("InputEdit")
        self.input_edit.setPlaceholderText(
            "想问什么就问雪花喵吧喵～（Enter 发送，Shift+Enter 换行）"
        )
        self.input_edit.setAcceptRichText(False)  # 只收纯文本
        self.input_edit.setFixedHeight(76)
        # 在输入框里按回车 → 尝试发送
        self.input_edit.enter_pressed.connect(self._on_enter_pressed)

        self.send_btn = QPushButton("发送喵~")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.setCursor(xhangge_hand_cursor())
        # 点击按钮：空闲时是发送，生成中是停止
        self.send_btn.clicked.connect(self._on_send_clicked)
        # 猫爪按压：缩放回弹动画
        _xhangge_button_press_animation(self.send_btn)

        input_layout.addWidget(self.input_edit, 1)  # 输入框占满剩余宽度
        input_layout.addWidget(self.send_btn)
        root.addWidget(input_bar)

        # 显示欢迎语（第一次打开时聊天区中间的可爱提示）
        self._welcome_label = None
        self._show_welcome()

    # ============================================================
    # 工具条（输入框上方那排小药丸按钮）
    # ============================================================
    def _build_tool_bar(self):
        """搭工具条：一行透明背景，左边放各种功能按钮。"""
        bar = QFrame()
        bar.setObjectName("ToolCapsuleBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 2)
        layout.setSpacing(8)

        # ---- Chat / Agent 模式开关（胶囊按钮，按下状态 = Agent）----
        # 普通聊天 = 只动嘴回答；Agent = 能自己动手干活（查资料/改文件/跑命令）
        self.mode_btn = QPushButton("🤖 Agent 喵")
        self.mode_btn.setObjectName("CapsuleBtn")
        self.mode_btn.setCursor(xhangge_hand_cursor())
        self.mode_btn.setCheckable(True)
        self.mode_btn.setToolTip(
            "关着（弹起）= 💬 聊天喵：只动嘴回答\n"
            "开着（按下）= 🤖 Agent 喵：自己动手查资料、改文件、跑命令"
        )
        self.mode_btn.toggled.connect(self._on_mode_toggled)
        layout.addWidget(self.mode_btn)

        # ---- 学习文档技能按钮 ----
        self.skill_btn = QPushButton("📖 学习文档喵")
        self.skill_btn.setObjectName("CapsuleBtn")
        self.skill_btn.setCursor(xhangge_hand_cursor())
        self.skill_btn.setToolTip(
            "把当前会话聊过的内容，整理成学习文档或问答集喵"
        )
        self.skill_btn.clicked.connect(self._show_skill_menu)
        layout.addWidget(self.skill_btn)

        layout.addStretch(1)  # 弹簧：按钮靠左，右边留白
        return bar

    # ============================================================
    # Chat / Agent 模式开关
    # ============================================================
    def _on_mode_toggled(self, checked):
        """模式按钮被点了一下：换文字 + 通知外面（主窗口会存进数据库）。"""
        # Agent 按下时换个配色感：文字变成「工作中」的样子
        self.mode_btn.setText("🤖 Agent 喵 · 已开启" if checked else "🤖 Agent 喵")
        self.mode_switched.emit("agent" if checked else "chat")

    def set_mode(self, mode_key):
        """把模式按钮设成某个状态（切换会话时恢复它上次的模式用）。

        blockSignals：恢复界面状态不该触发"用户切换了模式"的信号，
        不然一切会话就把数据库里存的模式改没了。
        """
        self.mode_btn.blockSignals(True)
        self.mode_btn.setChecked(mode_key == "agent")
        self.mode_btn.setText(
            "🤖 Agent 喵 · 已开启" if mode_key == "agent" else "🤖 Agent 喵"
        )
        self.mode_btn.blockSignals(False)

    def set_mode_btn_enabled(self, enabled):
        """单独控制「Agent 喵」按钮能不能点。

        Agent 运行期间要能再点它一下来停止任务，所以这里给主窗口
        一个单独的开关，别被 set_streaming() 里"生成中禁用按钮"的逻辑带走。
        """
        self.mode_btn.setEnabled(enabled)

    # ============================================================
    # Agent 步骤卡片（Agent 干活时显示"它正在做什么"）
    # ============================================================
    def begin_agent_steps(self):
        """Agent 开始干活：先立一张空的步骤卡片。"""
        self._remove_welcome()
        card = QFrame()
        card.setObjectName("agentStepCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        title = QLabel("🐾 雪花喵正在干活喵…")
        title.setObjectName("AgentStepTitle")
        layout.addWidget(title)
        self._steps_label = QLabel("")
        self._steps_label.setObjectName("AgentStepText")
        self._steps_label.setWordWrap(True)
        self._steps_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._steps_label)
        self._steps_lines = []
        self._insert_row(card)

    def add_agent_step(self, text):
        """Agent 汇报了一步：往步骤卡片里加一行。"""
        if getattr(self, "_steps_label", None) is None:
            return
        self._steps_lines.append(text)
        # 最多显示最近 30 行：工具一多卡片会变得巨长
        shown = self._steps_lines[-30:]
        self._steps_label.setText("\n".join(shown))
        QTimer.singleShot(0, self._scroll_to_bottom)

    def finish_agent_steps(self, ok=True):
        """Agent 干完活：卡片标题换成结果，收尾清理。"""
        if getattr(self, "_steps_label", None) is None:
            return
        title = self._steps_label.parent().findChild(QLabel, "AgentStepTitle")
        if title is not None:
            title.setText("🐾 本次 Agent 行动记录喵" if ok else "🐾 行动中止了喵")
        self._steps_label = None
        self._steps_lines = []

    def _show_skill_menu(self):
        """点「📖 学习文档喵」→ 弹出四档技能的小菜单。"""
        # QMenu 的样式全局 QSS 里已经有了（右键菜单同款）
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        # 悬浮变"小手指"。为什么写在代码里不写在 QSS 里：
        # QSS 不支持 cursor 属性（themes.py 开头注释里也提过这个坑），
        # 所以和按钮们一样在代码里设置喵。
        menu.setCursor(xhangge_hand_cursor())
        for skill_key, label, _, _ in XHANGGE_SKILL_MENU:
            # addAction 返回创建出来的动作对象，正好接它的点击信号
            action = menu.addAction(label)
            action.setData(skill_key)
            action.setToolTip("根据当前会话的聊天内容生成喵")
            action.triggered.connect(
                lambda _=False, key=skill_key: self.skill_requested.emit(key)
            )
        # 弹在按钮正下方
        menu.exec(
            self.skill_btn.mapToGlobal(
                self.skill_btn.rect().bottomLeft()
            )
        )

    # ============================================================
    # 发送 / 停止 相关
    # ============================================================
    def _on_send_clicked(self):
        """发送按钮被点击：空闲 → 发送；生成中 → 停止。"""
        if self._streaming:
            self.stop_requested.emit()
        else:
            self._send_text()

    def _on_enter_pressed(self):
        """输入框里按了回车：只在空闲时发送（生成中不动作，防止误停）。"""
        if not self._streaming:
            self._send_text()

    def _send_text(self):
        """取出输入框文字，发出"要发送"信号并清空输入框。"""
        text = self.input_edit.toPlainText().strip()
        if not text:
            return  # 空消息不发送
        self.send_requested.emit(text)
        self.input_edit.clear()

    def set_streaming(self, streaming):
        """切换"生成中"状态：换按钮文字和颜色，防止重复发送。

        这段在干什么：
        通过 setProperty 改变按钮的 QSS 属性 streaming，
        themes.py 里的 [streaming="true"] 选择器就会自动换成橙色"停止"样式。
        改完属性必须 unpolish/polish 刷新一次，样式才会立即生效。
        """
        self._streaming = streaming
        self.send_btn.setText("停止喵 ✋" if streaming else "发送喵~")
        self.send_btn.setProperty("streaming", "true" if streaming else "false")
        # 生成中把技能按钮和模式开关也灰掉：防止普通回答生成到一半，
        # 又叠加启动一次文档生成 / 切到 Agent，状态会乱套
        self.skill_btn.setEnabled(not streaming)
        self.mode_btn.setEnabled(not streaming)
        # 手动刷新样式（改 property 后 Qt 不会自动重算 QSS，要"擦一遍再画一遍"）
        self.send_btn.style().unpolish(self.send_btn)
        self.send_btn.style().polish(self.send_btn)

    # ============================================================
    # 消息气泡相关
    # ============================================================
    def _show_welcome(self):
        """显示欢迎语（聊天记录为空时）"""
        if self._welcome_label is not None:
            return
        self._welcome_label = QLabel(
            "喵呜～杂狗今天想学点什么呀？✨\n\n"
            "🐱 简单说喵：一两句话讲明白\n"
            "📖 仔细说喵：掰开揉碎讲透\n"
            "🎓 教杂狗喵：先哄小孩再上专业\n\n"
            "（在左侧边栏可以切换学习模式喵 🌸）\n"
            "（点下方「🤖 Agent 喵」可以让我自己动手干活：\n"
            "查资料、翻知识库、改文件、跑命令喵 🐾）\n"
            "（聊完之后，点「📖 学习文档喵」\n"
            "可以把聊过的内容变成文档或问答集复习喵 ✍️）"
        )
        self._welcome_label.setObjectName("WelcomeLabel")
        self._welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome_label.setWordWrap(True)
        # 插在弹簧前面，让欢迎语出现在聊天区上部
        self.message_layout.insertWidget(
            self.message_layout.count() - 1, self._welcome_label
        )

    def _remove_welcome(self):
        """有消息后把欢迎语撤掉"""
        if self._welcome_label is not None:
            self._welcome_label.setParent(None)
            self._welcome_label.deleteLater()
            self._welcome_label = None

    def _make_avatar(self, who):
        """造一个头像标签。

        who="assistant" → 雪花喵：猫娘圆形图（图加载不出来才显示 🐱）
        who="user"      → 用户：上传过的头像照片（没有/加载失败显示 🐶）
        """
        if who == "assistant":
            return xhangge_catgirl_label(38)
        return xhangge_user_label(38)

    def _insert_row(self, row):
        """把一行消息（头像+气泡）插到消息列表末尾（弹簧前面）。"""
        self.message_layout.insertWidget(self.message_layout.count() - 1, row)

    def _scroll_to_bottom(self):
        """把聊天区滚动到最底部（看到最新的消息）。"""
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_range_changed(self, _min, maxi):
        """内容高度变了（新消息插入 / Markdown 气泡渲染完长高 / 流式输出变长）。

        只要还处于吸底状态，就跟着新高度滚到底——
        这是"打开会话在底部、输出时自动下滚"的核心机制。
        """
        if self._stick_to_bottom:
            self.scroll_area.verticalScrollBar().setValue(maxi)

    def _on_scroll_value_changed(self, value):
        """滚动条位置变了（用户拖动 / 滚轮 / 程序滚动都会触发）。

        离底部超过约半屏 = 用户正在翻历史 → 暂停自动吸底，
        不然看一半被拽回底部会想打猫喵；滚回底部附近自动恢复。
        """
        bar = self.scroll_area.verticalScrollBar()
        distance = bar.maximum() - value
        self._stick_to_bottom = distance <= max(40, bar.pageStep() // 2)

    def _force_stick_to_bottom(self):
        """强制回到吸底状态并立刻滚到底（用户刚发出新消息时用）。"""
        self._stick_to_bottom = True
        self._scroll_to_bottom()
        # 双保险：等这一帧布局算完再滚一次
        QTimer.singleShot(0, self._scroll_to_bottom)

    def add_user_message(self, text):
        """添加一条用户消息（粉色气泡，靠右显示）。"""
        self._remove_welcome()

        # 气泡框
        bubble_frame = QFrame()
        bubble_frame.setObjectName("userBubble")
        bubble_layout = QVBoxLayout(bubble_frame)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        label = QLabel(text)
        label.setWordWrap(True)
        # 允许选中复制
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        bubble_layout.addWidget(label)

        # 整行：[弹簧][气泡][🐶头像] —— 靠右
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addStretch(1)
        row_layout.addWidget(bubble_frame)
        row_layout.addWidget(self._make_avatar("user"))

        self._bubble_frames.append((bubble_frame, label, False))
        self._insert_row(row)
        # 让新气泡遵守当前窗口下的宽度限制
        self._apply_bubble_max_width()
        # 用户刚发了消息 → 强制回到吸底状态（后面输出自动跟随）
        self._force_stick_to_bottom()

    def begin_assistant_message(self, hint=None):
        """开始一条雪花喵的回答：先创建一个空气泡，显示"思考中"。

        参数 hint：可选的提示文字。不传就用默认的"雪花喵思考中喵"；
        技能生成时传"正在整理学习文档喵"之类，用户一眼知道在干嘛。

        之后模型每传来一小段文字，就由 append_chunk() 往这个气泡里追加。
        """
        self._remove_welcome()
        # 先清掉上一次可能残留的状态（正常情况下不会发生，保险起见）
        self._accumulated = ""

        bubble_frame = QFrame()
        bubble_frame.setObjectName("assistantBubble")
        frame_layout = QVBoxLayout(bubble_frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)

        self._active_bubble = XhanggeMarkdownBubble()
        # 先显示思考中提示；收到第一段文字后会被替换掉
        self._active_bubble.set_markdown_text(hint or THINKING_HINT)
        frame_layout.addWidget(self._active_bubble)

        # 整行：[🐱头像][气泡][弹簧] —— 靠左
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self._make_avatar("assistant"))
        row_layout.addWidget(bubble_frame)
        row_layout.addStretch(1)

        self._active_frame = bubble_frame
        self._bubble_frames.append((bubble_frame, self._active_bubble, True))
        self._insert_row(row)
        self._apply_bubble_max_width()
        # 新回答开始 → 吸底，输出时自动跟随往下滚
        self._force_stick_to_bottom()

    def append_chunk(self, piece):
        """流式追加：模型传来一小段文字，立刻显示到气泡里（打字机效果的核心）。"""
        if self._active_bubble is None:
            return
        self._accumulated += piece
        # 用累积的全文重新渲染（Markdown 需要整体解析，不能只追加一段）。
        # 滚动跟随交给 rangeChanged：气泡长高会触发它，吸底就跟上喵
        self._active_bubble.set_markdown_text(self._accumulated)
        # 内容变长，气泡宽度要跟着走（只重算当前这一条，避免全量重算卡顿）
        if self._active_frame is not None:
            self._active_frame.setFixedWidth(
                self._bubble_width(self._active_bubble, True)
            )

    def finish_assistant_message(self, exportable=False):
        """一条回答完成：做收尾清理。

        参数 exportable：这条回答是不是"学习技能的产出"。
        是的话，在气泡下面挂一个「💾 导出喵」小按钮，
        点了就把它存成 .md 文件（真正的保存动作由主窗口做）。

        如果模型一个字都没回（比如刚连上就被停止），给个友好提示。
        """
        # 先记住"有没有真实内容"——被秒停时下面会用占位文字顶替，
        # 占位文字不该被导出成文件
        had_content = bool(self._accumulated.strip())
        if self._active_bubble is not None and not had_content:
            self._active_bubble.set_markdown_text(
                "（雪花喵还没来得及说话就被停下了喵...😿）"
            )
        # 技能产出且有真实内容 → 挂导出按钮（放在气泡框内部、正文下面，靠左）
        if (
            exportable
            and had_content
            and self._active_bubble is not None
            and self._active_frame is not None
        ):
            raw_text = getattr(self._active_bubble, "xhangge_raw_text", "")
            export_btn = QPushButton("💾 导出喵")
            export_btn.setObjectName("CapsuleBtn")
            export_btn.setCursor(xhangge_hand_cursor())
            export_btn.setToolTip("把这份资料存成 .md 文件喵")
            # 按钮点击 → 把"这份资料的原文"发出去，主窗口接住去选目录、写文件
            export_btn.clicked.connect(
                lambda _=False, t=raw_text: self.export_requested.emit(t)
            )
            # 包一行小布局，让按钮靠左、不占满整行
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 4, 0, 0)
            btn_row.addWidget(export_btn)
            btn_row.addStretch(1)
            self._active_frame.layout().addLayout(btn_row)
        self._active_bubble = None
        self._active_frame = None
        self._accumulated = ""

    def set_error(self, message):
        """把当前气泡变成红色错误气泡，显示友好的错误信息。"""
        if self._active_bubble is None:
            # 理论上不会发生（发消息前一定会先 begin），保险处理
            self.begin_assistant_message()
        # 换个"错误"身份（QSS 会自动变成红色描边样式）
        if self._active_frame is not None:
            self._active_frame.setObjectName("errorBubble")
            self._active_frame.style().unpolish(self._active_frame)
            self._active_frame.style().polish(self._active_frame)
        self._active_bubble.set_markdown_text(message)
        # 收尾（错误不算一条正常回答，不保存进数据库）
        self._active_bubble = None
        self._active_frame = None
        self._accumulated = ""

    # ============================================================
    # 历史记录加载 / 清空
    # ============================================================
    def load_history(self, messages):
        """把一个会话的历史记录整个显示出来（切换会话时用）。

        参数 messages：[{"role": "user"/"assistant", "content": "...",
                        "xhangge_is_skill": 0/1}, ...]
        带技能标记的消息，显示时也会挂上「💾 导出喵」按钮。
        """
        self.clear_chat()
        # 打开/切换会话：默认定位到最底部（用户要看的是最新对话）
        self._stick_to_bottom = True
        for msg in messages:
            if msg["role"] == "user":
                self.add_user_message(msg["content"])
            else:
                # 历史里的雪花喵回答：直接完整显示（不需要流式）
                self.begin_assistant_message()
                self.append_chunk(msg["content"])
                self.finish_assistant_message(
                    exportable=bool(msg.get("xhangge_is_skill"))
                )

    def clear_chat(self):
        """清空聊天区所有消息，恢复欢迎语。"""
        # 把布局里除弹簧外的所有控件都拆掉
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._bubble_frames = []
        self._active_bubble = None
        self._active_frame = None
        self._accumulated = ""
        self._steps_label = None
        self._steps_lines = []
        self._welcome_label = None  # 原欢迎语已随布局被删除，重新显示
        self._show_welcome()

    # ============================================================
    # 窗口尺寸变化时的处理
    # ============================================================
    def _bubble_width(self, bubble, is_markdown):
        """算单个气泡该多宽：按内容量理想宽度，再 clamp 到 [10%, 90%]。

        QTextBrowser（雪花喵气泡）的 sizeHint 是固定默认值、跟内容无关，
        所以这里按真实内容量一下理想宽度，让气泡"内容短就窄、内容长就宽"。
        """
        vp_w = self.scroll_area.viewport().width()
        if vp_w <= 0:
            vp_w = self.scroll_area.width() or 600
        max_w = int(vp_w * 0.9)
        min_w = int(vp_w * 0.1)
        if is_markdown:
            # 注意不能用 document().idealWidth()：文档已经被当前宽度包了行，
            # idealWidth 会退化成"最窄一行"的宽度（中文可任意断行，几乎为 0），
            # 气泡就会永远卡在最小宽度。改用渲染后的纯文本量宽度。
            text = bubble.toPlainText()
        else:
            text = bubble.text()
        fm = bubble.fontMetrics()
        lines = text.split("\n") if text else [""]
        ideal = max((fm.horizontalAdvance(line) for line in lines), default=0)
        ideal += 30  # 气泡左右内边距（12*2）加一点余量
        return max(min_w, min(ideal, max_w))

    def _apply_bubble_max_width(self):
        """让所有气泡宽度跟着内容走（新消息插入、窗口 resize 时调用）。"""
        for frame, bubble, is_markdown in self._bubble_frames:
            frame.setFixedWidth(self._bubble_width(bubble, is_markdown))

    def resizeEvent(self, event):
        """窗口大小变化时，重新计算所有气泡的最大宽度。"""
        super().resizeEvent(event)
        self._apply_bubble_max_width()
