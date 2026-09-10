# Author: xhangge
# This project is created by xhangge
"""
sidebar —— 左侧边栏
负责四块内容（从上到下）：
1. 🐾 新建会话按钮
2. 会话列表（右键可以重命名 / 删除）
3. 我的信息（设置用户名，不设置就叫"杂狗"）
4. 主题切换 + 学习模式切换

设计原则：侧边栏只管"显示和收集操作"，不直接碰数据库——
用户做了什么操作，通过 Qt 信号（Signal）告诉主窗口，
由主窗口去调用数据库干活，职责分明。
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.prompts import MODE_LABELS
from ui.themes import THEME_LABELS


class XhanggeSidebar(QFrame):
    """左侧边栏控件（主窗口把它放在左边，可以整体显示/隐藏）"""

    # ---- 对外信号：侧边栏里发生的事情，通过这些"喊话"告诉主窗口 ----
    new_session_requested = Signal()        # 用户点了"新建会话"
    session_selected = Signal(int)          # 用户点选了某个会话（参数：会话 id）
    session_rename_requested = Signal(int)  # 用户右键选择了"重命名"（参数：会话 id）
    session_delete_requested = Signal(int)  # 用户右键选择了"删除"（参数：会话 id）
    username_changed = Signal(str)          # 用户改了昵称（参数：新昵称）
    theme_changed = Signal(str)             # 用户换了主题（参数：主题标识）
    mode_changed = Signal(str)              # 用户换了学习模式（参数：模式标识）

    def __init__(self, settings, parent=None):
        """初始化侧边栏。

        参数：
            settings —— 保存的用户设置（用户名/主题/模式），
                        用来把界面恢复成用户上次关闭前的样子
        """
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(252)  # 侧边栏固定宽度，不跟着窗口拉伸

        # 记住上一次的用户名，用来判断"这次是不是真的改了"
        self._last_username = settings.get("username", "")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 14, 12, 12)
        main_layout.setSpacing(10)

        # ---- 顶部 logo 和"新建会话"按钮 ----
        logo = QLabel("🐱 雪花喵助手")
        logo.setObjectName("SidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(logo)

        self.new_session_btn = QPushButton("🐾 新建会话")
        self.new_session_btn.setObjectName("NewSessionBtn")
        self.new_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # 点按钮 → 发出"新建会话"信号
        self.new_session_btn.clicked.connect(self.new_session_requested.emit)
        main_layout.addWidget(self.new_session_btn)

        # ---- 会话列表 ----
        self.session_list = QListWidget()
        self.session_list.setObjectName("SessionList")
        # 开启"自定义右键菜单"模式：右键时 Qt 会发信号让我们自己画菜单
        self.session_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.session_list.customContextMenuRequested.connect(
            self._show_session_menu
        )
        # 用户单击某个会话 → 发出"选中了哪个会话"信号
        self.session_list.itemClicked.connect(self._on_session_clicked)
        main_layout.addWidget(self.session_list, 1)  # 参数 1 = 占据剩余所有空间

        # ---- 我的信息（用户名设置） ----
        info_group = QGroupBox("👤 我的信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(10, 6, 10, 8)
        info_layout.setSpacing(6)

        name_hint = QLabel("雪花喵该怎么称呼你喵？")
        name_hint.setObjectName("DialogText")
        self.username_edit = QLineEdit(self._last_username)
        # 输入框里灰色提示文字：不填就用默认名"杂狗"
        self.username_edit.setPlaceholderText("不设置就叫杂狗喵")
        self.username_edit.setClearButtonEnabled(True)  # 输入框右侧的小 × 清空按钮
        # editingFinished：按回车或点击别处（输入完成）时触发
        self.username_edit.editingFinished.connect(self._on_username_done)
        info_layout.addWidget(name_hint)
        info_layout.addWidget(self.username_edit)
        main_layout.addWidget(info_group)

        # ---- 主题 + 学习模式（放在同一行，节省竖向空间） ----
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        # 主题切换下拉框
        theme_group = QGroupBox("🎨 主题")
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setContentsMargins(8, 6, 8, 8)
        self.theme_combo = QComboBox()
        # 把每个主题加进下拉框；addItem 第二个参数存"主题标识"（如 "pink"）
        for theme_key, theme_label in THEME_LABELS:
            self.theme_combo.addItem(theme_label, theme_key)
        # 恢复用户上次选的主题（按存的数据找索引，找不到就用第 0 个）
        saved_theme = settings.get("theme", "pink")
        idx = self.theme_combo.findData(saved_theme)
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        # 用户换主题 → 发信号
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        bottom_row.addWidget(theme_group, 1)  # 参数 1 = 平分一行宽度

        # 学习模式下拉框（三种模式来自 core/prompts.py 的定义）
        mode_group = QGroupBox("📚 学习模式")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(8, 6, 8, 8)
        self.mode_combo = QComboBox()
        for mode_key, mode_label in MODE_LABELS:
            self.mode_combo.addItem(mode_label, mode_key)
        saved_mode = settings.get("mode", "simple")
        idx = self.mode_combo.findData(saved_mode)
        self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        bottom_row.addWidget(mode_group, 1)

        main_layout.addLayout(bottom_row)

    # --------------------------------------------------------
    # 会话列表相关
    # --------------------------------------------------------
    def refresh_sessions(self, sessions, current_id=None):
        """用数据库里的会话列表刷新界面显示。

        参数：
            sessions   —— 数据库查出来的会话列表（最新在前）
            current_id —— 当前选中的会话 id，刷新后保持选中状态
        """
        # 重建列表前先清空旧内容
        self.session_list.clear()
        for session in sessions:
            item = QListWidgetItem(session["title"])
            # 把会话 id 藏在条目数据里（UserRole 是"自定义数据"的位置）
            # 点到这个条目时就能取出对应的 id 去查数据库
            item.setData(Qt.ItemDataRole.UserRole, session["id"])
            self.session_list.addItem(item)
            # 这就是当前会话 → 让它保持选中高亮
            if session["id"] == current_id:
                self.session_list.setCurrentItem(item)

    def _on_session_clicked(self, item):
        """用户单击了某个会话条目 → 从条目里取出会话 id，发信号给主窗口"""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id is not None:
            self.session_selected.emit(session_id)

    def _show_session_menu(self, pos):
        """右键菜单：重命名 / 删除。

        这段在干什么：
        1. 根据鼠标右键的位置，找出用户右键的是哪个会话条目
        2. 弹出菜单（重命名 / 删除），等用户选择
        3. 把对应操作通过信号告诉主窗口（数据库操作由主窗口做）
        """
        # itemAt：把菜单弹出的坐标换算成列表里的条目
        item = self.session_list.itemAt(pos)
        if item is None:
            return  # 右键点在空白处，不弹菜单
        session_id = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        rename_action = menu.addAction("✏️ 重命名")
        delete_action = menu.addAction("🗑️ 删除会话")
        # exec() 弹出菜单并等待用户选择，返回被点的那个菜单项
        chosen = menu.exec(self.session_list.mapToGlobal(pos))

        if chosen == rename_action:
            self.session_rename_requested.emit(session_id)
        elif chosen == delete_action:
            self.session_delete_requested.emit(session_id)

    # --------------------------------------------------------
    # 设置项相关
    # --------------------------------------------------------
    def _on_username_done(self):
        """用户名输入完成（回车或点击别处）→ 通知主窗口。

        这段在干什么：
        只在名字真的发生变化时才发信号，
        避免用户只是点了一下输入框就触发无意义的保存。
        """
        text = self.username_edit.text().strip()
        if text != self._last_username:
            self._last_username = text
            self.username_changed.emit(text)

    def _on_theme_changed(self, index):
        """主题下拉框换了选项 → 取出主题标识，发信号"""
        theme_key = self.theme_combo.itemData(index)
        if theme_key:
            self.theme_changed.emit(theme_key)

    def _on_mode_changed(self, index):
        """模式下拉框换了选项 → 取出模式标识，发信号"""
        mode_key = self.mode_combo.itemData(index)
        if mode_key:
            self.mode_changed.emit(mode_key)

    # --------------------------------------------------------
    # 状态控制
    # --------------------------------------------------------
    def set_controls_enabled(self, enabled):
        """在模型生成回答期间，禁用会话相关操作，防止切换会话把状态搞乱。

        （用户名、主题、模式仍然可以改，它们只影响"下一条"消息）
        """
        self.new_session_btn.setEnabled(enabled)
        self.session_list.setEnabled(enabled)
