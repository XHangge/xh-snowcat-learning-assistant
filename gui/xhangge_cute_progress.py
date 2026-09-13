# Author: xhangge
# This project is created by xhangge
"""
xhangge_cute_progress —— 二次元可爱风进度条

为什么要自己画一个：
Qt 自带的 QProgressBar 只能靠 QSS 换颜色，而 QSS 不支持动画
（没有 CSS 那种 @keyframes）。想要"小猫爪跟着进度走""流动的糖果条"
"猫娘左右跑"这些动效，只能自己用 QPainter 画。

【两种模式】
1. 确定进度（知道百分比）：
   粉色渐变填充 + 从左往右滚动的高光斜纹 + 🐾 猫爪跟在进度头部轻轻跳
2. 不确定进度（还不知道总量，比如刚开始解析文档）：
   二次元猫娘立绘在槽里左右跑，跑到边缘会回头

【性能】
用一个 QTimer 每 50 毫秒（20帧/秒）重绘一次。
控件隐藏时自动停掉定时器，不做无用功，不占 CPU。
"""

import math

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from config import xhangge_settings as xhangge_config


class XhanggeCuteProgress(QWidget):
    """雪花喵专属的可爱进度条。

    用法：
        bar = XhanggeCuteProgress()
        bar.xhangge_set_progress(63, "下载中喵 2.9/4.7GB")   # 确定进度
        bar.xhangge_set_indeterminate("正在切块喵")            # 不确定进度
        bar.xhangge_reset()                                   # 复位隐藏
    """

    def __init__(self, parent=None, height=34):
        super().__init__(parent)
        self.setFixedHeight(height)
        # 最小宽度，太窄了猫娘跑不开
        self.setMinimumWidth(180)

        # ---- 状态 ----
        self._percent = 0            # 当前百分比 0-100
        self._label = ""             # 显示的文字
        self._indeterminate = False  # 是不是"不知道总量"的模式
        self._phase = 0.0            # 动画相位，每帧递增，驱动所有动效
        self._runner_x = 0.0         # 猫娘当前横向位置（0.0~1.0）
        self._runner_dir = 1         # 猫娘朝向：1 向右，-1 向左
        self._runner_frame = 0       # 跑步动画当前帧
        self._turning = 0            # 转身动画剩余帧数（>0 时显示回头图）

        # ---- 主题配色（可以被 xhangge_apply_theme 换掉）----
        self._c_track = QColor("#FFE4EF")     # 底槽
        self._c_fill_a = QColor("#FF9EC4")    # 填充渐变起点
        self._c_fill_b = QColor("#FF7BAC")    # 填充渐变终点
        self._c_text = QColor("#B85C7E")      # 文字
        self._c_shine = QColor(255, 255, 255, 90)  # 流动高光

        # ---- 猫娘素材（加载失败就退回用 emoji，程序不会崩）----
        self._pix_run = []
        self._pix_turn = None
        self._xhangge_load_catgirl()

        # ---- 动画定时器：20 帧/秒 ----
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._xhangge_tick)

    # ============================================================
    # 素材加载
    # ============================================================
    def _xhangge_load_catgirl(self):
        """把猫娘跑步和回头的图读进来，缩到进度条高度。

        素材不存在时静默跳过，绘制时会自动改用 🐱 emoji 兜底，
        保证即使 assets 目录被删了程序也照样能跑。
        """
        target_h = max(18, self.height() - 6)
        for name in xhangge_config.XHANGGE_CATGIRL_RUN:
            p = xhangge_config.xhangge_catgirl_path(name)
            if p is not None:
                pix = QPixmap(str(p))
                if not pix.isNull():
                    self._pix_run.append(
                        pix.scaledToHeight(
                            target_h, Qt.TransformationMode.SmoothTransformation
                        )
                    )
        p = xhangge_config.xhangge_catgirl_path(xhangge_config.XHANGGE_CATGIRL_TURN)
        if p is not None:
            pix = QPixmap(str(p))
            if not pix.isNull():
                self._pix_turn = pix.scaledToHeight(
                    target_h, Qt.TransformationMode.SmoothTransformation
                )

    def xhangge_apply_theme(self, theme_key):
        """跟随软件主题换配色（粉/亮/暗三套）。"""
        if theme_key == "dark":
            self._c_track = QColor("#3A3339")
            self._c_fill_a = QColor("#D9709A")
            self._c_fill_b = QColor("#B85C7E")
            self._c_text = QColor("#E8C7D4")
            self._c_shine = QColor(255, 255, 255, 55)
        elif theme_key == "light":
            self._c_track = QColor("#EDEDED")
            self._c_fill_a = QColor("#FFAFCC")
            self._c_fill_b = QColor("#FF8FB4")
            self._c_text = QColor("#7A6670")
            self._c_shine = QColor(255, 255, 255, 100)
        else:  # pink
            self._c_track = QColor("#FFE4EF")
            self._c_fill_a = QColor("#FF9EC4")
            self._c_fill_b = QColor("#FF7BAC")
            self._c_text = QColor("#B85C7E")
            self._c_shine = QColor(255, 255, 255, 90)
        self.update()

    # ============================================================
    # 对外接口
    # ============================================================
    def xhangge_set_progress(self, percent, label=""):
        """设成"确定进度"模式。

        参数 percent 传 -1 会自动切到不确定模式——
        这样服务层可以统一发一个信号，不用自己判断该调哪个方法。
        """
        if percent is None or percent < 0:
            self.xhangge_set_indeterminate(label)
            return
        self._indeterminate = False
        self._percent = max(0, min(100, int(percent)))
        if label:
            self._label = label
        self.setVisible(True)
        self._xhangge_ensure_timer()
        self.update()

    def xhangge_set_indeterminate(self, label=""):
        """设成"不确定进度"模式：猫娘在槽里左右跑。"""
        self._indeterminate = True
        if label:
            self._label = label
        self.setVisible(True)
        self._xhangge_ensure_timer()
        self.update()

    def xhangge_set_label(self, label):
        """只改文字，不动进度。"""
        self._label = label
        self.update()

    def xhangge_reset(self):
        """复位并隐藏（任务结束时调用），同时停掉定时器省 CPU。"""
        self._timer.stop()
        self._percent = 0
        self._label = ""
        self._indeterminate = False
        self._phase = 0.0
        self._runner_x = 0.0
        self._runner_dir = 1
        self.setVisible(False)

    # ============================================================
    # 动画驱动
    # ============================================================
    def _xhangge_ensure_timer(self):
        """需要动的时候才开定时器（已经在跑就不重复开）。"""
        if not self._timer.isActive():
            self._timer.start()

    def _xhangge_tick(self):
        """每帧推进一次动画状态。"""
        # 相位持续增长，驱动高光流动和文字呼吸
        self._phase += 0.12

        if self._indeterminate:
            # 猫娘左右跑：位置按方向前进，撞到边缘就转身
            self._runner_x += self._runner_dir * 0.011
            if self._runner_x >= 1.0:
                self._runner_x = 1.0
                self._runner_dir = -1
                self._turning = 8      # 转身动画持续 8 帧
            elif self._runner_x <= 0.0:
                self._runner_x = 0.0
                self._runner_dir = 1
                self._turning = 8
            if self._turning > 0:
                self._turning -= 1
            else:
                # 每 4 帧换一张跑步图，形成迈步的感觉
                if int(self._phase * 2) % 2 == 0:
                    self._runner_frame = (self._runner_frame + 1) % max(
                        1, len(self._pix_run)
                    )
        self.update()

    def hideEvent(self, event):
        """控件被隐藏时停掉定时器，不浪费 CPU。"""
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """重新显示时把定时器开回来。"""
        super().showEvent(event)
        self._xhangge_ensure_timer()

    # ============================================================
    # 绘制
    # ============================================================
    def paintEvent(self, event):
        """自己画整个进度条。

        画的顺序（后画的盖在前面画的上面）：
        1. 圆角底槽
        2. 粉色渐变填充（按百分比决定宽度）
        3. 流动的高光斜纹
        4. 🐾 猫爪 或 猫娘立绘
        5. 右侧文字
        """
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        # 右侧留出空间写文字
        text_w = 200 if self._label else 0
        bar_w = max(60, w - text_w - 8)
        bar_h = 14
        bar_y = (h - bar_h) / 2
        radius = bar_h / 2

        # ---- 1. 底槽 ----
        track = QRectF(0, bar_y, bar_w, bar_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._c_track)
        p.drawRoundedRect(track, radius, radius)

        # 用底槽形状做裁剪区，这样填充和高光都不会画出圆角外面
        clip = QPainterPath()
        clip.addRoundedRect(track, radius, radius)
        p.save()
        p.setClipPath(clip)

        if self._indeterminate:
            # 不确定模式：不画来回滑动的"高亮块"了，改成只有雪花喵在槽里跑步，
            # 更可爱、更直观（原来的高亮块看着像个"圈"，观感不好喵）
            pass
        else:
            # ---- 确定模式：按百分比填充 ----
            fill_w = bar_w * self._percent / 100.0
            if fill_w > 0:
                grad = QLinearGradient(0, 0, fill_w, 0)
                grad.setColorAt(0.0, self._c_fill_a)
                grad.setColorAt(1.0, self._c_fill_b)
                p.setBrush(grad)
                p.drawRect(QRectF(0, bar_y, fill_w, bar_h))

                # ---- 3. 流动高光斜纹（糖果条效果）----
                # 让斜纹随相位向右滚动，制造"正在动"的感觉
                p.setPen(QPen(self._c_shine, 6))
                stripe_gap = 18
                offset = (self._phase * 14) % stripe_gap
                x = -bar_h + offset
                while x < fill_w:
                    p.drawLine(int(x), int(bar_y + bar_h),
                               int(x + bar_h), int(bar_y))
                    x += stripe_gap
        p.restore()

        # ---- 4. 猫爪 / 猫娘 ----
        if self._indeterminate:
            self._xhangge_draw_runner(p, bar_w, bar_h, bar_y)
        else:
            self._xhangge_draw_paw(p, bar_w, bar_h, bar_y)

        # ---- 5. 文字（带呼吸式明暗）----
        if self._label:
            # 用正弦波让透明度在 165~255 之间来回变化，像在呼吸
            alpha = int(210 + 45 * math.sin(self._phase * 0.9))
            c = QColor(self._c_text)
            c.setAlpha(max(150, min(255, alpha)))
            p.setPen(c)
            f = QFont()
            f.setPointSize(11)
            p.setFont(f)
            # 不确定模式下在文字后面加会动的省略号
            text = self._label
            if self._indeterminate:
                dots = "…" * (1 + int(self._phase) % 3)
                text = f"{text} {dots}"
            p.drawText(
                QRectF(bar_w + 8, 0, w - bar_w - 8, h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )

    def _xhangge_draw_paw(self, p, bar_w, bar_h, bar_y):
        """画跟在进度头部的 🐾 猫爪，带轻微上下跳动。"""
        x = bar_w * self._percent / 100.0
        # 正弦波做 2px 幅度的轻跳，像小猫踩着进度往前走
        bounce = math.sin(self._phase * 2.2) * 2.0
        f = QFont()
        f.setPointSize(13)
        p.setFont(f)
        p.setPen(self._c_fill_b)
        p.drawText(
            QRectF(x - 10, bar_y - 9 + bounce, 22, bar_h + 18),
            Qt.AlignmentFlag.AlignCenter,
            "🐾",
        )

    def _xhangge_draw_runner(self, p, bar_w, bar_h, bar_y):
        """画在槽里左右跑的猫娘。

        素材加载失败时退回画 🐱 emoji，保证功能不缺失。
        """
        pix = None
        if self._turning > 0 and self._pix_turn is not None:
            pix = self._pix_turn
        elif self._pix_run:
            pix = self._pix_run[self._runner_frame % len(self._pix_run)]

        if pix is None:
            # 兜底：素材没了就用 emoji
            x = self._runner_x * (bar_w - 20)
            f = QFont()
            f.setPointSize(14)
            p.setFont(f)
            p.setPen(self._c_fill_b)
            p.drawText(
                QRectF(x, 0, 24, self.height()),
                Qt.AlignmentFlag.AlignCenter,
                "🐱",
            )
            return

        pw = pix.width()
        x = self._runner_x * max(1, bar_w - pw)
        y = (self.height() - pix.height()) / 2
        # 向左跑时把图水平翻转，让她真的"转过身"
        if self._runner_dir < 0 and self._turning <= 0:
            p.save()
            p.translate(x + pw, y)
            p.scale(-1, 1)
            p.drawPixmap(0, 0, pix)
            p.restore()
        else:
            p.drawPixmap(int(x), int(y), pix)
