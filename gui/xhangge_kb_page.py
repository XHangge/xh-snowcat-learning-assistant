# Author: xhangge
# This project is created by xhangge
"""
xhangge_kb_page —— 📚 知识库管理窗口（模块五的界面）

点主窗口标题栏的 📚 按钮打开。布局：

    ┌───────────────────────────────────────────────┐
    │ 📚 知识库喵                                ✕ │
    ├──────────┬────────────────────────────────────┤
    │ ＋新建库  │ ┌ 当前会话喵 ────────────────────┐ │
    │          │ │ ☑ 回答时翻知识库   [库A ✕]     │ │
    │ 库 A     │ └────────────────────────────────┘ │
    │ 库 B     │ ┌ 选中库的详情 ──────────────────┐ │
    │ (最多10) │ │ 容量条    📁导入  绑定/解绑     │ │
    │          │ │ ┌ 拖文件到这里… ────────────┐  │ │
    │          │ │ └───────────────────────────┘  │ │
    │          │ │ 文件1  1.2MB  24块  [删除]     │ │
    │          │ │ 文件2 …                        │ │
    │          │ └────────────────────────────────┘ │
    └──────────┴────────────────────────────────────┘

分层规矩（和整个项目一致）：
这个文件只管"显示"和"转发"——
- 真正的导入/检索/删除都在 services/xhangge_kb_service.py
- 档案读写都在 models/xhangge_db.py
- 这里只把用户的点击变成对它们的调用，再把结果画出来
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from config import xhangge_settings as xhangge_config
from gui.xhangge_avatars import xhangge_apply_paw_cursor, xhangge_hand_cursor
from gui.xhangge_cute_progress import XhanggeCuteProgress
from gui.xhangge_dialogs import (
    show_confirm_dialog,
    show_ok_dialog,
    show_rename_dialog,
    show_warning_dialog,
)
from gui.xhangge_resize import XhanggeResizeHelper
from services.xhangge_kb_service import (
    XhanggeKbImportWorker,
    xhangge_delete_kb_everywhere,
    xhangge_delete_kb_file_everywhere,
)

# 文件选择框里给用户看的过滤器（Qt 的写法：显示名 + 通配符）
_XHANGGE_FILE_FILTER = "文档喵 (*.pdf *.txt *.md *.docx);;所有文件 (*)"


def _xhangge_fmt_size(n):
    """把字节数变成人类好读的字符串（自适应单位）。

    为什么要这个函数：以前一律换算成 MB 保留一位小数，
    结果 1200 字节的文件显示成「0.0MB」——
    容量明明记上了，看起来却像没导入一样（真踩过的坑喵）。
    现在小的按 B / KB 显示，大的才用 MB。
    """
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f}MB"
    if n >= 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n}B"


class XhanggeKbDialog(QDialog):
    """知识库管理窗口。"""

    # 关窗时告诉主窗口"绑定/开关可能有变化，刷新一下"（暂时没人监听也留着，第5步会用到）
    session_kb_changed = Signal()

    def __init__(self, parent, db, session_id, theme_key="pink"):
        super().__init__(parent)
        self.db = db
        self.session_id = session_id
        self.theme_key = theme_key

        # 正在导入的线程 + 排队等待的文件列表。
        # 一次只导入一个（进度条只有一条），后来的排大队。
        self._import_worker = None
        self._import_queue = []

        # 无边框 + 透明背景（圆角才能显示），模态
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(860, 620)
        self.setMinimumSize(780, 540)
        self._drag_pos = None

        self._build_ui()
        # 无边框窗口：装上"拖边缘/角调整大小"的能力
        self._resize_helper = XhanggeResizeHelper(self)
        # 知识库窗也显示粉色猫爪指针
        xhangge_apply_paw_cursor(self)
        self._refresh_all()

    # ========================================================
    # 界面搭建
    # ========================================================
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setObjectName("SettingsFrame")  # 复用设置窗的圆角描边样式
        outer.addWidget(frame)

        root = QVBoxLayout(frame)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_title_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_left_panel())
        body.addWidget(self._build_right_panel(), 1)
        root.addLayout(body)

        # ---- 右下角拖拽把手：无边框窗口没有系统边框可拖，
        #      靠它才能调整窗口大小（用户反馈过"窗口大小变不了"喵）----
        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(16, 16)
        self._size_grip.raise_()

    def resizeEvent(self, event):
        """窗口大小变化：拖拽把手永远待在右下角。"""
        super().resizeEvent(event)
        self._size_grip.move(self.width() - 18, self.height() - 18)

    def _build_title_bar(self):
        """小标题栏（可拖动 + 关闭按钮），和设置窗同一个套路。"""
        bar = QFrame()
        bar.setObjectName("SettingsTitleBar")
        bar.setFixedHeight(44)

        title = QLabel("📚 知识库喵")
        title.setObjectName("SettingsTitleLabel")

        # 标题旁边的小提示：没装 Ollama 和 bge-m3 用不了知识库
        hint = QLabel("要先下载 ollama 和 bge-m3 才能正常使用喵~")
        hint.setObjectName("SettingsHint")

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setFixedSize(34, 26)
        close_btn.setCursor(xhangge_hand_cursor())
        close_btn.clicked.connect(self.close)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addWidget(close_btn)

        bar.mousePressEvent = self._bar_mouse_press
        bar.mouseMoveEvent = self._bar_mouse_move
        bar.mouseReleaseEvent = self._bar_mouse_release
        return bar

    def _build_left_panel(self):
        """左边：新建按钮 + 知识库列表（最多 10 个）。"""
        panel = QFrame()
        panel.setObjectName("KbPanel")
        panel.setFixedWidth(180)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.new_kb_btn = QPushButton("＋ 新建知识库喵")
        self.new_kb_btn.setObjectName("SettingsBtn")
        self.new_kb_btn.setCursor(xhangge_hand_cursor())
        self.new_kb_btn.clicked.connect(self._on_new_kb)
        layout.addWidget(self.new_kb_btn)

        self.kb_list = QListWidget()
        self.kb_list.setObjectName("KbList")
        self.kb_list.setCursor(xhangge_hand_cursor())
        self.kb_list.currentRowChanged.connect(self._on_kb_selected)
        layout.addWidget(self.kb_list, 1)

        # 底部小字：还剩几个库可以建
        self.kb_count_label = QLabel("")
        self.kb_count_label.setObjectName("SettingsHint")
        self.kb_count_label.setWordWrap(True)
        layout.addWidget(self.kb_count_label)
        return panel

    def _build_right_panel(self):
        """右边：当前会话卡片 + 选中库的详情（整体可滚动）。"""
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        # 存个引用：导入新文件后要滚到文件列表底部（把新文件露出来）
        self._files_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        layout.addWidget(self._build_session_card())
        layout.addWidget(self._build_kb_detail())
        layout.addStretch(1)
        scroll.setWidget(page)
        return scroll

    def _build_session_card(self):
        """「当前会话喵」卡片：检索开关 + 已绑定的库。"""
        card = QFrame()
        card.setObjectName("SettingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("🐱 当前会话喵")
        title.setObjectName("SettingsCardTitle")
        layout.addWidget(title)

        # 检索开关：绑定是"把书放桌上"，开关是"允不允许翻书"
        self.rag_check = QCheckBox("🔍 回答时翻知识库（要先绑定至少一个库喵）")
        self.rag_check.setCursor(xhangge_hand_cursor())
        self.rag_check.toggled.connect(self._on_rag_toggled)
        layout.addWidget(self.rag_check)

        # 本会话已绑定的库（小药丸，点一下解绑）
        self.bound_row = QHBoxLayout()
        self.bound_row.setSpacing(6)
        bound_tag = QLabel("本会话绑定的库：")
        bound_tag.setObjectName("SettingsText")
        bound_tag.setFixedWidth(104)
        self.bound_row.addWidget(bound_tag)
        self.bound_row.addStretch(1)
        layout.addLayout(self.bound_row)

        hint = QLabel(
            "一个会话最多绑定 "
            + str(xhangge_config.XHANGGE_MAX_KB_PER_SESSION)
            + " 个库喵。选中某个库后点「📎 绑定会话」，勾选要绑定到哪些会话。"
        )
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return card

    def _build_kb_detail(self):
        """选中知识库的详情卡：容量、导入、拖拽区、文件列表。"""
        self.detail_card = QFrame()
        self.detail_card.setObjectName("SettingsCard")
        self.detail_layout = QVBoxLayout(self.detail_card)
        self.detail_layout.setContentsMargins(16, 12, 16, 12)
        self.detail_layout.setSpacing(10)

        # ---- 第一行：库标题 + 操作按钮 ----
        head = QHBoxLayout()
        self.kb_title = QLabel("还没有选中知识库喵")
        self.kb_title.setObjectName("SettingsCardTitle")
        # 长库名换行而不是把右侧按钮挤出窗口（同文件行的修复思路）
        self.kb_title.setWordWrap(True)
        self.kb_title.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        head.addWidget(self.kb_title, 1)

        self.bind_btn = QPushButton("📎 绑定会话")
        self.bind_btn.setObjectName("SettingsGhostBtn")
        self.bind_btn.setCursor(xhangge_hand_cursor())
        self.bind_btn.clicked.connect(self._on_bind_clicked)
        head.addWidget(self.bind_btn)

        # 已绑定会话数（点「绑定会话」后按勾选更新）
        self.bind_count_label = QLabel("")
        self.bind_count_label.setObjectName("SettingsHint")
        head.addWidget(self.bind_count_label)

        self.rename_btn = QPushButton("✏️ 重命名")
        self.rename_btn.setObjectName("SettingsGhostBtn")
        self.rename_btn.setCursor(xhangge_hand_cursor())
        self.rename_btn.setToolTip("给这个知识库改名字喵")
        self.rename_btn.clicked.connect(self._on_rename_kb)
        head.addWidget(self.rename_btn)

        self.del_kb_btn = QPushButton("🗑 删除知识库")
        self.del_kb_btn.setObjectName("SettingsDangerBtn")
        self.del_kb_btn.setCursor(xhangge_hand_cursor())
        self.del_kb_btn.setToolTip(
            "删掉整个知识库（文件副本、向量、绑定关系全清，你的原文件不受影响）"
        )
        self.del_kb_btn.clicked.connect(self._on_delete_kb)
        head.addWidget(self.del_kb_btn)
        self.detail_layout.addLayout(head)

        # ---- 容量条（复用可爱进度条，当"油表"用）----
        cap_title = QLabel("容量喵")
        cap_title.setObjectName("KbCapTitle")
        self.detail_layout.addWidget(cap_title)
        self.capacity_bar = XhanggeCuteProgress()
        self.capacity_bar.xhangge_apply_theme(self.theme_key)
        self.capacity_bar.setFixedHeight(26)
        self.detail_layout.addWidget(self.capacity_bar)

        # ---- 导入按钮 + 导入进度 ----
        tools = QHBoxLayout()
        self.import_btn = QPushButton("📁 选文件导入喵")
        self.import_btn.setObjectName("SettingsBtn")
        self.import_btn.setCursor(xhangge_hand_cursor())
        self.import_btn.clicked.connect(self._on_pick_files)
        tools.addWidget(self.import_btn)

        self.cancel_import_btn = QPushButton("取消导入喵")
        self.cancel_import_btn.setObjectName("SettingsGhostBtn")
        self.cancel_import_btn.setCursor(xhangge_hand_cursor())
        self.cancel_import_btn.clicked.connect(self._on_cancel_import)
        self.cancel_import_btn.setVisible(False)
        tools.addWidget(self.cancel_import_btn)
        tools.addStretch(1)
        self.detail_layout.addLayout(tools)

        self.import_progress = XhanggeCuteProgress()
        self.import_progress.xhangge_apply_theme(self.theme_key)
        self.import_progress.setVisible(False)
        self.detail_layout.addWidget(self.import_progress)

        # ---- 拖拽投放区 ----
        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("KbDropZone")
        self.drop_zone.setFixedHeight(64)
        # setAcceptDrops：打开"接收拖拽"的开关，默认是关的
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.dragEnterEvent = self._drop_enter
        self.drop_zone.dropEvent = self._drop
        self.drop_zone.dragLeaveEvent = self._drop_leave
        drop_label = QLabel(
            "把 pdf / txt / md / docx 文件拖到这里喵～\n"
            "（也可以点上面的「📁 选文件导入喵」）"
        )
        drop_label.setObjectName("SettingsHint")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setContentsMargins(8, 8, 8, 8)
        drop_layout.addWidget(drop_label)
        self.detail_layout.addWidget(self.drop_zone)

        # ---- 文件列表（动态往里加行）----
        self.files_container = QWidget()
        self.files_container.setObjectName("SettingsPage")
        self.files_layout = QVBoxLayout(self.files_container)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.files_layout.setSpacing(6)
        self.detail_layout.addWidget(self.files_container)

        return self.detail_card

    # ========================================================
    # 数据刷新（从数据库读，画到界面上）
    # ========================================================
    def _refresh_all(self):
        """刷新整扇窗：库列表、会话卡、详情卡。"""
        self._refresh_kb_list()
        self._refresh_session_card()
        self._refresh_detail()

    def _refresh_kb_list(self):
        """刷新左边的知识库列表。"""
        kbs = self.db.xhangge_list_kb()
        # 先记下当前选中的库 id（clear() 之后 currentRow 会变 -1，就取不到了）
        current = self._current_kb()
        current_id = current.id if current is not None else None

        self.kb_list.blockSignals(True)  # 填列表时不触发"选中变了"
        self.kb_list.clear()
        for kb in kbs:
            # 两行显示：名字一行，"几个文件 · 多少容量"一行
            # 容量用自适应单位（B/KB/MB），小文件才不会显示成"0.0MB"
            item = QListWidgetItem(
                f"{kb.name}\n{kb.file_count} 个文件 · {_xhangge_fmt_size(kb.used_bytes)}"
            )
            item.setSizeHint(item.sizeHint().__class__(item.sizeHint().width(), 44))
            self.kb_list.addItem(item)
        # 恢复之前选中的那个；之前没选中就落到第一个
        if current_id is not None:
            for i, kb in enumerate(kbs):
                if kb.id == current_id:
                    self.kb_list.setCurrentRow(i)
                    break
        elif kbs:
            self.kb_list.setCurrentRow(0)
        self.kb_list.blockSignals(False)

        # 新建按钮：建满 10 个就灰掉
        full = len(kbs) >= xhangge_config.XHANGGE_MAX_KB_COUNT
        self.new_kb_btn.setEnabled(not full)
        self.new_kb_btn.setToolTip(
            "最多建 " + str(xhangge_config.XHANGGE_MAX_KB_COUNT) + " 个喵"
            if full else ""
        )
        self.kb_count_label.setText(
            f"已建 {len(kbs)} / {xhangge_config.XHANGGE_MAX_KB_COUNT} 个喵"
        )

    def _refresh_session_card(self):
        """刷新当前会话卡：开关状态 + 已绑定的库药丸。"""
        state = self.db.xhangge_get_session_state(self.session_id)
        self.rag_check.blockSignals(True)
        self.rag_check.setChecked(state.rag_enabled)
        self.rag_check.blockSignals(False)
        # 没绑定任何库时，开关允许打开但会提示；这里不禁用，
        # 让用户能先开开关再绑库
        self.rag_check.setToolTip(
            "开着但一个库都没绑的话，雪花喵没书可翻，就正常回答喵"
        )

        # 清掉旧的药丸，画新的
        while self.bound_row.count() > 2:  # 保留"已绑定："和最后的弹簧
            item = self.bound_row.takeAt(1)
            if item.widget() is not None:
                item.widget().deleteLater()
        for kb_id in state.kb_ids:
            kb = self.db.xhangge_get_kb(kb_id)
            if kb is None:
                continue
            chip = QPushButton(f"📚 {kb.name} ✕")
            chip.setObjectName("CapsuleBtn")
            chip.setCursor(xhangge_hand_cursor())
            chip.setToolTip("点一下解除绑定喵")
            chip.clicked.connect(
                lambda _=False, kid=kb_id: self._unbind(kid)
            )
            self.bound_row.insertWidget(self.bound_row.count() - 1, chip)

    def _refresh_detail(self):
        """刷新选中库的详情：标题、绑定按钮、容量、文件列表。"""
        kb = self._current_kb()
        importing = self._import_worker is not None

        if kb is None:
            self.kb_title.setText("还没有知识库喵～点左上角「＋ 新建知识库喵」建一个")
            for w in (self.bind_btn, self.rename_btn, self.del_kb_btn,
                      self.import_btn, self.drop_zone):
                w.setEnabled(False)
            self.capacity_bar.xhangge_set_progress(0, "— / 30MB")
            self._set_files([])
            return

        for w in (self.rename_btn, self.del_kb_btn):
            w.setEnabled(True)
        self.import_btn.setEnabled(not importing)
        self.drop_zone.setEnabled(True)

        self.kb_title.setText(f"📖 {kb.name}（{kb.file_count} 个文件）")

        # 绑定按钮状态 + 已绑定会话（列出会话名，一目了然）
        self.bind_btn.setEnabled(True)
        self.bind_btn.setText("📎 绑定会话")
        bound_ids = self.db.xhangge_get_kb_session_ids(kb.id)
        sessions = self.db.list_sessions()
        names = [s["title"] for s in sessions if s["id"] in bound_ids]
        if names:
            self.bind_count_label.setText(
                f"已绑定 {len(names)} 个会话：{'、'.join(names)}"
            )
        else:
            self.bind_count_label.setText("已绑定 0 个会话")

        # 容量条当"油表"：百分比 = 已用/上限。
        # 注意小文件的百分比会四舍五入成 0%（比如 2KB / 30MB），
        # 条会纹丝不动、看起来像没更新——所以只要装了东西，
        # 至少露 3% 的头，让用户看见"条动了"喵（真实数字看旁边文字）。
        percent = int(kb.used_bytes / xhangge_config.XHANGGE_MAX_KB_BYTES * 100)
        if kb.used_bytes > 0:
            percent = max(percent, 3)
        self.capacity_bar.xhangge_set_progress(
            percent,
            f"{_xhangge_fmt_size(kb.used_bytes)} / "
            f"{xhangge_config.XHANGGE_MAX_KB_BYTES / 1024 / 1024:.0f} MB",
        )

        self._set_files(self.db.xhangge_list_kb_files(kb.id))

    def _set_files(self, files):
        """把文件列表画出来（每行：名字+大小+块数+删除按钮）。"""
        # 清空旧的。先 hide() 再 deleteLater()：
        # deleteLater 要等事件循环跑起来才真删，先 hide 能保证
        # 这一帧就把旧行藏掉（不然看起来像"删了没反应"喵）
        while self.files_layout.count():
            item = self.files_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

        if not files:
            empty = QLabel("（这个库还没有文件喵，拖一个进来试试～）")
            empty.setObjectName("SettingsHint")
            self.files_layout.addWidget(empty)
            return

        for f in files:
            row = QFrame()
            row.setObjectName("KbFileRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(8)

            name = QLabel(f"📄 {f.file_name}")
            name.setToolTip("副本保存在：" + f.copy_path)
            # 关键修复：文件名要能换行、能被压窄。
            # 以前长文件名会把整行撑宽，而横向滚动条是关着的——
            # 结果右边的删除按钮被挤出可视范围，看得见名字却点不到按钮。
            name.setWordWrap(True)
            name.setSizePolicy(
                QSizePolicy.Policy.Ignored,   # 允许被压到比"理想宽度"窄
                QSizePolicy.Policy.Preferred,
            )
            info = QLabel(
                f"{_xhangge_fmt_size(f.size_bytes)} · {f.chunk_count} 块"
            )
            info.setObjectName("SettingsHint")
            info.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred
            )
            del_btn = QPushButton("🗑 删除")
            del_btn.setObjectName("SettingsDangerBtn")
            del_btn.setCursor(xhangge_hand_cursor())
            del_btn.setToolTip("从知识库里删掉这个文件（只删副本，不碰你的原文件喵）")
            del_btn.setEnabled(self._import_worker is None)
            del_btn.setSizePolicy(
                QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred
            )
            del_btn.clicked.connect(
                lambda _=False, fid=f.id: self._on_delete_file(fid)
            )

            row_layout.addWidget(name, 1)
            row_layout.addWidget(info)
            row_layout.addWidget(del_btn)
            self.files_layout.addWidget(row)

    def _current_kb(self):
        """当前选中的知识库（没选中/没建过返回 None）。"""
        row = self.kb_list.currentRow()
        kbs = self.db.xhangge_list_kb()
        if 0 <= row < len(kbs):
            return kbs[row]
        return None

    # ========================================================
    # 交互：建库 / 改名 / 删库
    # ========================================================
    def _on_new_kb(self):
        name = show_rename_dialog(
            self, "", dialog_title="新建知识库喵", prompt="📚 给新知识库起个名字喵"
        )
        if not name:
            return
        kb_id = self.db.xhangge_create_kb(name)
        if kb_id is None:
            show_warning_dialog(
                self, "建不了喵",
                "名字重复了，或者已经建满 "
                + str(xhangge_config.XHANGGE_MAX_KB_COUNT) + " 个了喵～",
            )
            return
        self._refresh_all()
        # 选中新库，让用户直接开始导文件
        kbs = self.db.xhangge_list_kb()
        for i, kb in enumerate(kbs):
            if kb.id == kb_id:
                self.kb_list.setCurrentRow(i)
        self._refresh_detail()

    def _on_rename_kb(self):
        kb = self._current_kb()
        if kb is None:
            return
        new_name = show_rename_dialog(
            self, kb.name, dialog_title="重命名喵", prompt="✏️ 给这个知识库改个名字喵"
        )
        if not new_name or new_name == kb.name:
            return
        if not self.db.xhangge_rename_kb(kb.id, new_name):
            show_warning_dialog(self, "改不了喵", "这个名字已经被别的库用了喵～")
            return
        self._refresh_all()

    def _on_delete_kb(self):
        kb = self._current_kb()
        if kb is None:
            return
        if self._import_worker is not None:
            show_warning_dialog(
                self, "先等等喵", "这个库正在导入文件，等导入结束（或取消）再删喵～"
            )
            return
        if not show_confirm_dialog(
            self, "删除知识库喵？",
            "「" + kb.name + "」里的所有文件、向量和绑定关系都会消失喵，\n"
            "确定吗？（你电脑里的原文件不受影响）",
        ):
            return
        xhangge_delete_kb_everywhere(self.db, kb.id)
        self.session_kb_changed.emit()
        self._refresh_all()
        show_ok_dialog(
            self, "删除成功喵",
            "「" + kb.name + "」和里面的文件、向量、绑定都清掉了喵～\n"
            "（你电脑里的原文件完好无损）",
        )

    # ========================================================
    # 交互：绑定 / 解绑 / 检索开关
    # ========================================================
    def _on_bind_clicked(self):
        """点「绑定会话」：弹出会话列表，勾选即绑定到对应会话。"""
        kb = self._current_kb()
        if kb is None:
            return
        XhanggeKbBindDialog(self, self.db, kb).exec()
        # 弹窗里改了绑定关系，刷新会话卡和详情
        self.session_kb_changed.emit()
        self._refresh_session_card()
        self._refresh_detail()

    def _unbind(self, kb_id):
        self.db.xhangge_unbind_kb(self.session_id, kb_id)
        self.session_kb_changed.emit()
        self._refresh_session_card()
        self._refresh_detail()

    def _on_rag_toggled(self, checked):
        self.db.xhangge_set_session_rag_enabled(self.session_id, checked)

    # ========================================================
    # 交互：导入（选文件 / 拖拽 / 队列 / 进度 / 取消）
    # ========================================================
    def _on_pick_files(self):
        if self._current_kb() is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选要导入的文件喵～", "", _XHANGGE_FILE_FILTER
        )
        self._enqueue_files(paths)

    def _drop_enter(self, event):
        """有东西拖进来悬停时：格式对就放行（虚线框会亮）。"""
        if self._files_ok(event.mimeData().urls()):
            event.acceptProposedAction()

    def _drop_leave(self, event):
        event.accept()

    def _drop(self, event):
        """松手：把拖进来的文件排进导入队列。"""
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        self._enqueue_files(paths)

    @staticmethod
    def _files_ok(urls):
        """这批拖进来的文件里有没有能用的（格式合法）。"""
        return any(
            Path(u.toLocalFile()).suffix.lower()
            in xhangge_config.XHANGGE_ALLOWED_DOC_EXTS
            for u in urls
        )

    def _enqueue_files(self, paths):
        """把一批文件排进导入队列，并启动导入（如果没在导的话）。

        每个文件连同"要导进哪个库"一起入队——否则导入中途切换选中库、
        或列表刷新把选中项重置后，后面的文件会跑错库（真踩过的坑喵）。
        """
        kb = self._current_kb()
        if kb is None or not paths:
            return
        skipped = []
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext in xhangge_config.XHANGGE_ALLOWED_DOC_EXTS:
                self._import_queue.append((kb.id, Path(p)))
            else:
                skipped.append(Path(p).name)
        if skipped:
            show_warning_dialog(
                self, "这几个导不了喵",
                "只支持 "
                + " / ".join(xhangge_config.XHANGGE_ALLOWED_DOC_EXTS)
                + " 喵～\n被跳过：" + "、".join(skipped),
            )
        if self._import_queue and self._import_worker is None:
            self._start_next_import()

    def _start_next_import(self):
        """从队头取一个文件（带目标库 id），开后台线程导入。"""
        if not self._import_queue:
            self._import_done_ui()
            return

        kb_id, file_path = self._import_queue.pop(0)
        self.import_btn.setEnabled(False)
        self.cancel_import_btn.setVisible(True)
        self.import_progress.setVisible(True)
        self.import_progress.xhangge_set_indeterminate("准备导入喵…")

        self._import_worker = XhanggeKbImportWorker(self.db, kb_id, file_path)
        self._import_worker.import_progress.connect(self._on_import_progress)
        self._import_worker.import_finished.connect(self._on_import_finished)
        self._import_worker.file_registered.connect(self._on_file_registered)
        self._import_worker.finished.connect(self._import_worker.deleteLater)
        self._import_worker.start()

    def _on_import_progress(self, percent, label):
        self.import_progress.xhangge_set_progress(percent, label)

    def _on_file_registered(self):
        """文件登记进库了：刷新容量条和文件列表，实时反映变化。

        文件在向量化之前就登记好了（容量会立刻增加），
        但以前要等整个导入结束才刷新界面，用户看不到容量变化；
        这里在登记那一刻就刷一次，容量条马上跳，文件也立刻出现在列表里。
        """
        self._refresh_detail()

    def _on_import_finished(self, ok, message):
        """一个文件导完了：报信（失败才弹窗），接着导下一个。"""
        self._import_worker = None
        if not ok:
            show_warning_dialog(self, "导入没成功喵", message)
        # 刷新详情（容量、文件数都变了）
        self._refresh_all()
        # 滚到文件列表底部，让刚导入的文件露出来
        # （修过的坑：文件行的换行高度是异步定稿的，只滚一次会差一截，
        #   所以这一帧和 120 毫秒后各滚一次喵）
        QTimer.singleShot(0, self._scroll_files_to_bottom)
        QTimer.singleShot(120, self._scroll_files_to_bottom)
        if self._import_queue:
            self._start_next_import()
        else:
            self._import_done_ui()

    def _scroll_files_to_bottom(self):
        """把右侧滚动区滚到底部（新导入的文件在列表末尾）。"""
        bar = self._files_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _import_done_ui(self):
        """队列空了：恢复按钮，进度条收起来。"""
        self.import_btn.setEnabled(self._current_kb() is not None)
        self.cancel_import_btn.setVisible(False)
        self.import_progress.setVisible(False)
        self.import_progress.xhangge_reset()

    def _on_cancel_import(self):
        if self._import_worker is None:
            return
        # 二次确认：防止手滑点了取消把导了一半的文件清掉
        if not show_confirm_dialog(
            self,
            "确认要终止喵？",
            "正在导入的这个文件会被删掉喵（只删我们保存的副本和已生成的向量，"
            "你电脑里的原文件不受影响），确定要终止吗？",
        ):
            return
        self.import_progress.xhangge_set_label("正在取消喵…")
        self._import_worker.request_stop()
        # 取消后队列里剩下的也不导了（用户大概率是想全停）
        self._import_queue.clear()

    # ========================================================
    # 交互：删单个文件
    # ========================================================
    def _on_delete_file(self, file_id):
        f = self.db.xhangge_get_kb_file(file_id)
        if f is None:
            return
        if not show_confirm_dialog(
            self, "删除文件喵？",
            "「" + f.file_name + "」会从知识库里移除喵（"
            "只删我们保存的副本，你电脑里的原文件不受影响），确定吗？",
        ):
            return
        xhangge_delete_kb_file_everywhere(self.db, file_id)
        self._refresh_all()
        # 用户明确想要"删除成功"的反馈弹窗（没有反馈时容易以为点了没反应喵）
        show_ok_dialog(
            self, "删除成功喵",
            "「" + f.file_name + "」已经从知识库里移除了喵～\n"
            "（你电脑里的原文件完好无损）",
        )

    # ========================================================
    # 选中变化 / 拖动窗口 / 关窗收尾
    # ========================================================
    def _on_kb_selected(self, row):
        self._refresh_detail()

    def _bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def _bar_mouse_move(self, event):
        if self._drag_pos is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _bar_mouse_release(self, event):
        self._drag_pos = None

    def closeEvent(self, event):
        """关窗前：把正在导入的线程停干净（不然信号会打到已销毁的界面上）。"""
        if self._import_worker is not None:
            self._import_worker.import_progress.disconnect(self._on_import_progress)
            self._import_worker.import_finished.disconnect(self._on_import_finished)
            self._import_worker.request_stop()
            self._import_worker.wait(5000)
            self._import_worker = None
        self.import_progress.xhangge_reset()
        self.capacity_bar.xhangge_reset()
        super().closeEvent(event)


class XhanggeKbBindDialog(QDialog):
    """「绑定会话」弹窗：列出所有会话，勾选即把当前知识库绑定到对应会话。

    一个知识库可以绑定到多个会话；每个会话末尾一个粉色小框，
    打上粉色对勾 = 绑定，取消对勾 = 解绑。
    """

    def __init__(self, parent, db, kb):
        super().__init__(parent)
        self.db = db
        self.kb = kb
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(420, 500)
        self.setMinimumSize(360, 360)
        xhangge_apply_paw_cursor(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame(self)
        frame.setObjectName("SettingsFrame")
        outer.addWidget(frame)
        root = QVBoxLayout(frame)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        title = QLabel(f"📎 绑定会话喵 · 「{kb.name}」")
        title.setObjectName("SettingsCardTitle")
        title.setWordWrap(True)
        root.addWidget(title)

        self.count_label = QLabel("")
        self.count_label.setObjectName("SettingsHint")
        root.addWidget(self.count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget = QWidget()
        self.list_layout = QVBoxLayout(list_widget)
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setSpacing(8)
        scroll.setWidget(list_widget)
        root.addWidget(scroll, 1)

        self._checkboxes = {}
        self._build_rows()
        self.list_layout.addStretch(1)

        close_btn = QPushButton("好哒喵～")
        close_btn.setObjectName("PrimaryBtn")
        close_btn.setCursor(xhangge_hand_cursor())
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

    def _build_rows(self):
        check_path = (
            xhangge_config.XHANGGE_CATGIRL_DIR.parent / "xhangge_checkmark.png"
        ).as_posix()
        checkbox_qss = (
            "QCheckBox { spacing: 8px; }"
            "QCheckBox::indicator { width: 20px; height: 20px;"
            " border: 2px solid #FF9EC4; border-radius: 6px; background: #FFFFFF; }"
            # 勾选态：浅粉底 + 粉色对勾；即使对勾图没加载，浅粉底也能看出已勾选
            "QCheckBox::indicator:checked { background: #FFE4EF;"
            f" image: url({check_path}); "
            "}"
        )
        sessions = self.db.list_sessions()
        bound_ids = set(self.db.xhangge_get_kb_session_ids(self.kb.id))
        for s in sessions:
            title = s["title"] or "未命名会话"
            cb = QCheckBox(title)
            cb.setChecked(s["id"] in bound_ids)
            cb.setCursor(xhangge_hand_cursor())
            cb.setStyleSheet(checkbox_qss)
            cb.toggled.connect(
                lambda checked, sid=s["id"]: self._on_toggle(sid, checked)
            )
            self._checkboxes[s["id"]] = cb
            self.list_layout.addWidget(cb)
        self._refresh_count()

    def _on_toggle(self, session_id, checked):
        if checked:
            ok = self.db.xhangge_bind_kb(session_id, self.kb.id)
            if not ok:
                cb = self._checkboxes.get(session_id)
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)
                show_warning_dialog(
                    self, "绑不上了喵",
                    "一个会话最多绑定 "
                    + str(xhangge_config.XHANGGE_MAX_KB_PER_SESSION)
                    + " 个知识库喵～先解绑一个再来。",
                )
                return
        else:
            self.db.xhangge_unbind_kb(session_id, self.kb.id)
        self._refresh_count()

    def _refresh_count(self):
        bound_ids = self.db.xhangge_get_kb_session_ids(self.kb.id)
        sessions = self.db.list_sessions()
        names = [s["title"] for s in sessions if s["id"] in bound_ids]
        if names:
            self.count_label.setText(f"已绑定 {len(names)} 个会话：{'、'.join(names)}")
        else:
            self.count_label.setText("已绑定 0 个会话喵")
