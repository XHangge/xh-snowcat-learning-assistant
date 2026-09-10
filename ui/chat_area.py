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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# 雪花喵回答前显示的"思考中"提示文字（Markdown 斜体语法）
THINKING_HINT = "*雪花喵思考中喵... 🐾*"


class XhanggeInputEdit(QTextEdit):
    """底部输入框：支持"回车发送、Shift+回车换行"。

    QTextEdit 默认回车是换行，这里重写按键事件改变行为，
    更符合大家使用聊天软件的习惯喵。
    """

    # 按下回车时发出的信号（输入框自己不发送消息，交给外层处理）
    enter_pressed = Signal()

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
    send_requested = Signal(str)  # 用户要发送一条消息（参数：消息文本）
    stop_requested = Signal()     # 用户要点"停止生成"

    def __init__(self, parent=None):
        super().__init__(parent)
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

        # ---- 下：输入栏（输入框 + 发送按钮） ----
        input_bar = QWidget()
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

        self.send_btn = QPushButton("发送喵 🚀")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 点击按钮：空闲时是发送，生成中是停止
        self.send_btn.clicked.connect(self._on_send_clicked)

        input_layout.addWidget(self.input_edit, 1)  # 输入框占满剩余宽度
        input_layout.addWidget(self.send_btn)
        root.addWidget(input_bar)

        # 显示欢迎语（第一次打开时聊天区中间的可爱提示）
        self._welcome_label = None
        self._show_welcome()

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
        self.send_btn.setText("停止喵 ✋" if streaming else "发送喵 🚀")
        self.send_btn.setProperty("streaming", "true" if streaming else "false")
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
            "（在左侧边栏可以切换学习模式喵 🌸）"
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

    def _make_avatar(self, emoji):
        """造一个头像标签（🐱 是雪花喵，🐶 是用户）。"""
        avatar = QLabel(emoji)
        avatar.setObjectName("AvatarLabel")
        avatar.setFixedSize(38, 38)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return avatar

    def _insert_row(self, row):
        """把一行消息（头像+气泡）插到消息列表末尾（弹簧前面），并滚动到底部。"""
        self.message_layout.insertWidget(self.message_layout.count() - 1, row)
        # singleShot(0, ...) = 等界面布局算完这一帧再滚动，保证滚到真正的底部
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """把聊天区滚动到最底部（看到最新的消息）"""
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

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
        row_layout.addWidget(self._make_avatar("🐶"))

        self._bubble_frames.append(bubble_frame)
        self._insert_row(row)
        # 让新气泡遵守当前窗口下的最大宽度限制
        self._apply_bubble_max_width()

    def begin_assistant_message(self):
        """开始一条雪花喵的回答：先创建一个空气泡，显示"思考中"。

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
        self._active_bubble.set_markdown_text(THINKING_HINT)
        frame_layout.addWidget(self._active_bubble)

        # 整行：[🐱头像][气泡][弹簧] —— 靠左
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_layout.addWidget(self._make_avatar("🐱"))
        row_layout.addWidget(bubble_frame)
        row_layout.addStretch(1)

        self._active_frame = bubble_frame
        self._bubble_frames.append(bubble_frame)
        self._insert_row(row)
        self._apply_bubble_max_width()

    def append_chunk(self, piece):
        """流式追加：模型传来一小段文字，立刻显示到气泡里（打字机效果的核心）。"""
        if self._active_bubble is None:
            return
        self._accumulated += piece
        # 用累积的全文重新渲染（Markdown 需要整体解析，不能只追加一段）
        self._active_bubble.set_markdown_text(self._accumulated)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def finish_assistant_message(self):
        """一条回答完成：做收尾清理。

        如果模型一个字都没回（比如刚连上就被停止），给个友好提示。
        """
        if self._active_bubble is not None and not self._accumulated.strip():
            self._active_bubble.set_markdown_text(
                "（雪花喵还没来得及说话就被停下了喵...😿）"
            )
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

        参数 messages：[{"role": "user"/"assistant", "content": "..."}, ...]
        """
        self.clear_chat()
        for msg in messages:
            if msg["role"] == "user":
                self.add_user_message(msg["content"])
            else:
                # 历史里的雪花喵回答：直接完整显示（不需要流式）
                self.begin_assistant_message()
                self.append_chunk(msg["content"])
                self.finish_assistant_message()

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
        self._welcome_label = None  # 原欢迎语已随布局被删除，重新显示
        self._show_welcome()

    # ============================================================
    # 窗口尺寸变化时的处理
    # ============================================================
    def _apply_bubble_max_width(self):
        """限制气泡最大宽度（约聊天区宽度的 72%）。

        不限制的话，一条短消息也会撑满整行，太难看了喵。
        """
        max_width = max(240, int(self.scroll_area.viewport().width() * 0.72))
        for frame in self._bubble_frames:
            frame.setMaximumWidth(max_width)

    def resizeEvent(self, event):
        """窗口大小变化时，重新计算所有气泡的最大宽度。"""
        super().resizeEvent(event)
        self._apply_bubble_max_width()
