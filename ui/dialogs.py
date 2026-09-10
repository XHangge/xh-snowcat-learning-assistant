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

from PySide6.QtCore import Qt
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
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def show_star_dialog(parent):
    """启动弹窗：每次打开软件都显示一次，请大家给 xhangge 点 star 喵。

    对应需求：启动弹窗内容"支持xhangge请帮忙点个star喵 🌟"
    """
    dlg = CuteDialog(parent, width=400)
    dlg.setWindowTitle("喵～")

    # 大号猫咪 emoji，弹窗更有可爱气氛
    emoji_label = QLabel("🐱✨🌸")
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
    dlg = CuteDialog(parent, width=420)
    dlg.setWindowTitle("喵呜")

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


def show_rename_dialog(parent, current_title):
    """重命名弹窗：修改会话标题。

    参数：
        current_title —— 当前标题（显示在输入框里，方便在原名基础上改）
    返回：
        用户点"确定"：返回新标题（字符串）
        用户点"取消"或关掉弹窗：返回 None
    """
    dlg = CuteDialog(parent, width=380)
    dlg.setWindowTitle("重命名喵")
    dlg.setFixedSize(380, 230)

    title_label = QLabel("✏️ 给这个会话改个名字喵")
    title_label.setObjectName("DialogTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # 输入框：预填当前标题，全选方便直接覆盖输入
    edit = QLineEdit(current_title)
    edit.selectAll()

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
