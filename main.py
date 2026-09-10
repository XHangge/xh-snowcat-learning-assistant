# Author: xhangge
# This project is created by xhangge miao
"""
main —— 程序入口（整个软件从这里的 main() 开始运行）
启动流程：
1. 创建 Qt 应用（Qt 应用是一切界面的"地基"）
2. 设置字体（按系统自动选合适的中文字体）和图标
3. 读取用户设置 → 创建并显示主窗口
4. 弹出启动弹窗（请大家点 star 喵）→ 检查 Ollama 服务状态
5. 进入事件循环（程序开始响应鼠标键盘，直到用户关闭窗口）

运行方式：在项目目录执行  python main.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from core import xhangge_config
from core.ollama_client import check_ollama_status
from ui.dialogs import show_star_dialog, show_warning_dialog
from ui.main_window import XhanggeMainWindow
from ui.themes import XHANGGE_THEMES


def main():
    """软件主函数：一切从这里开始。"""
    # ---- 1. 创建 Qt 应用 ----
    app = QApplication(sys.argv)
    app.setApplicationName(xhangge_config.APP_NAME)
    app.setOrganizationName(xhangge_config.APP_AUTHOR)

    # ---- 2. 全局字体和图标 ----
    # 按操作系统自动挑选好看的中文字体（Mac 苹方 / Windows 微软雅黑）
    font = QFont()
    font.setFamilies(xhangge_config.get_font_families())
    font.setPointSize(13)
    app.setFont(font)

    # 应用图标：assets/icon.png 是预留的图标位置，
    # 想换成自己的图片，直接用同名文件替换它就行喵
    icon_path = Path(__file__).resolve().parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # ---- 3. 读取用户设置 → 创建主窗口 ----
    settings = xhangge_config.load_xhangge_settings()
    window = XhanggeMainWindow(settings)

    # 先应用用户上次选的主题（给整个应用"换皮肤"），再显示窗口
    theme_key = settings.get("theme", "pink")
    app.setStyleSheet(
        XHANGGE_THEMES.get(theme_key, XHANGGE_THEMES["pink"])
    )
    window.show()

    # ---- 4. 启动弹窗 + Ollama 状态检查 ----
    # singleShot(150, ...) = 延迟 150 毫秒再执行，
    # 让主窗口先完整画出来，弹窗再登场，观感更好
    QTimer.singleShot(150, lambda: xhangge_startup_checks(window))

    # ---- 5. 事件循环：程序在这里持续运行，直到窗口被关闭 ----
    sys.exit(app.exec())


def xhangge_startup_checks(window):
    """启动检查：先弹 star 弹窗，再检查 Ollama 服务和模型是否就绪。"""
    # 需求：每次打开软件弹出"支持xhangge请帮忙点个star喵 🌟"
    show_star_dialog(window)

    # 检查本地 Ollama 服务（连不上就提前告诉用户，别等到发消息才报错）
    alive, model_ready = check_ollama_status()
    if not alive:
        show_warning_dialog(
            window,
            "连不上 Ollama 喵呜呜 😿",
            "雪花喵找不到本地的大模型服务喵！\n\n"
            "请确认：\n"
            "1. Ollama 已经启动（终端里运行：ollama serve）\n"
            "2. 服务地址正确：" + xhangge_config.OLLAMA_BASE_URL,
        )
    elif not model_ready:
        show_warning_dialog(
            window,
            "模型还没下载喵 😿",
            "Ollama 在运行，但还没有找到模型「"
            + xhangge_config.XHANGGE_MODEL_NAME + "」喵。\n\n"
            "请在终端里运行：\n"
            "ollama pull " + xhangge_config.XHANGGE_MODEL_NAME,
        )


if __name__ == "__main__":
    main()
