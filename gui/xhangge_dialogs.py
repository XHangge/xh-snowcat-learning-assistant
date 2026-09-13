# Author: xhangge
# This project is created by xhangge
"""
dialogs —— 可爱风弹窗集合
包含软件里用到的所有弹窗：
1. 启动弹窗（每次打开软件显示"点个 star 喵"）
2. 警告弹窗（比如 Ollama 没启动时提醒用户）
3. 重命名弹窗（右键会话重命名）
4. 确认弹窗（删除会话前问一下，防止误删）

所有弹窗都基于 CuteDialog：无边框 + 圆角 + 粉色描边，
样式统一在 themes.py 的 QSS 里（#cuteDialogFrame 等名字）。
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.xhangge_avatars import (
    xhangge_apply_paw_cursor,
    xhangge_catgirl_label,
    xhangge_hand_cursor,
    xhangge_ibeam_cursor,
)
from gui.xhangge_cute_progress import XhanggeCuteProgress


class CuteDialog(QDialog):
    """可爱弹窗的基础模板。

    这段在干什么：
    1. 去掉系统自带的灰色窗口边框（FramelessWindowHint）
    2. 开启背景透明（WA_TranslucentBackground），
       这样 QSS 里的圆角 border-radius 才能真正显示出来
       （不透明的话，圆角外面会有直角背景）
    3. 里面套一个 QFrame 作为"卡片"，圆角和描边样式都画在它身上
    """

    def __init__(self, parent=None, width=420):
        super().__init__(parent)
        # Dialog：这是一个对话框窗口；FramelessWindowHint：去掉系统边框
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        # 背景透明，让圆角生效
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 模态：弹窗没关掉之前，不能操作主窗口
        self.setModal(True)
        self.setFixedSize(width, 300)  # 默认尺寸，子类可自行调整
        # 弹窗上也显示粉色猫爪指针（按钮自己带的小手光标优先级更高）
        xhangge_apply_paw_cursor(self)

        # ---- 卡片本体（圆角粉色描边的那个框）----
        self.frame = QFrame(self)
        self.frame.setObjectName("cuteDialogFrame")
        # 卡片内部的垂直布局（标题/内容/按钮从上到下排）
        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(24, 20, 24, 20)
        self.frame_layout.setSpacing(12)

        # 最外层布局：让卡片充满整个弹窗
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.frame)

    def center_on_parent(self):
        """把弹窗移动到父窗口的正中央，看起来更舒服"""
        if self.parent() is None:
            return
        parent_geometry = self.parent().geometry()
        # 父窗口中心点坐标 减去 弹窗宽高的一半 = 弹窗左上角坐标
        x = parent_geometry.center().x() - self.width() // 2
        y = parent_geometry.center().y() - self.height() // 2
        self.move(x, y)


def _make_button(text, primary=True):
    """小工具函数：造一个统一样式的按钮。
    primary=True 是粉色实心主按钮，False 是白底描边次按钮。"""
    btn = QPushButton(text)
    btn.setObjectName("PrimaryBtn" if primary else "SecondaryBtn")
    btn.setCursor(xhangge_hand_cursor())
    return btn


def show_star_dialog(parent):
    """启动弹窗：每次打开软件都显示一次，请大家给 xhangge 点 star 喵。

    对应需求：启动弹窗内容"支持xhangge请帮忙点个star喵 🌟"
    """
    dlg = CuteDialog(parent, width=400)
    dlg.setWindowTitle("喵～")

    # 大号猫娘头像（图标位一律用真图，加载失败才退回 🐱 emoji）
    emoji_label = xhangge_catgirl_label(64)
    emoji_label.setObjectName("DialogEmoji")
    emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_label = QLabel("支持 xhangge 请帮忙点个 star 喵 🌟")
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setWordWrap(True)

    text_label = QLabel(
        "这个软件是 xhangge 开源制作的小作品喵～\n"
        "如果你觉得雪花喵可爱又好用，\n"
        "去 GitHub 给项目点一颗小星星，就是对作者最大的鼓励喵 💖"
    )
    text_label.setObjectName("DialogText")
    text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text_label.setWordWrap(True)

    ok_btn = _make_button("好哒喵～ 💖")
    # 点按钮 = 关闭弹窗（accept 就是"确认并关闭"）
    ok_btn.clicked.connect(dlg.accept)

    # 垂直排列：emoji → 标题 → 说明 → 按钮
    dlg.frame_layout.addWidget(emoji_label)
    dlg.frame_layout.addWidget(title_label)
    dlg.frame_layout.addWidget(text_label)
    dlg.frame_layout.addStretch(1)
    # 按钮行（水平布局，让按钮居中）
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(ok_btn)
    btn_row.addStretch(1)
    dlg.frame_layout.addLayout(btn_row)

    dlg.center_on_parent()
    # exec()：弹出并等待用户点击（模态，会阻塞在这里直到弹窗关闭）
    dlg.exec()


def show_warning_dialog(parent, title, text):
    """警告弹窗：出问题时用（比如 Ollama 没启动）。"""
    emoji_label = QLabel("😿")
    emoji_label.setObjectName("DialogEmoji")
    emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_label = QLabel(title)
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setWordWrap(True)

    text_label = QLabel(text)
    text_label.setObjectName("DialogText")
    text_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    text_label.setWordWrap(True)

    ok_btn = _make_button("知道啦喵")
    ok_btn.clicked.connect(dlg.accept)

    dlg.frame_layout.addWidget(emoji_label)
    dlg.frame_layout.addWidget(title_label)
    dlg.frame_layout.addWidget(text_label)
    dlg.frame_layout.addStretch(1)
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(ok_btn)
    btn_row.addStretch(1)
    dlg.frame_layout.addLayout(btn_row)

    dlg.center_on_parent()
    dlg.exec()


def show_ok_dialog(parent, title, text):
    """成功提示弹窗：操作顺利完成后用（比如「删除成功喵」）。

    和警告弹窗长得一样，只是图标换成 ✅、语气是开心的喵。
    """
    dlg = CuteDialog(parent, width=400)
    dlg.setWindowTitle("好耶")

    emoji_label = QLabel("✅")
    emoji_label.setObjectName("DialogEmoji")
    emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_label = QLabel(title)
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    text_label = QLabel(text)
    text_label.setObjectName("DialogText")
    text_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    text_label.setWordWrap(True)

    ok_btn = _make_button("好哒喵～")
    ok_btn.clicked.connect(dlg.accept)

    dlg.frame_layout.addWidget(emoji_label)
    dlg.frame_layout.addWidget(title_label)
    dlg.frame_layout.addWidget(text_label)
    dlg.frame_layout.addStretch(1)
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(ok_btn)
    btn_row.addStretch(1)
    dlg.frame_layout.addLayout(btn_row)

    dlg.center_on_parent()
    dlg.exec()


def show_rename_dialog(parent, current_title, dialog_title="重命名喵", prompt="✏️ 给这个会话改个名字喵"):
    """通用"输入一个名字"弹窗（重命名会话 / 新建知识库 / 库改名 都用它）。

    参数：
        current_title —— 预填在输入框里的文字（新建场景传空字符串）
        dialog_title  —— 弹窗标题
        prompt        —— 输入框上面的提示语
    返回：
        用户点"确定"：返回新标题（字符串）
        用户点"取消"或关掉弹窗：返回 None
    """
    dlg = CuteDialog(parent, width=380)
    dlg.setWindowTitle(dialog_title)
    dlg.setFixedSize(380, 230)

    title_label = QLabel(prompt)
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # 输入框：预填当前标题，全选方便直接覆盖输入
    edit = QLineEdit(current_title)
    edit.selectAll()
    edit.setCursor(xhangge_ibeam_cursor())

    result = {"title": None}  # 用字典把结果带出内部函数（闭包技巧）

    def on_ok():
        # 记录用户输入的新标题并关闭弹窗
        result["title"] = edit.text().strip()
        dlg.accept()

    ok_btn = _make_button("确定喵")
    cancel_btn = _make_button("取消喵", primary=False)
    ok_btn.clicked.connect(on_ok)
    cancel_btn.clicked.connect(dlg.reject)

    dlg.frame_layout.addWidget(title_label)
    dlg.frame_layout.addWidget(edit)
    dlg.frame_layout.addStretch(1)
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(ok_btn)
    btn_row.addWidget(cancel_btn)
    btn_row.addStretch(1)
    dlg.frame_layout.addLayout(btn_row)

    # 按 Enter 键相当于点"确定"，操作更顺手
    edit.returnPressed.connect(on_ok)

    dlg.center_on_parent()
    dlg.exec()
    return result["title"]


def show_confirm_dialog(parent, title, text):
    """确认弹窗：做危险操作前问一下（比如删除会话）。

    返回：
        True  —— 用户点了"确定"
        False —— 用户点了"取消"或关掉弹窗
    """
    dlg = CuteDialog(parent, width=380)

    emoji_label = QLabel("⚠️")
    emoji_label.setObjectName("DialogEmoji")
    emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_label = QLabel(title)
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setWordWrap(True)

    text_label = QLabel(text)
    text_label.setObjectName("DialogText")
    text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text_label.setWordWrap(True)

    ok_btn = _make_button("确定喵")
    cancel_btn = _make_button("取消喵", primary=False)
    ok_btn.clicked.connect(dlg.accept)
    cancel_btn.clicked.connect(dlg.reject)

    dlg.frame_layout.addWidget(emoji_label)
    dlg.frame_layout.addWidget(title_label)
    dlg.frame_layout.addWidget(text_label)
    dlg.frame_layout.addStretch(1)
    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(ok_btn)
    btn_row.addWidget(cancel_btn)
    btn_row.addStretch(1)
    dlg.frame_layout.addLayout(btn_row)

    dlg.center_on_parent()
    # exec() 的返回值：accept → True，reject → False
    return dlg.exec() == QDialog.DialogCode.Accepted


# ============================================================
# 导出进度弹窗（「💾 导出喵」功能用）
# ============================================================
# 一个小实况说明：写一个几 KB 的 .md 文件是瞬间完成的，
# 并不存在"真实的进度百分比"。
# 但用户明确要求"进度条和其它进度条保持一致"——
# 所以这里用一个定时器把进度从 0 匀速推到 100（约 1 秒），
# 让猫娘跑完这一程再报"导出成功喵～"。
# 这是给用户的"可爱反馈"，不是在假装干活喵。

class XhanggeExportProgressDialog(CuteDialog):
    """导出进度弹窗：可爱进度条从 0 跑到 100，然后显示导出结果。"""

    def __init__(self, parent, theme_key="pink"):
        # 宽 420 高 240：进度条 + 结果文字 + 按钮刚好放下
        super().__init__(parent, width=420)
        self.setFixedSize(420, 240)

        # ---- 进度条（和设置窗下载模型用的同一个组件）----
        self.progress = XhanggeCuteProgress()
        self.progress.xhangge_apply_theme(theme_key)
        self.progress.xhangge_set_progress(0, "正在导出喵…")

        # ---- 结果文字（导出成功后显示存到了哪里）----
        self.result_label = QLabel("")
        self.result_label.setObjectName("DialogText")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setVisible(False)

        # ---- 确认按钮（导出完成后才出现）----
        self.ok_btn = _make_button("好哒喵～")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setVisible(False)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.ok_btn)
        btn_row.addStretch(1)

        self.frame_layout.addWidget(self.progress)
        self.frame_layout.addWidget(self.result_label)
        self.frame_layout.addStretch(1)
        self.frame_layout.addLayout(btn_row)

        # ---- 进度动画：每 40 毫秒走 4%，25 步走完 100% ----
        self._percent = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._xhangge_tick)

    def xhangge_start(self, on_done):
        """开始播放进度动画；动画走完时回调 on_done()。

        文件已经在弹这个窗之前写好了（写文件瞬间完成，
        先写后动画最稳：动画再好看，文件没落盘都白搭），
        on_done 里做的事情是"把结果展示出来"。
        """
        self._on_done = on_done
        self._timer.start()

    def _xhangge_tick(self):
        """进度 +4%，到 100% 时停表并回调。"""
        self._percent = min(100, self._percent + 4)
        self.progress.xhangge_set_progress(self._percent, "正在导出喵…")
        if self._percent >= 100:
            self._timer.stop()
            self._on_done()

    def xhangge_show_result(self, ok, message):
        """动画结束后调用：进度条收工，亮出结果。"""
        self.progress.xhangge_set_progress(
            100, "导出成功喵～ ✨" if ok else "导出失败喵 😿"
        )
        self.result_label.setText(message)
        self.result_label.setVisible(True)
        self.ok_btn.setVisible(True)


# ============================================================
# Agent 人工确认弹窗（HITL）
# ============================================================
def show_hitl_dialog(parent, tool_label, target, preview=""):
    """Agent 要做高危操作前，弹窗问用户同不同意。

    参数：
        tool_label —— 操作的中文名，如「✏️ 写入/修改文件」
        target     —— 操作目标（文件路径或命令内容）
        preview    —— 预览内容（写入的文件内容等，可为空）
    返回：
        True  —— 用户点了「同意喵」（Agent 会继续执行）
        False —— 用户点了「拒绝喵」或直接关掉窗口（Agent 会放弃这个操作）
    """
    dlg = CuteDialog(parent, width=480)
    dlg.setWindowTitle("雪花喵想动手喵")
    dlg.setFixedSize(480, 340)

    emoji_label = QLabel("🤔")
    emoji_label.setObjectName("DialogEmoji")
    emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    title_label = QLabel("雪花喵想做这件事，需要你同意喵：")
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # 操作类型 + 目标
    action_label = QLabel(tool_label)
    action_label.setObjectName("DialogTitle")
    target_label = QLabel(target or "（没有目标）")
    target_label.setObjectName("DialogText")
    target_label.setWordWrap(True)
    # 允许选中复制（路径/命令比较长，用户可能想复制出来看看）
    target_label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )

    dlg.frame_layout.addWidget(emoji_label)
    dlg.frame_layout.addWidget(title_label)
    dlg.frame_layout.addWidget(action_label)
    dlg.frame_layout.addWidget(target_label)

    # 预览内容（写入文件时会显示要写的东西，放可滚动区域里）
    if preview:
        from PySide6.QtWidgets import QScrollArea

        preview_area = QScrollArea()
        preview_area.setWidgetResizable(True)
        preview_area.setFixedHeight(110)
        preview_area.setFrameShape(QFrame.Shape.StyledPanel)
        preview_text = QLabel(preview)
        preview_text.setWordWrap(True)
        preview_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        preview_area.setWidget(preview_text)
        dlg.frame_layout.addWidget(preview_area)

    hint = QLabel("拒绝不会出错喵，雪花喵会换个办法继续～")
    hint.setObjectName("DialogText")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dlg.frame_layout.addWidget(hint)

    ok_btn = _make_button("同意喵 ✔️")
    cancel_btn = _make_button("拒绝喵 ✋", primary=False)
    ok_btn.clicked.connect(dlg.accept)
    cancel_btn.clicked.connect(dlg.reject)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    btn_row.addWidget(ok_btn)
    btn_row.addWidget(cancel_btn)
    btn_row.addStretch(1)
    dlg.frame_layout.addLayout(btn_row)

    dlg.center_on_parent()
    # accept → True（同意）；reject 或直接关窗 → False（拒绝）
    return dlg.exec() == QDialog.DialogCode.Accepted
