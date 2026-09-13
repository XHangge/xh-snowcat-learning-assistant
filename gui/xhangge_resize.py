# Author: xhangge
# This project is created by xhangge
"""
xhangge_resize —— 无边框窗口的"鼠标拖边缘调整大小"助手

为什么需要它：
软件所有窗口都是无边框（FramelessWindowHint）——为了圆角可爱风，
去掉了系统自带的边框，也就失去了系统提供的"拖边缘改变大小"能力。
之前只在右下角放了一个 16×16 的 QSizeGrip，而且 QSS 里是透明的，
用户根本看不见、抓不到，等于没法调大小。

这个助手把"调整大小"做成全局事件过滤：
鼠标只要靠近窗口任意一条边或一个角（6 像素以内），
光标就变成对应的拉伸箭头，按住左键拖动即可改变窗口大小，
松开即停。窗口缩放时 Qt 的布局会自动跟着重排，不用额外处理。
"""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication

from gui.xhangge_avatars import xhangge_resize_cursor

# 距离窗口边缘多少像素内算"进入调整大小区域"
_RESIZE_MARGIN = 6


class XhanggeResizeHelper(QObject):
    """给一个无边框窗口装上边缘调整大小。

    用法（在窗口 __init__ 里）：
        self._resize_helper = XhanggeResizeHelper(self)
    """

    def __init__(self, window):
        super().__init__(window)  # 挂在窗口下面，窗口销毁时自动跟着销毁
        self._window = window
        self._dir = None              # 正在调整的方向（None = 没在调）
        self._hover_dir = None        # 鼠标当前悬停在哪个边缘
        self._override_active = False  # 当前是否设了 override 光标
        self._origin_global = None    # 按下时鼠标的全局坐标
        self._origin_geometry = None  # 按下时窗口的几何（位置+大小）
        QApplication.instance().installEventFilter(self)

    # ---- 判断一个全局坐标落在窗口哪条边/角 ----
    def _edge_at(self, pos):
        g = self._window.frameGeometry()
        m = _RESIZE_MARGIN
        left = pos.x() <= g.left() + m
        right = pos.x() >= g.right() - m
        top = pos.y() <= g.top() + m
        bottom = pos.y() >= g.bottom() - m
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bottom and left:
            return "bl"
        if bottom and right:
            return "br"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    @staticmethod
    def _cursor_for(direction):
        return xhangge_resize_cursor(direction) if direction else None

    def _update_edge_cursor(self, direction):
        """更新边缘光标（direction=None 表示恢复默认）。

        关键：先恢复旧的、再设新的，避免 setOverrideCursor 堆叠——
        堆叠会导致切到别的软件再回来时光标卡住/失效。
        """
        if direction == self._hover_dir:
            return
        self._hover_dir = direction
        if self._override_active:
            QApplication.restoreOverrideCursor()
            self._override_active = False
        if direction is not None:
            QApplication.setOverrideCursor(self._cursor_for(direction))
            self._override_active = True

    def _clear_edge_cursor(self):
        """彻底清掉 override 光标（鼠标离开 / 失焦时用）。"""
        if self._override_active:
            QApplication.restoreOverrideCursor()
            self._override_active = False
        self._hover_dir = None

    def _do_resize(self, pos):
        """按鼠标移动量调整窗口几何，同时受最小尺寸约束。"""
        d = self._dir
        delta = pos - self._origin_global
        g = self._origin_geometry
        x, y, w, h = g.x(), g.y(), g.width(), g.height()

        if "left" in d:
            x = g.x() + delta.x()
            w = g.width() - delta.x()
        if "right" in d:
            w = g.width() + delta.x()
        if "top" in d:
            y = g.y() + delta.y()
            h = g.height() - delta.y()
        if "bottom" in d:
            h = g.height() + delta.y()

        w = max(w, self._window.minimumWidth())
        h = max(h, self._window.minimumHeight())
        self._window.setGeometry(x, y, w, h)

    def eventFilter(self, watched, event):
        # 窗口可能已经在程序退出时被销毁（C++ 对象没了），
        # 这里兜住，避免退出时打一堆 RuntimeError。
        try:
            if (
                self._window.isMaximized()
                or not self._window.isVisible()
                or not self._window.isActiveWindow()
            ):
                # 不是活动窗口（比如别的模态窗盖在上面）：清掉残留 override 并跳过，
                # 否则多个窗口的 resize helper 会互相打架、抢 override 光标，
                # 导致盖在上面的窗口按钮光标/点击异常。
                self._clear_edge_cursor()
                return super().eventFilter(watched, event)
        except RuntimeError:
            return super().eventFilter(watched, event)

        t = event.type()
        if t == QEvent.Type.MouseMove:
            pos = event.globalPosition().toPoint()
            if self._dir is not None:
                # 正在拖拽调整大小
                self._do_resize(pos)
                return True
            # 没在拖：按鼠标所在边缘更新光标样式
            self._update_edge_cursor(self._edge_at(pos))
        elif t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            direction = self._edge_at(event.globalPosition().toPoint())
            if direction is not None:
                self._dir = direction
                self._origin_global = event.globalPosition().toPoint()
                self._origin_geometry = self._window.geometry()
                return True
        elif t == QEvent.Type.MouseButtonRelease:
            if self._dir is not None:
                self._dir = None
                self._clear_edge_cursor()
                return True
        elif t == QEvent.Type.ApplicationDeactivate:
            # 切到别的软件：清掉 override 光标，避免回来时卡住/失效
            self._clear_edge_cursor()
        return super().eventFilter(watched, event)
