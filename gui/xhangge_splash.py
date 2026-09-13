# Author: xhangge
# This project is created by xhangge
"""
xhangge_splash —— 开启加载页（splash）

程序一启动就先弹它：悬浮的雪花喵圆形大头像 + 下方「snowcat～」
粉色艺术字，没有任何边框和底板，就那么飘在屏幕中央喵。
主窗口准备好的前一瞬间，它消失。

为什么要这个东西：
- 软件启动要加载 Qt、主题、主窗口等一串东西，快的机器半秒、
  慢的机器两三秒。这段时间里用户看到的是"什么都没发生"；
- 有了 splash，双击/命令行启动的**第一帧**就有反馈，
  而且顺便把"重量级导入"挪到 splash 出现之后，
  启动观感直接快了一个档次。

技术要点：
- Qt.SplashScreen：专门的启动画面窗口标志——没有任务栏图标、
  不抢焦点、天然适合干这个
- WA_TranslucentBackground + 无边框：头像和艺术字是"悬浮"的，
  没有卡片底板
- 素材缺失时优雅降级：头像退回 🐱、艺术字退回粉色字体
  （保证任何情况下 splash 都能显示，不会白屏报错）
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from config import xhangge_settings as xhangge_config
from gui.xhangge_avatars import xhangge_catgirl_pixmap

# 大头像直径（像素，两次各放大 1.3 倍：160→208→270）
_XHANGGE_SPLASH_AVATAR = 270
# 艺术字显示宽度（等比缩放：320→416→541）
_XHANGGE_SPLASH_TEXT_W = 541
# 头像和艺术字之间的间距
_XHANGGE_SPLASH_GAP = 31

# 艺术字素材位置（assets 目录下）
_XHANGGE_SPLASH_TEXT_PATH = (
    xhangge_config.XHANGGE_CATGIRL_DIR.parent / "xhangge_splash_text.png"
)


class XhanggeSplash(QWidget):
    """启动画面：圆形猫娘头像 + snowcat～ 艺术字，悬浮在屏幕正中。"""

    def __init__(self):
        super().__init__()
        # SplashScreen：无任务栏图标的启动画面；置顶保证不被别的窗口压住
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        # 透明背景（头像和字悬浮，没有底板）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 不抢焦点：用户可能正在别的窗口打字，splash 别去打扰
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.addStretch(1)

        # ---- 雪花喵圆形大头像 ----
        avatar = QLabel()
        avatar.setFixedSize(_XHANGGE_SPLASH_AVATAR, _XHANGGE_SPLASH_AVATAR)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setObjectName("AvatarLabel")
        pm = xhangge_catgirl_pixmap(_XHANGGE_SPLASH_AVATAR)
        if pm is not None:
            avatar.setPixmap(pm)
        else:
            # 素材加载失败也要能显示（退回 emoji）
            avatar.setText("🐱")
            font = QFont()
            font.setPixelSize(_XHANGGE_SPLASH_AVATAR - 40)
            avatar.setFont(font)
        layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- snowcat～ 粉色艺术字 ----
        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 记下艺术字实际要占多高，算窗口总高用（默认值 = 退回字体模式的高度）
        art_height = 110
        art_pm = None
        if _XHANGGE_SPLASH_TEXT_PATH.exists():
            art_pm = QPixmap(str(_XHANGGE_SPLASH_TEXT_PATH))
        if art_pm is not None and not art_pm.isNull():
            # 等比缩放到固定宽度，并记下实际高度
            scaled = art_pm.scaledToWidth(
                _XHANGGE_SPLASH_TEXT_W,
                Qt.TransformationMode.SmoothTransformation,
            )
            art.setPixmap(scaled)
            art_height = scaled.height()
        else:
            # 退回方案：粉色粗体字，至少名字还在喵
            art.setText("snowcat～")
            art.setStyleSheet(
                "color: #FF7BAC; font-size: 74px; font-weight: bold;"
                "background: transparent;"
            )
        layout.addWidget(art, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

        # ---- 窗口尺寸：按内容实际大小算（踩过的坑：早先写死 220 宽，
        #      而 320 宽的艺术字被左右裁掉，"没显示全"喵）----
        window_w = max(_XHANGGE_SPLASH_AVATAR, _XHANGGE_SPLASH_TEXT_W) + 80
        window_h = (
            _XHANGGE_SPLASH_AVATAR + art_height
            + _XHANGGE_SPLASH_GAP + 80
        )
        self.setFixedSize(window_w, window_h)
        self._move_to_center()

    def _move_to_center(self):
        """把自己挪到主屏幕正中央。"""
        screen = self.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )
