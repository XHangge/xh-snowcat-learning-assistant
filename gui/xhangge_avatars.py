# Author: xhangge
# This project is created by xhangge
"""
xhangge_avatars —— 头像工具箱（圆形头像的加载、制作、保存）

这个项目里所有"头像"都是圆形的：
- 雪花喵（猫娘）：assets/xhangge_catgirl/avatar.png（本来就是圆形的图）
- 用户：默认显示 🐶 emoji；上传照片后变成圆形头像，
  存在 ~/.xh_snowcat/xhangge_user_avatar.png

规则（和用户确认过的）：
- 图标位一律用真图片；只有图片缺失/加载失败才退回 emoji（🐱 / 🐶）
- 用户上传的图不管什么形状，都会"居中裁成方形 → 套圆形蒙版"再保存

分层：这个文件是纯工具（只管图片），不碰数据库不碰界面逻辑。
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBitmap, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel

from config import xhangge_settings as xhangge_config

# 用户头像保存尺寸（256 够各种显示大小用，也不会让文件太大）
_XHANGGE_AVATAR_SAVE_SIZE = 256


def _xhangge_circle_pixmap(src, size):
    """把一张图变成"居中裁方形 + 圆形蒙版"的圆形 QPixmap。

    参数：
        src  —— 原图（QPixmap）
        size —— 输出尺寸（正方形边长）
    """
    # 1) 等比缩放到"刚好盖住 size×size"（KeepAspectRatioByExpanding：
    #    保持比例放大到短边=size），然后居中裁掉多余部分
    scaled = src.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)

    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)  # 先铺透明底
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(0, 0, scaled, x, y, size, size)
    painter.end()

    # 2) 画一个圆形蒙版：蒙版里白色(color1)的部分保留、黑色(color0)的挖掉
    #    踩过的坑：QPainter 默认的画刷是黑的——圆会被填成黑色，
    #    整个蒙版全黑 = 整张图全透明，头像就"隐形"了喵。
    #    所以必须明确把画刷设成白色(color1)、关掉描边。
    mask = QBitmap(size, size)
    mask.fill(Qt.GlobalColor.color0)  # 全黑 = 先全部挖掉
    mask_painter = QPainter(mask)
    mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    mask_painter.setPen(Qt.PenStyle.NoPen)          # 不要描边
    mask_painter.setBrush(Qt.GlobalColor.color1)    # 白色填充 = 圆内保留
    mask_painter.drawEllipse(0, 0, size, size)
    mask_painter.end()
    out.setMask(mask)
    return out


def xhangge_catgirl_pixmap(size):
    """雪花喵的圆形头像。加载失败返回 None（调用方退回 🐱 emoji）。"""
    path = xhangge_config.xhangge_catgirl_path(
        xhangge_config.XHANGGE_CATGIRL_AVATAR
    )
    if path is None:
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    # avatar.png 本来就是圆形的，再套一次蒙版也无害（双保险）
    return _xhangge_circle_pixmap(pm, size)


def xhangge_user_pixmap(size):
    """用户的圆形头像。没上传过 / 加载失败返回 None（退回 🐶）。"""
    path = xhangge_config.XHANGGE_USER_AVATAR
    if not path.exists():
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    return _xhangge_circle_pixmap(pm, size)


def _xhangge_make_label(pixmap_getter, size, fallback_text):
    """造一个头像 QLabel：有图显示图，没图显示 emoji 兜底。"""
    label = QLabel()
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setObjectName("AvatarLabel")
    pm = pixmap_getter(size)
    if pm is not None:
        label.setPixmap(pm)
    else:
        # 图片加载异常 → emoji 兜底（AvatarLabel 的 QSS 会给它大字号）
        label.setText(fallback_text)
    return label


def xhangge_catgirl_label(size, fallback_text="🐱"):
    """雪花喵头像标签（图标位一律用它替换 🐱 emoji）。"""
    return _xhangge_make_label(xhangge_catgirl_pixmap, size, fallback_text)


def xhangge_user_label(size, fallback_text="🐶"):
    """用户头像标签（聊天气泡右侧；默认 🐶，上传后变照片）。"""
    return _xhangge_make_label(xhangge_user_pixmap, size, fallback_text)


def xhangge_save_user_avatar(source_path):
    """把用户选的照片加工成圆形头像并保存。

    加工步骤：加载 → 居中裁方形 → 缩到 256 → 圆形蒙版 → 存 PNG。
    返回 True = 成功；False = 文件读不了（格式不支持/损坏）。
    """
    img = QImage(str(source_path))
    if img.isNull():
        return False
    # 居中裁方形（原图可能是长方形，取中间最大正方形）
    side = min(img.width(), img.height())
    x = (img.width() - side) // 2
    y = (img.height() - side) // 2
    square = img.copy(x, y, side, side)
    # 缩放到保存尺寸再套圆形
    base = QPixmap.fromImage(square).scaled(
        _XHANGGE_AVATAR_SAVE_SIZE, _XHANGGE_AVATAR_SAVE_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    circular = _xhangge_circle_pixmap(base, _XHANGGE_AVATAR_SAVE_SIZE)
    xhangge_config.XHANGGE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return circular.save(str(xhangge_config.XHANGGE_USER_AVATAR), "PNG")


def xhangge_clear_user_avatar():
    """删掉用户头像（"恢复默认"按钮用，之后气泡回到 🐶）。"""
    try:
        xhangge_config.XHANGGE_USER_AVATAR.unlink(missing_ok=True)
        return True
    except OSError:
        return False


# ============================================================
# 粉色鼠标指针（猫爪 / 小手 / I 型）
# ============================================================
# 光标目标尺寸（逻辑像素）：48×48 原图缩到这个大小，和标准光标差不多
_XHANGGE_CURSOR_SIZE = 24

_xhangge_paw_cursor = None
_xhangge_hand_cursor = None
_xhangge_ibeam_cursor = None


def _xhangge_make_cursor(filename, hot_x, hot_y):
    """加载一张光标图，缩到统一尺寸，做成 QCursor。失败返回 None。

    hot_x / hot_y 是 48×48 原图坐标下的热点，这里按缩放比例换算。
    """
    from PySide6.QtGui import QCursor, QPixmap

    path = xhangge_config.XHANGGE_CATGIRL_DIR.parent / filename
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    pm = pm.scaled(
        _XHANGGE_CURSOR_SIZE,
        _XHANGGE_CURSOR_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    scale = pm.width() / 48.0
    return QCursor(pm, int(hot_x * scale), int(hot_y * scale))


def xhangge_paw_cursor():
    """粉色猫爪光标（缓存复用）。热点在中上脚趾尖。"""
    global _xhangge_paw_cursor
    if _xhangge_paw_cursor is None:
        _xhangge_paw_cursor = _xhangge_make_cursor("xhangge_cursor_paw.png", 24, 7)
    return _xhangge_paw_cursor


def xhangge_hand_cursor():
    """粉色小手光标（缓存复用）。热点在食指尖。"""
    global _xhangge_hand_cursor
    if _xhangge_hand_cursor is None:
        _xhangge_hand_cursor = _xhangge_make_cursor("xhangge_cursor_hand.png", 36, 4)
    return _xhangge_hand_cursor


def xhangge_ibeam_cursor():
    """粉色 I 型光标（缓存复用）。热点在竖条中心。"""
    global _xhangge_ibeam_cursor
    if _xhangge_ibeam_cursor is None:
        _xhangge_ibeam_cursor = _xhangge_make_cursor("xhangge_cursor_ibeam.png", 24, 24)
    return _xhangge_ibeam_cursor


# 粉色窗口调整大小光标（双向箭头），按方向缓存
_xhangge_resize_cursors = {}
_XHANGGE_RESIZE_FILES = {
    "left": "xhangge_cursor_resize_h.png",
    "right": "xhangge_cursor_resize_h.png",
    "top": "xhangge_cursor_resize_v.png",
    "bottom": "xhangge_cursor_resize_v.png",
    "tl": "xhangge_cursor_resize_d1.png",
    "br": "xhangge_cursor_resize_d1.png",
    "tr": "xhangge_cursor_resize_d2.png",
    "bl": "xhangge_cursor_resize_d2.png",
}


def xhangge_resize_cursor(direction):
    """返回某个方向的粉色双向箭头光标（缓存复用）。热点在中心。"""
    global _xhangge_resize_cursors
    if direction not in _xhangge_resize_cursors:
        _xhangge_resize_cursors[direction] = _xhangge_make_cursor(
            _XHANGGE_RESIZE_FILES[direction], 24, 24
        )
    return _xhangge_resize_cursors[direction]


def xhangge_apply_paw_cursor(widget):
    """给一个顶层窗口设上猫爪光标（图片缺失时静默跳过）。

    子控件（输入框、按钮）自己带的光标优先级更高，不会被覆盖——
    打字时还是 I 型、点按钮时还是小手喵。
    """
    cursor = xhangge_paw_cursor()
    if cursor is not None:
        widget.setCursor(cursor)
