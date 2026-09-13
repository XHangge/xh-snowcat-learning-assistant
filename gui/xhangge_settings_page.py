# Author: xhangge
# This project is created by xhangge
"""
xhangge_settings_page —— ⚙️ 设置窗口

点标题栏的 ⚙️ 按钮就会打开这个窗口。它长这样：

    ┌──────────────────────────────────────────┐
    │ ⚙️ 设置喵                             ✕ │  ← 自己画的小标题栏
    ├──────────┬───────────────────────────────┤
    │ 🧠 模型   │  （右边显示当前选中那一页）    │
    │ 🤖 Agent  │                               │
    │ 🔍 搜索   │                               │
    │ 🎨 外观   │                               │
    │ ℹ️ 关于   │                               │
    └──────────┴───────────────────────────────┘

左边那条小侧边栏就是「留给以后扩展用」的地方：
以后想加新设置页，只要在 _build_nav() 里加一行、再写一个 _build_xxx_page()
就行了，不用动其它任何代码。

关于分层（很重要，这个项目一直守着这条规矩）：
这个文件属于 gui 层，只负责「显示界面」和「把用户的点击转成信号发出去」。
它自己不写任何 AI 逻辑：
- 要下载模型 → 交给 services/xhangge_ollama_deploy.py 的后台线程
- 要测试在线 API → 同样交给 services 层的后台线程
- 要读写配置 → 交给 models/xhangge_db.py 和 config/xhangge_settings.py
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import xhangge_settings as xhangge_config
from gui.xhangge_avatars import (
    xhangge_apply_paw_cursor,
    xhangge_clear_user_avatar,
    xhangge_hand_cursor,
    xhangge_ibeam_cursor,
    xhangge_save_user_avatar,
    xhangge_user_label,
)
from gui.xhangge_cute_progress import XhanggeCuteProgress
from gui.xhangge_dialogs import show_confirm_dialog, show_ok_dialog, show_warning_dialog
from gui.xhangge_resize import XhanggeResizeHelper
from gui.xhangge_themes import THEME_LABELS
from services.xhangge_ollama_deploy import (
    XhanggeLocalStatusWorker,
    XhanggeModelDownloadWorker,
    XhanggeOllamaInstallWorker,
    XhanggeOnlineTestWorker,
    xhangge_detect_ollama,
    xhangge_get_cached_status,
    xhangge_is_model_installed,
)


# ============================================================
# 一些造小控件的工具函数（避免下面重复写十几遍同样的三行代码）
# ============================================================
def _xhangge_title(text):
    """造一个页面大标题，例如「🧠 模型设置喵」"""
    label = QLabel(text)
    label.setObjectName("SettingsPageTitle")
    return label


def _xhangge_hint(text):
    """造一行灰色小字说明（告诉用户这个设置是干嘛的）"""
    label = QLabel(text)
    label.setObjectName("SettingsHint")
    label.setWordWrap(True)  # 太长自动换行，不会把窗口撑宽
    return label


def _xhangge_text(text):
    """造一行普通说明文字"""
    label = QLabel(text)
    label.setObjectName("SettingsText")
    label.setWordWrap(True)
    return label


def _xhangge_card(title=None):
    """造一张白色圆角卡片，返回 (卡片, 卡片内部的竖向布局)。

    为什么要卡片：设置项一多，界面就会变成一锅粥。
    把相关的几项圈进一张卡片里，用户一眼就知道「这几个是一伙的」。
    """
    card = QFrame()
    card.setObjectName("SettingsCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    if title:
        card_title = QLabel(title)
        card_title.setObjectName("SettingsCardTitle")
        layout.addWidget(card_title)
    return card, layout


def _xhangge_btn(text, object_name="SettingsBtn"):
    """造一个设置窗里的按钮（默认是粉色实心的主按钮）"""
    btn = QPushButton(text)
    btn.setObjectName(object_name)
    btn.setCursor(xhangge_hand_cursor())
    return btn


def _xhangge_badge(text, ok=True):
    """造一个状态小药丸，例如「✅ 已安装喵」/「⚠️ 未安装喵」"""
    label = QLabel(text)
    label.setObjectName("SettingsBadgeOk" if ok else "SettingsBadgeWarn")
    return label


def _xhangge_row(*widgets):
    """把几个控件横着排成一行，返回这一行的布局"""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    for w in widgets:
        if w is None:
            row.addStretch(1)  # 传 None 表示「这里塞一个弹簧」
        elif isinstance(w, QWidget):
            row.addWidget(w)
        else:
            row.addLayout(w)
    return row


# ============================================================
# 设置窗口本体
# ============================================================
class XhanggeSettingsDialog(QDialog):
    """设置窗口。

    对外发两个信号（主窗口接住它们）：
    - settings_saved(dict)  用户改了偏好设置，请主窗口写进设置文件
    - backend_changed()     模型后端换了（本地↔在线，或换了模型），
                            请主窗口让 llm_router 丢掉旧缓存重新建连接
    """

    settings_saved = Signal(dict)
    backend_changed = Signal()
    # 🎨 外观页换了主题（参数：主题标识 pink/light/dark）——主窗口立刻换肤
    theme_changed = Signal(str)
    # 👤 我的信息页改了用户名（参数：新昵称）
    username_changed = Signal(str)
    # 👤 我的信息页上传/删除了头像
    avatar_changed = Signal()

    def __init__(self, parent, db, settings):
        super().__init__(parent)

        # db：数据库对象（在线模型配置存在里面）
        self.db = db
        # settings：当前完整的用户设置字典。
        # 注意这里用 dict(settings) 复制一份，改的是副本，
        # 用户点保存才发信号让主窗口落盘，这样"取消"不会污染原设置。
        self.xhangge_settings = dict(settings)
        # 正在安装 Ollama / 下载模型的后台线程（None = 空闲）
        self._install_worker = None
        self._download_worker = None
        # 正在测试在线 API 的后台线程
        self._test_worker = None
        # 正在后台探测 Ollama 状态（避免 /api/tags 2 秒把设置窗卡住）
        self._status_worker = None
        # 「保存并使用」要先测试：测试通过后要保存的内容暂存在这
        self._pending_save = None

        # ---- 无边框 + 透明背景，圆角才能显示出来（和其它弹窗一个套路）----
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(760, 560)
        self.setMinimumSize(700, 500)
        self._drag_pos = None  # 拖动窗口用

        self._build_ui()
        # 无边框窗口：装上"拖边缘/角调整大小"的能力
        self._resize_helper = XhanggeResizeHelper(self)
        # 设置窗也显示粉色猫爪指针
        xhangge_apply_paw_cursor(self)
        # 所有输入框打字时显示粉色 I 型光标
        for le in self.findChildren(QLineEdit):
            le.setCursor(xhangge_ibeam_cursor())
        self._load_current_values()

    # ========================================================
    # 界面搭建
    # ========================================================
    def _build_ui(self):
        """搭出「小标题栏 + 左导航 + 右内容」这个整体框架。"""
        # 最外层：让圆角卡片充满整个窗口
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setObjectName("SettingsFrame")
        outer.addWidget(frame)

        root = QVBoxLayout(frame)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 顶部小标题栏（可以拖动窗口 + 一个关闭按钮）----
        root.addWidget(self._build_title_bar())

        # ---- 下半部分：左导航 + 右内容 ----
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        body.addWidget(self._build_nav())
        # 1 表示「剩下的横向空间都给右边的内容区」
        body.addWidget(self._build_pages(), 1)
        root.addLayout(body)

    def _build_title_bar(self):
        """设置窗自己的小标题栏。"""
        bar = QFrame()
        bar.setObjectName("SettingsTitleBar")
        bar.setFixedHeight(44)

        title = QLabel("⚙️ 设置喵")
        title.setObjectName("SettingsTitleLabel")

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")  # 复用主窗口那个悬停变红的关闭按钮样式
        close_btn.setFixedSize(34, 26)
        close_btn.setCursor(xhangge_hand_cursor())
        close_btn.clicked.connect(self.close)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(close_btn)

        # 把拖动事件接到标题栏上（无边框窗口得自己实现拖动）
        bar.mousePressEvent = self._bar_mouse_press
        bar.mouseMoveEvent = self._bar_mouse_move
        bar.mouseReleaseEvent = self._bar_mouse_release
        return bar

    def _build_nav(self):
        """左侧导航栏。以后要加新设置页，就在 nav_items 里加一行。"""
        panel = QFrame()
        panel.setObjectName("SettingsNavPanel")
        panel.setFixedWidth(150)

        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.setCursor(xhangge_hand_cursor())

        # (显示文字, 是否可点)
        # 「🎨 外观喵」「👤 我的信息喵」已启用：主题/用户名/头像都搬进来了
        nav_items = [
            ("🧠 模型喵", True),
            ("🤖 Agent 喵", True),
            ("🔍 搜索喵", True),
            ("🎨 外观喵", True),
            ("👤 我的信息喵", True),
            ("ℹ️ 关于喵", True),
        ]
        for text, enabled in nav_items:
            item = QListWidgetItem(text)
            if not enabled:
                # ItemIsEnabled 这个标志去掉，这一项就点不了了（显示成灰色）
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.nav.addItem(item)

        # 选中第一项（模型设置），并让右边内容区跟着切换
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(self.nav)
        return panel

    def _build_pages(self):
        """右侧内容区：一个 QStackedWidget（一叠页面，一次只显示一张）。"""
        self.pages = QStackedWidget()
        # 每页都套一层滚动区。
        # 为什么必须套：模型设置页有两张卡片加一堆说明，内容比窗口高。
        # 不套滚动区的话，Qt 会硬把所有控件挤进有限的高度里，
        # 结果就是卡片被压扁、文字互相叠在一起，根本看不清。
        # 套上之后内容超出就出现滚动条，卡片各自保持该有的高度。
        self.pages.addWidget(self._wrap_scroll(self._build_model_page()))       # 第 0 页
        self.pages.addWidget(self._wrap_scroll(self._build_agent_page()))       # 第 1 页
        self.pages.addWidget(self._wrap_scroll(self._build_search_page()))      # 第 2 页
        self.pages.addWidget(self._wrap_scroll(self._build_appearance_page()))  # 第 3 页：外观
        self.pages.addWidget(self._wrap_scroll(self._build_profile_page()))     # 第 4 页：我的信息
        self.pages.addWidget(self._wrap_scroll(self._build_about_page()))       # 第 5 页
        return self.pages

    @staticmethod
    def _wrap_scroll(page):
        """把一个页面装进滚动区里。"""
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        # setWidgetResizable(True)：让页面宽度跟着滚动区变，
        # 不加这句页面就会保持自己的原始宽度，右边留一大块空白。
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        # 横向永远不要滚动条：内容都会自动换行，出现横向滚动条只会碍事
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QFrame.Shape.NoFrame)  # 去掉滚动区自带的方框边
        return scroll

    @staticmethod
    def _page_shell():
        """造一个空白页面，返回 (页面控件, 页面内的竖向布局)。

        每页都长一样的外壳：统一的留白 + 间距，看起来才整齐。
        """
        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        return page, layout

    # ========================================================
    # 第 1 页：🧠 模型设置
    # ========================================================
    def _build_model_page(self):
        """模型设置页：本地 Ollama 和 在线 API 二选一（互斥）。"""
        page, layout = self._page_shell()
        layout.addWidget(_xhangge_title("🧠 模型设置喵"))
        layout.addWidget(_xhangge_hint(
            "雪花喵的「大脑」用哪个模型。本地和在线只能选一个喵～"
        ))

        # ---- 二选一的单选按钮 ----
        self.radio_local = QRadioButton("🖥️  用本地模型（Ollama，不花钱、不联网）")
        self.radio_online = QRadioButton("☁️  用在线 API（速度快、更聪明，要自己的 Key）")
        # toggled 信号：切换时立刻更新界面的可用状态
        self.radio_local.toggled.connect(self._on_backend_radio_changed)
        layout.addWidget(self.radio_local)
        layout.addWidget(self.radio_online)

        # ---- 卡片一：本地模型 ----
        layout.addWidget(self._build_local_card())
        # ---- 卡片二：在线 API ----
        layout.addWidget(self._build_online_card())

        # ---- 最后一条固定说明：Embedding 永远走本地 ----
        layout.addWidget(_xhangge_hint(
            "📌 小提示喵：知识库的「向量化」永远用本地的 "
            + xhangge_config.XHANGGE_EMBED_MODEL
            + "，不受上面这个开关影响。"
            "因为各家在线接口的向量格式不统一，而且把你的私人文档发到云端做向量化并不合适喵。"
            "所以用知识库的时候，Ollama 需要开着。"
        ))
        layout.addStretch(1)
        return page

    def _build_local_card(self):
        """本地 Ollama 那张卡片：状态 + 选模型 + 一键下载 + 可爱进度条。"""
        card, layout = _xhangge_card("本地模型喵")

        # ---- 第一行：Ollama 装了没有 ----
        self.ollama_badge = _xhangge_badge("检查中喵…", ok=True)
        layout.addLayout(_xhangge_row(
            _xhangge_text("Ollama 状态："), self.ollama_badge, None
        ))
        layout.addWidget(_xhangge_hint(
            "下载失败可手动装：Windows 在 cmd 运行 "
            "irm https://ollama.com/install.ps1 | iex 喵；"
            "macOS 用 brew install ollama 喵～"
        ))

        # ---- 第二行：选一个模型 + 它装了没有 ----
        self.local_model_combo = QComboBox()
        self.local_model_combo.setCursor(xhangge_hand_cursor())
        # 把配置里那份「消费级电脑跑得动」的模型清单填进下拉框。
        # addItem 的第二个参数是「隐藏数据」，存真正的模型名，
        # 显示的文字则是带说明的友好版本。
        for model_id, desc in xhangge_config.XHANGGE_PULLABLE_MODELS:
            self.local_model_combo.addItem(desc, model_id)
        self.local_model_combo.currentIndexChanged.connect(
            self._on_local_model_changed
        )
        self.model_badge = _xhangge_badge("检查中喵…", ok=True)
        layout.addLayout(_xhangge_row(
            self.local_model_combo, self.model_badge
        ))

        # ---- 第三行：一键部署按钮 ----
        self.pull_btn = _xhangge_btn("⬇️ 一键部署喵")
        self.pull_btn.clicked.connect(self._on_pull_clicked)
        self.pull_cancel_btn = _xhangge_btn("停止喵", "SettingsGhostBtn")
        self.pull_cancel_btn.clicked.connect(self._on_pull_cancel_clicked)
        self.pull_cancel_btn.setVisible(False)  # 只有下载时才出现
        layout.addLayout(_xhangge_row(
            self.pull_btn, self.pull_cancel_btn, None
        ))

        # ---- 第四行：二次元可爱进度条（下载时才显示）----
        self.pull_progress = XhanggeCuteProgress()
        self.pull_progress.setVisible(False)
        layout.addWidget(self.pull_progress)

        return card

    def _build_online_card(self):
        """在线 API 那张卡片：管理多份配置 + 测试连接 + 保存/删除。"""
        card, layout = _xhangge_card("在线 API 喵")
        self.online_card = card  # 存下来，切到「本地」时要把它整体灰掉

        # ---- 已保存的配置下拉框 ----
        self.online_combo = QComboBox()
        self.online_combo.setCursor(xhangge_hand_cursor())
        self.online_combo.currentIndexChanged.connect(self._on_online_selected)
        # 标签固定宽度，和下面四个输入框的标签对齐成一条竖线，看起来才整齐
        saved_tag = _xhangge_text("已保存")
        saved_tag.setFixedWidth(64)
        layout.addLayout(_xhangge_row(saved_tag, self.online_combo))

        layout.addWidget(self._separator())

        # ---- 填写/编辑一份配置的四个输入框 ----
        self.online_name = QLineEdit()
        self.online_name.setPlaceholderText("给它起个名字，比如「我的 DeepSeek」")
        self.online_base_url = QLineEdit()
        self.online_base_url.setPlaceholderText("https://api.deepseek.com/v1")
        self.online_api_key = QLineEdit()
        self.online_api_key.setPlaceholderText("sk-xxxxxxxxxxxxxxxx")
        # Password 模式：输入的 Key 显示成圆点，别人从背后看屏幕也偷不走
        self.online_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.online_model_name = QLineEdit()
        self.online_model_name.setPlaceholderText("deepseek-chat")

        for label_text, editor in (
            ("配置名称", self.online_name),
            ("接口地址", self.online_base_url),
            ("API Key", self.online_api_key),
            ("模型名称", self.online_model_name),
        ):
            tag = _xhangge_text(label_text)
            tag.setFixedWidth(64)
            layout.addLayout(_xhangge_row(tag, editor))

        layout.addWidget(_xhangge_hint(
            "接口地址要填「兼容 OpenAI 格式」的那个地址喵，"
            "常见的写法是官网给的地址后面带 /v1。"
            "DeepSeek、通义千问、Moonshot、硅基流动都支持这种格式。"
        ))

        # ---- 三个按钮：测试连接 / 保存 / 删除 ----
        self.online_test_btn = _xhangge_btn("🔌 测试连接喵", "SettingsGhostBtn")
        self.online_test_btn.clicked.connect(self._on_test_clicked)
        self.online_save_btn = _xhangge_btn("💾 保存并使用喵")
        self.online_save_btn.clicked.connect(self._on_online_save_clicked)
        self.online_delete_btn = _xhangge_btn("🗑 删除", "SettingsDangerBtn")
        self.online_delete_btn.clicked.connect(self._on_online_delete_clicked)
        layout.addLayout(_xhangge_row(
            self.online_test_btn, self.online_save_btn, None,
            self.online_delete_btn,
        ))

        # ---- 测试结果显示在这里 ----
        self.online_result = _xhangge_hint("")
        layout.addWidget(self.online_result)

        return card

    # ========================================================
    # 第 2 页：🤖 Agent 设置
    # ========================================================
    def _build_agent_page(self):
        """Agent 设置页：工作目录（安全边界）+ 沙箱超时 + 高危工具说明。"""
        page, layout = self._page_shell()
        layout.addWidget(_xhangge_title("🤖 Agent 设置喵"))
        layout.addWidget(_xhangge_hint(
            "Agent 模式下雪花喵能自己动手查资料、读写文件、跑代码。"
            "这一页管的是「她能动到哪里」——也就是安全边界喵。"
        ))

        # ---- 卡片一：工作目录 ----
        card, card_layout = _xhangge_card("工作目录喵（重要）")
        self.work_dir_edit = QLineEdit()
        self.work_dir_edit.setReadOnly(True)  # 只能用按钮选，不许手打，防打错路径
        self.work_dir_edit.setPlaceholderText("还没选喵（改文件、跑命令都会被拒绝）")
        pick_btn = _xhangge_btn("📁 选择文件夹", "SettingsGhostBtn")
        pick_btn.clicked.connect(self._on_pick_work_dir)
        clear_btn = _xhangge_btn("清空", "SettingsGhostBtn")
        clear_btn.clicked.connect(self._on_clear_work_dir)
        card_layout.addLayout(_xhangge_row(
            self.work_dir_edit, pick_btn, clear_btn
        ))
        card_layout.addWidget(_xhangge_hint(
            "为什么必须你自己选：不给 Agent 一个默认目录，她就没法在你没同意的情况下"
            "翻你电脑里的东西喵。所有「改文件」「跑命令」都只能发生在这个文件夹里面，"
            "想往外面走一步都会被直接拦下来。没选的时候，这两个工具干脆用不了。"
        ))
        layout.addWidget(card)

        # ---- 卡片二：沙箱 ----
        card2, card2_layout = _xhangge_card("代码沙箱喵")
        self.sandbox_spin = QSpinBox()
        self.sandbox_spin.setRange(3, 120)
        self.sandbox_spin.setSuffix(" 秒")
        self.sandbox_spin.setFixedWidth(110)
        card2_layout.addLayout(_xhangge_row(
            _xhangge_text("单次运行超时："), self.sandbox_spin, None
        ))
        card2_layout.addWidget(_xhangge_hint(
            "跑代码超过这个时间就强行掐掉喵。这是防死循环用的——"
            "万一雪花喵写出个 while True，没有这个限制就会一直吃你的 CPU。"
        ))
        layout.addWidget(card2)

        # ---- 卡片三：高危工具清单（只读展示，让用户知道啥时候会弹窗）----
        card3, card3_layout = _xhangge_card("需要你点「同意」的操作喵")
        tool_names = {
            "xhangge_write_file": "✏️ 写入 / 修改文件",
            "xhangge_delete_file": "🗑 删除文件",
            "xhangge_run_command": "⌨️ 执行命令",
        }
        for tool in xhangge_config.XHANGGE_HITL_TOOLS:
            card3_layout.addWidget(_xhangge_text("• " + tool_names.get(tool, tool)))
        card3_layout.addWidget(_xhangge_hint(
            "这三件事雪花喵不会自己偷偷做，每次都会先停下来弹窗问你，"
            "你点了同意她才动手喵。查资料、读文件、查知识库这些只看不改的操作不用问，"
            "不然一次任务弹十几个窗会烦死人。"
        ))
        layout.addWidget(card3)

        layout.addStretch(1)
        return page

    # ========================================================
    # 第 3 页：🔍 搜索设置
    # ========================================================
    def _build_search_page(self):
        """搜索设置页：联网搜索用哪个引擎。"""
        page, layout = self._page_shell()
        layout.addWidget(_xhangge_title("🔍 搜索设置喵"))
        layout.addWidget(_xhangge_hint(
            "Agent 模式下雪花喵要上网查资料时，走哪个搜索引擎喵。"
        ))

        card, card_layout = _xhangge_card("搜索引擎喵")
        self.radio_ddgs = QRadioButton("🦆  DuckDuckGo（免费、不用配置，装好就能用）")
        self.radio_tavily = QRadioButton("⭐  Tavily（专门给 AI 用的，结果更干净，要 Key）")
        self.radio_tavily.toggled.connect(self._on_search_radio_changed)
        card_layout.addWidget(self.radio_ddgs)
        card_layout.addWidget(self.radio_tavily)

        self.tavily_key_edit = QLineEdit()
        self.tavily_key_edit.setPlaceholderText("tvly-xxxxxxxxxxxxxxxx")
        self.tavily_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tavily_key_label = _xhangge_text("Tavily Key")
        self.tavily_key_label.setFixedWidth(78)
        card_layout.addLayout(_xhangge_row(
            self.tavily_key_label, self.tavily_key_edit
        ))
        card_layout.addWidget(_xhangge_hint(
            "Tavily 官网注册就送一批免费额度喵。"
            "如果选了 Tavily 但 Key 是空的，雪花喵会自动退回去用 DuckDuckGo，"
            "不会因为这个就查不了资料。"
        ))
        layout.addWidget(card)

        save_btn = _xhangge_btn("💾 保存搜索设置喵")
        save_btn.clicked.connect(self._on_save_search_clicked)
        layout.addLayout(_xhangge_row(save_btn, None))
        layout.addStretch(1)
        return page

    # ========================================================
    # 第 4 页：🎨 外观（主题切换，从侧边栏搬过来的）
    # ========================================================
    def _build_appearance_page(self):
        """外观页：三套主题单选，选中立刻换肤（和以前侧边栏的行为一致）。"""
        page, layout = self._page_shell()
        layout.addWidget(_xhangge_title("🎨 外观设置喵"))
        layout.addWidget(_xhangge_hint(
            "给整个软件换皮肤喵。选中的那一刻立刻生效，"
            "下次打开软件也会记住这个选择～"
        ))

        card, card_layout = _xhangge_card("主题喵")
        # 三个单选按钮 + 每个前面一个色卡小圆点，直观看出每套主题的底色
        self._theme_radios = {}
        theme_swatch_colors = {
            "pink": "#FFD9E8",
            "light": "#F7F8FA",
            "dark": "#332A3B",
        }
        for theme_key, theme_label in THEME_LABELS:
            row = QHBoxLayout()
            row.setSpacing(10)
            swatch = QLabel()
            swatch.setFixedSize(18, 18)
            # 用一个圆形色卡直观展示这套主题的底色
            swatch.setStyleSheet(
                "background: " + theme_swatch_colors[theme_key]
                + "; border-radius: 9px; border: 1px solid #B8B8C0;"
            )
            radio = QRadioButton(theme_label)
            radio.setCursor(xhangge_hand_cursor())
            # 单选组里哪个被选中 → 立刻发信号让主窗口换肤，
            # 同时同步到设置副本，否则关窗时 _emit_settings 会用旧主题把新主题覆盖掉
            radio.toggled.connect(
                lambda checked, key=theme_key: self._on_theme_radio(checked, key)
            )
            self._theme_radios[theme_key] = radio
            row.addWidget(swatch)
            row.addWidget(radio)
            row.addStretch(1)
            card_layout.addLayout(row)
        layout.addWidget(card)

        # 换主题后，本窗口里的可爱进度条也要跟着换配色（自收自发）
        self.theme_changed.connect(self._on_own_theme_changed)
        layout.addStretch(1)
        return page

    def _on_own_theme_changed(self, theme_key):
        """换肤后：设置窗自己带的小进度条也要换配色喵。"""
        if hasattr(self, "pull_progress"):
            self.pull_progress.xhangge_apply_theme(theme_key)

    def _on_theme_radio(self, checked, key):
        """选中了某套主题：同步到设置副本 + 发信号让主窗口换肤。"""
        if not checked:
            return
        self.xhangge_settings["theme"] = key
        self.theme_changed.emit(key)

    # ========================================================
    # 第 5 页：👤 我的信息（用户名 + 头像，从侧边栏搬过来的）
    # ========================================================
    def _build_profile_page(self):
        """我的信息页：改昵称 + 上传头像。"""
        page, layout = self._page_shell()
        layout.addWidget(_xhangge_title("👤 我的信息喵"))
        layout.addWidget(_xhangge_hint(
            "雪花喵该怎么称呼你、聊天时用哪张头像，都在这里设置喵～"
        ))

        # ---- 卡片一：用户名 ----
        name_card, name_layout = _xhangge_card("称呼喵")
        self.username_edit = QLineEdit(self.xhangge_settings.get("username", ""))
        self.username_edit.setPlaceholderText("不设置就叫杂狗喵")
        self.username_edit.setClearButtonEnabled(True)
        save_name_btn = _xhangge_btn("💾 保存称呼喵")
        save_name_btn.clicked.connect(self._on_save_username)
        # 回车 = 保存，顺手
        self.username_edit.returnPressed.connect(self._on_save_username)
        name_layout.addWidget(self.username_edit)
        name_row = _xhangge_row(save_name_btn, None)
        name_layout.addLayout(name_row)
        layout.addWidget(name_card)

        # ---- 卡片二：头像 ----
        avatar_card, avatar_layout = _xhangge_card("头像喵")
        # 大号预览：上传过的照片（圆形）/ 没上传显示 🐶
        self.avatar_preview = xhangge_user_label(96)
        avatar_layout.addWidget(self.avatar_preview)
        avatar_layout.addWidget(_xhangge_hint(
            "上传照片后会自动裁成圆形喵（png / jpg / webp 都行）。\n"
            "它会出现在每条你发出的消息旁边；不上传就用 🐶。"
        ))
        upload_btn = _xhangge_btn("🖼️ 上传头像喵")
        upload_btn.clicked.connect(self._on_upload_avatar)
        reset_btn = _xhangge_btn("恢复默认 🐶", "SettingsGhostBtn")
        reset_btn.clicked.connect(self._on_reset_avatar)
        avatar_layout.addLayout(_xhangge_row(upload_btn, reset_btn, None))
        layout.addWidget(avatar_card)

        layout.addStretch(1)
        return page

    def _on_save_username(self):
        """保存称呼：更新本窗的设置副本 + 发信号让主窗口生效。"""
        name = self.username_edit.text().strip()
        self.xhangge_settings["username"] = name
        self._emit_settings()
        self.username_changed.emit(name)

    def _on_upload_avatar(self):
        """选一张照片 → 裁圆保存 → 通知界面换新头像。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选一张头像照片喵～", "",
            "图片喵 (*.png *.jpg *.jpeg *.webp);;所有文件 (*)",
        )
        if not path:
            return  # 用户取消/关窗
        ok = xhangge_save_user_avatar(path)
        if not ok:
            show_warning_dialog(
                self, "这张图读不出来喵",
                "换个 png / jpg / webp 的图片试试喵 😿",
            )
            return
        # 重新画预览（换新图），并通知主窗口重画聊天气泡
        new_preview = xhangge_user_label(96)
        self._swap_widget(self.avatar_preview, new_preview)
        self.avatar_preview = new_preview
        self.avatar_changed.emit()

    def _on_reset_avatar(self):
        """恢复默认 🐶：删掉保存的头像文件，通知界面换回去。"""
        if not show_confirm_dialog(
            self, "恢复默认头像喵？", "会删掉你上传的头像，回到 🐶 喵，确定吗？"
        ):
            return
        xhangge_clear_user_avatar()
        new_preview = xhangge_user_label(96)
        self._swap_widget(self.avatar_preview, new_preview)
        self.avatar_preview = new_preview
        self.avatar_changed.emit()

    @staticmethod
    def _swap_widget(old_widget, new_widget):
        """把界面上的一个控件原地换成另一个（保持位置）。"""
        parent = old_widget.parent()
        if parent is None:
            return
        layout = parent.layout()
        if layout is None:
            return
        index = layout.indexOf(old_widget)
        if index < 0:
            return
        layout.removeWidget(old_widget)
        old_widget.deleteLater()
        layout.insertWidget(index, new_widget)

    # ========================================================
    # 第 6 页：ℹ️ 关于
    # ========================================================
    def _build_about_page(self):
        """关于页：猫娘立绘 + 作者署名 + GitHub 链接。"""
        page, layout = self._page_shell()
        layout.addWidget(_xhangge_title("ℹ️ 关于喵"))

        # ---- 猫娘立绘（素材缺失就退回 emoji，不让程序崩）----
        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art.setStyleSheet("background: transparent;")
        stand_path = xhangge_config.xhangge_catgirl_path(
            xhangge_config.XHANGGE_CATGIRL_STAND
        )
        if stand_path is not None:
            pixmap = QPixmap(str(stand_path))
            # 等比缩放到高 180，SmoothTransformation 让缩小后不锯齿
            art.setPixmap(pixmap.scaledToHeight(
                180,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            art.setText("🐱")
            art.setStyleSheet("background: transparent; font-size: 64px;")
        layout.addWidget(art)

        name = QLabel(xhangge_config.APP_NAME)
        name.setObjectName("SettingsCardTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        made_by = _xhangge_text("Made by " + xhangge_config.APP_AUTHOR + " 💖")
        made_by.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(made_by)

        # ---- GitHub 链接（可点击，用系统默认浏览器打开）----
        link = QLabel(
            '<a href="' + xhangge_config.XHANGGE_GITHUB_URL + '">'
            "🌟 GitHub 仓库（点个 star 支持一下喵）</a>"
        )
        link.setObjectName("SettingsLink")
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 这两行是让 QLabel 里的链接真的能点：
        # setOpenExternalLinks 交给系统浏览器打开，
        # setTextInteractionFlags 允许鼠标和链接交互。
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(link)

        layout.addWidget(_xhangge_hint(
            "这是 xhangge 开源的一个小作品喵。"
            "遇到 bug 或者有想要的功能，欢迎去仓库开 issue～"
        ))
        layout.addStretch(1)
        return page

    @staticmethod
    def _separator():
        """造一条细细的分隔线"""
        line = QFrame()
        line.setObjectName("SettingsSeparator")
        return line

    # ========================================================
    # 把当前设置填到界面上（打开窗口时调一次）
    # ========================================================
    def _load_current_values(self):
        """读数据库和设置文件，把界面上每个控件都设成当前的真实值。"""
        # ---- 本地 / 在线 是哪个 ----
        # 判断标准很简单：数据库里有没有一份「激活的」在线配置。
        # 有就是在线，没有就是本地。互斥关系由数据库那一列保证。
        active = self.db.xhangge_get_active_model_config()
        # blockSignals：填值的时候先把信号掐掉，
        # 不然 setChecked 会立刻触发 toggled，把用户还没看到的界面搞乱。
        self.radio_local.blockSignals(True)
        self.radio_online.blockSignals(True)
        self.radio_local.setChecked(active is None)
        self.radio_online.setChecked(active is not None)
        self.radio_local.blockSignals(False)
        self.radio_online.blockSignals(False)

        # ---- 本地模型下拉框选中当前用的那个 ----
        current_local = self.xhangge_settings.get(
            "local_model", xhangge_config.XHANGGE_MODEL_NAME
        )
        self.local_model_combo.blockSignals(True)
        index = self.local_model_combo.findData(current_local)
        if index >= 0:
            self.local_model_combo.setCurrentIndex(index)
        else:
            # 用户在配置文件里手写了一个清单里没有的模型名 → 临时加进去，
            # 不然一打开设置窗就被悄悄改成清单里的第一个，那才叫惊喜。
            self.local_model_combo.addItem(current_local + "（自定义）", current_local)
            self.local_model_combo.setCurrentIndex(
                self.local_model_combo.count() - 1
            )
        self.local_model_combo.blockSignals(False)

        # ---- 刷新 Ollama 和模型的安装状态 ----
        self._refresh_local_status()
        # ---- 刷新在线配置下拉框 ----
        self._refresh_online_combo(select_active=True)

        # ---- Agent 页 ----
        self.work_dir_edit.setText(self.xhangge_settings.get("agent_work_dir", ""))
        self.sandbox_spin.setValue(int(self.xhangge_settings.get(
            "sandbox_timeout", xhangge_config.XHANGGE_SANDBOX_TIMEOUT
        )))

        # ---- 搜索页 ----
        engine = self.xhangge_settings.get("search_engine", "ddgs")
        self.radio_tavily.blockSignals(True)
        self.radio_ddgs.setChecked(engine != "tavily")
        self.radio_tavily.setChecked(engine == "tavily")
        self.radio_tavily.blockSignals(False)
        self.tavily_key_edit.setText(self.xhangge_settings.get("tavily_api_key", ""))
        self._on_search_radio_changed()

        # ---- 外观页：选中当前正在用的主题 ----
        current_theme = self.xhangge_settings.get("theme", "pink")
        for key, radio in getattr(self, "_theme_radios", {}).items():
            radio.blockSignals(True)
            radio.setChecked(key == current_theme)
            radio.blockSignals(False)

        # ---- 我的信息页：用户名预填（头像预览是创建时自己取的）----
        self.username_edit.setText(self.xhangge_settings.get("username", ""))

        # ---- 最后统一刷一次「哪些控件能用」----
        self._on_backend_radio_changed()

    def _refresh_local_status(self):
        """刷新 Ollama / 模型状态小药丸。

        优先读启动时探测好的缓存；只有缓存没有、或本地模型变了才后台重新探测。
        （模型变了 = 用户在本地模型下拉框切换了模型，这是唯一需要二次探测的情况）
        """
        model_id = self.local_model_combo.currentData()
        cache = xhangge_get_cached_status()
        if cache is not None and cache.get("model_id") == model_id:
            # 缓存命中 → 直接显示，不重复跑脚本
            self._on_status_ready(
                cache["ollama_ok"], cache["version"], cache["models"]
            )
            return

        # 没缓存或模型变了 → 后台探测一次
        self.ollama_badge.setText("检查中喵…")
        self.model_badge.setText("检查中喵…")
        self._polish_badges()

        # 旧的后台探测如果还在跑，先断开，避免旧结果覆盖新结果
        if self._status_worker is not None:
            try:
                self._status_worker.status_ready.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._status_worker = None
        self._status_worker = XhanggeLocalStatusWorker(model_id)
        self._status_worker.status_ready.connect(self._on_status_ready)
        self._status_worker.finished.connect(self._status_worker.deleteLater)
        self._status_worker.start()

    def _on_status_ready(self, ollama_ok, version, models):
        """后台状态回来了，刷 Ollama 和模型两个小药丸。"""
        if ollama_ok:
            self.ollama_badge.setText("✅ 已安装喵")
            self.ollama_badge.setObjectName("SettingsBadgeOk")
            self.ollama_badge.setToolTip("Ollama " + (version or ""))
        else:
            self.ollama_badge.setText("⚠️ 没找到喵")
            self.ollama_badge.setObjectName("SettingsBadgeWarn")
            self.ollama_badge.setToolTip(
                "点「⬇️ 一键部署喵」会自动帮你下载并安装 Ollama"
            )

        model_id = self.local_model_combo.currentData()
        installed = False
        for m in models:
            # 前缀匹配："bge-m3" 能匹配上 Ollama 返回的 "bge-m3:latest"
            if m == model_id or m.split(":")[0] == model_id.split(":")[0]:
                installed = True
                break
        if model_id and installed:
            self.model_badge.setText("✅ 已下载喵")
            self.model_badge.setObjectName("SettingsBadgeOk")
        else:
            self.model_badge.setText("⚠️ 未下载喵")
            self.model_badge.setObjectName("SettingsBadgeWarn")

        self._polish_badges()

    def _polish_badges(self):
        """改了 objectName 后手动刷新样式（QSS 的坑：objectName 变了样式不自动重算）。"""
        for badge in (self.ollama_badge, self.model_badge):
            badge.style().unpolish(badge)
            badge.style().polish(badge)

    def _refresh_online_combo(self, select_active=False):
        """重新读数据库里所有在线配置，填进下拉框。"""
        configs = self.db.xhangge_list_model_configs()
        self.online_combo.blockSignals(True)
        self.online_combo.clear()
        self.online_combo.addItem("＋ 新建一份配置喵", None)
        target_row = 0
        for i, cfg in enumerate(configs):
            # 正在使用的那份前面加个 ✅，一眼能看出来
            prefix = "✅ " if cfg.is_active else "　"
            self.online_combo.addItem(
                prefix + cfg.name + "（" + cfg.model_name + "）", cfg.id
            )
            if select_active and cfg.is_active:
                target_row = i + 1  # +1 是因为第 0 项是「新建」
        self.online_combo.setCurrentIndex(target_row)
        self.online_combo.blockSignals(False)
        # 把选中那份的内容填到下面的输入框里
        self._fill_online_fields(self.online_combo.currentData())

    def _fill_online_fields(self, config_id):
        """把某份在线配置的内容填进四个输入框（config_id 为 None 就清空）。"""
        if config_id is None:
            self.online_name.clear()
            self.online_base_url.clear()
            self.online_api_key.clear()
            self.online_model_name.clear()
            self.online_delete_btn.setEnabled(False)
            return
        for cfg in self.db.xhangge_list_model_configs():
            if cfg.id == config_id:
                self.online_name.setText(cfg.name)
                self.online_base_url.setText(cfg.base_url)
                self.online_api_key.setText(cfg.api_key)
                self.online_model_name.setText(cfg.model_name)
                self.online_delete_btn.setEnabled(True)
                return

    # ========================================================
    # 各种交互响应
    # ========================================================
    def _on_nav_changed(self, row):
        """左边点了哪一项，右边就翻到那一页。"""
        if row >= 0:
            self.pages.setCurrentIndex(row)

    def _on_backend_radio_changed(self, *_):
        """本地 / 在线 切换了：把另一边的控件灰掉，让「互斥」看得见。

        这段在干什么：
        单选按钮本身已经保证「同时只能选一个」（QRadioButton 在同一个父控件下
        自动成为一组）。但光是圆点变了，用户还是会去点被禁用那边的按钮。
        所以这里再把整张卡片 setEnabled(False)，从视觉上就告诉他「这半边现在不生效」。
        """
        use_local = self.radio_local.isChecked()

        # 本地那半边：下载模型这件事，即使当前用的是在线 API 也允许做
        # （可以先把模型下好，以后随时切回来），
        # 所以它只跟"有没有正在安装/下载"有关，不跟本地/在线的选择有关。
        busy = self._install_worker is not None or self._download_worker is not None
        self.pull_btn.setEnabled(not busy)
        self.local_model_combo.setEnabled(not busy)

        # 在线那半边整张卡片
        self.online_card.setEnabled(not use_local)

        # 真正落库：切到本地就把在线配置全部取消激活
        if use_local:
            if self.db.xhangge_get_active_model_config() is not None:
                self.db.xhangge_activate_model_config(None)
                self._refresh_online_combo()
                self.backend_changed.emit()
        else:
            # 切到在线：如果一份配置都没有，提示用户先填一份，
            # 但不强行把圆点弹回去——让他就在这张卡片上填完，体验更顺。
            if not self.db.xhangge_list_model_configs():
                self.online_result.setText(
                    "还没有在线配置喵～ 在下面填好之后点「保存并使用」就生效啦。"
                )

    def _on_local_model_changed(self, *_):
        """换了本地模型：更新安装状态药丸，并记进设置。"""
        self._refresh_local_status()
        model_id = self.local_model_combo.currentData()
        if model_id:
            self.xhangge_settings["local_model"] = model_id
            self._emit_settings()
            # 本地模型换了，llm_router 缓存里那个旧连接就过期了
            self.backend_changed.emit()

    # ---------------- 下载模型 ----------------
    def _on_pull_clicked(self):
        """点「一键部署」：先确认 Ollama 装没装，再下载选中的模型。

        流程：
        1. 没装 Ollama → 弹窗问要不要装 → 确认后后台下载安装程序
        2. 装了 Ollama → 下载选中的模型 gguf 到项目 local_model 文件夹
        """
        if self._install_worker is not None or self._download_worker is not None:
            return  # 正在安装或下载

        # 1. 先探测 Ollama 装没装（实际跑一下 ollama -v）
        ollama_ok, _version = xhangge_detect_ollama()
        if not ollama_ok:
            if not show_confirm_dialog(
                self,
                "先装 Ollama 喵",
                "雪花喵还没找到 Ollama 喵，没有它就没法用本地模型。\n\n"
                "点「确定」就帮你在后台下载 Ollama 安装程序，\n"
                "下载完会弹出安装向导，你跟着点完就行啦～",
            ):
                return
            self._start_ollama_install()
            return

        # 2. Ollama 装了 → 下载选中的模型
        model_id = self.local_model_combo.currentData()
        if not model_id:
            return
        if xhangge_is_model_installed(model_id):
            show_warning_dialog(
                self,
                "已经有了喵",
                "「" + model_id + "」已经装好了，不用再下一遍喵～",
            )
            return
        self._start_model_download(model_id)

    def _start_ollama_install(self):
        """后台下载并启动 Ollama 安装程序。"""
        self._set_pull_busy(True)
        self.pull_progress.setVisible(True)
        self.pull_progress.xhangge_set_indeterminate("准备下载 Ollama 安装程序喵")
        self._install_worker = XhanggeOllamaInstallWorker()
        self._install_worker.install_progress.connect(self._on_pull_progress)
        self._install_worker.install_finished.connect(self._on_install_finished)
        self._install_worker.finished.connect(self._install_worker.deleteLater)
        self._install_worker.start()

    def _start_model_download(self, model_id):
        """后台把模型 gguf 下载到项目 local_model 文件夹。"""
        self._set_pull_busy(True)
        self.pull_progress.setVisible(True)
        self.pull_progress.xhangge_set_indeterminate("准备下载模型喵")
        self._download_worker = XhanggeModelDownloadWorker(model_id)
        self._download_worker.download_progress.connect(self._on_pull_progress)
        self._download_worker.download_finished.connect(self._on_pull_finished)
        self._download_worker.finished.connect(self._download_worker.deleteLater)
        self._download_worker.start()

    def _set_pull_busy(self, busy):
        """下载/安装期间：主按钮和模型下拉灰掉，停止按钮出现。"""
        self.pull_btn.setEnabled(not busy)
        self.local_model_combo.setEnabled(not busy)
        self.pull_cancel_btn.setVisible(busy)

    def _on_pull_cancel_clicked(self):
        """点「停止」：让正在跑的安装/下载线程停下来。"""
        if self._install_worker is not None:
            self.pull_progress.xhangge_set_label("正在停止喵")
            self._install_worker.request_stop()
        if self._download_worker is not None:
            self.pull_progress.xhangge_set_label("正在停止喵")
            self._download_worker.request_stop()

    def _on_pull_progress(self, percent, label):
        """后台线程报告进度 → 更新可爱进度条。

        percent 是 -1 时表示「解析不出百分比」，
        xhangge_set_progress 会自动切成不确定模式（猫娘来回跑）。
        """
        self.pull_progress.xhangge_set_progress(percent, label)

    def _on_pull_finished(self, ok, message):
        """模型下载结束（成功、失败、或用户手动停止）。"""
        self._download_worker = None
        self._set_pull_busy(False)

        if ok:
            self.pull_progress.xhangge_set_progress(100, "下载完成喵")
            model_id = self.local_model_combo.currentData() or ""
            show_ok_dialog(
                self,
                "下载好啦喵",
                "模型「" + model_id + "」下载好啦喵 ~🎉\n\n"
                "现在就可以在设置里选它来聊天了喵～",
            )
        else:
            self.pull_progress.setVisible(False)
            self.pull_progress.xhangge_reset()
            show_warning_dialog(self, "下载没成功喵", message)
        # 无论成功失败，模型的安装状态都可能变了，刷一下小药丸
        self._refresh_local_status()

    def _on_install_finished(self, ok, message):
        """Ollama 安装流程结束。"""
        self._install_worker = None
        self._set_pull_busy(False)
        self.pull_progress.setVisible(False)
        self.pull_progress.xhangge_reset()
        if ok:
            show_ok_dialog(self, "Ollama 装好啦喵", message)
        else:
            show_warning_dialog(self, "没装成喵", message)
        self._refresh_local_status()

    # ---------------- 在线 API ----------------
    def _on_online_selected(self, *_):
        """下拉框换了一份配置：把它的内容填到输入框里。"""
        self._fill_online_fields(self.online_combo.currentData())
        self.online_result.setText("")

    def _collect_online_input(self):
        """把四个输入框的内容收上来，顺便做基础校验。

        返回 (base_url, api_key, model_name, name)，
        校验不过就返回 None 并已经提示过用户了。
        """
        name = self.online_name.text().strip()
        base_url = self.online_base_url.text().strip()
        api_key = self.online_api_key.text().strip()
        model_name = self.online_model_name.text().strip()

        missing = []
        if not base_url:
            missing.append("接口地址")
        if not api_key:
            missing.append("API Key")
        if not model_name:
            missing.append("模型名称")
        if missing:
            self.online_result.setText("这几项还空着喵：" + "、".join(missing))
            return None
        # 名字没填就用模型名兜底，省得用户为了起名字卡住
        if not name:
            name = model_name
        return base_url, api_key, model_name, name

    def _on_test_clicked(self):
        """点了「测试连接」：开后台线程真的发一句话过去试试。"""
        if self._test_worker is not None:
            return
        collected = self._collect_online_input()
        if collected is None:
            return
        base_url, api_key, model_name, _ = collected

        self.online_test_btn.setEnabled(False)
        self.online_result.setText("正在连过去试试喵…")

        self._test_worker = XhanggeOnlineTestWorker(base_url, api_key, model_name)
        self._test_worker.test_finished.connect(self._on_test_finished)
        self._test_worker.finished.connect(self._test_worker.deleteLater)
        self._test_worker.start()

    def _on_test_finished(self, ok, message):
        """测试结果回来了。"""
        self._test_worker = None
        self.online_test_btn.setEnabled(True)
        self.online_result.setText(("✅ " if ok else "❌ ") + message)

    def _on_online_save_clicked(self):
        """点了「保存并使用」：先真连一次测试，通过才保存并启用。

        为什么必须先测（用户踩过的坑）：以前直接保存+启用，
        结果地址少打了 /v1、模型名拼错这种小笔误也能"保存成功"，
        用户一回到聊天就报错，还以为软件坏了喵。
        现在测试不通过就不启用，本地模型继续顶上，聊天永远不会被坏配置卡死。
        """
        if self._test_worker is not None:
            return
        collected = self._collect_online_input()
        if collected is None:
            return
        # 测试通过后要保存的内容先存起来，回调里用
        self._pending_save = collected

        base_url, api_key, model_name, _ = collected
        self.online_save_btn.setEnabled(False)
        self.online_test_btn.setEnabled(False)
        self.online_result.setText("先帮你真的连一下喵…（通过了才会保存启用）")

        # 标记：这次测试是为了保存，走专门的回调分支
        self._test_worker = XhanggeOnlineTestWorker(base_url, api_key, model_name)
        self._test_worker.test_finished.connect(self._on_save_test_finished)
        self._test_worker.finished.connect(self._test_worker.deleteLater)
        self._test_worker.start()

    def _on_save_test_finished(self, ok, message):
        """「保存并使用」的测试结果回来了。"""
        self._test_worker = None
        self.online_save_btn.setEnabled(True)
        self.online_test_btn.setEnabled(True)

        if not ok:
            # 测试失败：什么都不保存、不启用，本地模型继续用
            self.online_result.setText("❌ " + message)
            show_warning_dialog(
                self,
                "这份配置还用不了喵",
                "测试没通过，先不保存启用喵（聊天不受影响，还在用本地模型）。\n\n"
                + message + "\n\n"
                "常见原因：\n"
                "1. 接口地址少了结尾的 /v1\n"
                "2. 模型名称打错了（去官网抄一下喵）\n"
                "3. API Key 不对或没额度",
            )
            return

        base_url, api_key, model_name, name = self._pending_save
        config_id = self.online_combo.currentData()
        if config_id is None:
            # 新建一份
            config_id = self.db.xhangge_add_model_config(
                name, base_url, api_key, model_name
            )
        else:
            # 编辑已有的那份：数据库层没提供 update，
            # 这里用「删掉旧的 + 插入新的」实现，效果一样且不用改数据库层。
            self.db.xhangge_delete_model_config(config_id)
            config_id = self.db.xhangge_add_model_config(
                name, base_url, api_key, model_name
            )

        # 激活它。数据库那个方法会先把全表清 0 再置 1，
        # 所以「本地 vs 在线」和「多份在线配置之间」的互斥都是它保证的。
        self.db.xhangge_activate_model_config(config_id)

        # 界面同步：圆点跳到「在线」
        self.radio_online.blockSignals(True)
        self.radio_online.setChecked(True)
        self.radio_online.blockSignals(False)
        self.online_card.setEnabled(True)

        self._refresh_online_combo(select_active=True)
        self.online_result.setText("✅ 测试通过，已保存并启用喵～现在用的就是这份配置")
        # 通知主窗口：后端换了，把旧连接丢掉
        self.backend_changed.emit()

    def _on_online_delete_clicked(self):
        """点了「删除」：确认后删掉这份在线配置。"""
        config_id = self.online_combo.currentData()
        if config_id is None:
            return
        name = self.online_name.text().strip() or "这份配置"
        if not show_confirm_dialog(
            self,
            "删除配置喵？",
            "「" + name + "」会被删掉喵，\n确定吗？",
        ):
            return

        # 删的是不是正在用的那份？先记下来，删完要处理善后
        was_active = False
        for cfg in self.db.xhangge_list_model_configs():
            if cfg.id == config_id:
                was_active = cfg.is_active
                break

        self.db.xhangge_delete_model_config(config_id)
        self._refresh_online_combo(select_active=True)

        if was_active:
            # 正在用的那份被删了，没有后端可用会直接报错，
            # 所以自动退回本地模型，保证雪花喵还能说话。
            self.radio_local.blockSignals(True)
            self.radio_local.setChecked(True)
            self.radio_local.blockSignals(False)
            self.online_card.setEnabled(False)
            self.online_result.setText("删掉的是正在用的那份，已经自动切回本地模型喵～")
            self.backend_changed.emit()
        else:
            self.online_result.setText("删掉啦喵～")

    # ---------------- Agent 页 ----------------
    def _on_pick_work_dir(self):
        """选 Agent 工作目录。"""
        # getExistingDirectory：只让选文件夹，不让选文件
        path = QFileDialog.getExistingDirectory(
            self, "选一个文件夹给雪花喵当工作区喵", self.work_dir_edit.text() or ""
        )
        if not path:
            return  # 用户点了取消
        self.work_dir_edit.setText(path)
        self.xhangge_settings["agent_work_dir"] = path
        self._emit_settings()

    def _on_clear_work_dir(self):
        """清空工作目录 = 关掉「改文件 / 跑命令」这两个工具。"""
        self.work_dir_edit.clear()
        self.xhangge_settings["agent_work_dir"] = ""
        self._emit_settings()

    # ---------------- 搜索页 ----------------
    def _on_search_radio_changed(self, *_):
        """选了 Tavily 才让填 Key，选 DuckDuckGo 就把输入框灰掉。"""
        use_tavily = self.radio_tavily.isChecked()
        self.tavily_key_edit.setEnabled(use_tavily)
        self.tavily_key_label.setEnabled(use_tavily)

    def _on_save_search_clicked(self):
        """保存搜索设置。"""
        self.xhangge_settings["search_engine"] = (
            "tavily" if self.radio_tavily.isChecked() else "ddgs"
        )
        self.xhangge_settings["tavily_api_key"] = self.tavily_key_edit.text().strip()
        self._emit_settings()
        show_warning_dialog(
            self, "保存好啦喵", "搜索设置已经记下来了喵，下次查资料就按这个来～"
        )

    def _emit_settings(self):
        """把改动过的完整设置字典交给主窗口去落盘。

        为什么不在这里直接写文件：
        设置文件是主窗口在管的（它还持有用户名/主题/模式那几项）。
        如果这里也直接写一遍，两边就会互相覆盖，
        典型症状是「改了 A 项，B 项莫名恢复默认」。
        统一交给主窗口一个地方写，就不会打架。
        """
        # sandbox_timeout 是 QSpinBox，用户改完不一定点保存，
        # 所以每次发信号时都顺手把它的当前值带上。
        self.xhangge_settings["sandbox_timeout"] = self.sandbox_spin.value()
        self.settings_saved.emit(dict(self.xhangge_settings))

    # ========================================================
    # 拖动窗口（无边框窗口得自己实现，和主窗口标题栏一个套路）
    # ========================================================
    def _bar_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 记下「鼠标位置 - 窗口左上角」的偏移量
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

    # ========================================================
    # 关窗收尾
    # ========================================================
    def closeEvent(self, event):
        """关窗前把最新的数字输入框值存一下，并停掉还在跑的后台线程。

        为什么要停线程：
        窗口关了之后，线程发信号回来时接收方已经被销毁，
        Qt 会直接崩掉（典型报错是 wrapped C/C++ object has been deleted）。
        所以关窗前必须先让线程停下来并等它真的结束。
        """
        self._emit_settings()
        # 安装 / 下载线程先停掉（下载的是大文件，能被取消）
        if self._install_worker is not None:
            self._install_worker.request_stop()
            self._install_worker.wait(3000)  # 最多等 3 秒，避免关窗卡住
            self._install_worker = None
        if self._download_worker is not None:
            self._download_worker.request_stop()
            self._download_worker.wait(3000)
            self._download_worker = None
        # 测试/验证线程没法中途取消（一次 HTTP 请求发出去就只能等结果）。
        # 先把它的信号全部断开——这样即使它在窗口销毁之后才跑完，
        # 信号也不会再打到已经不存在的界面上，就不会崩了。
        # （可能连着"测试连接"或"保存前验证"两个回调中的某一个，
        #   所以用不带参数的 disconnect() 全断喵）
        if self._test_worker is not None:
            try:
                self._test_worker.test_finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._test_worker = None
        # 后台探测 Ollama 状态的线程：断开信号，别让它在窗口销毁后再打回来
        if self._status_worker is not None:
            try:
                self._status_worker.status_ready.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._status_worker = None
        # 停掉进度条的定时器，别让它在后台空转
        self.pull_progress.xhangge_reset()
        super().closeEvent(event)
