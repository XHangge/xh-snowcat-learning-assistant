# Author: xhangge
# This project is created by xhangge
"""
main —— 程序入口（整个软件从这里的 main() 开始运行）
启动流程（带 splash 的版本）：
1. 只做最少量的事：创建 Qt 应用 + 字体图标 + **立刻弹出启动画面**
   （雪花喵大头像 + snowcat～ 艺术字，悬浮在屏幕中央）
2. 趁 splash 露脸的这几百毫秒，才去导入主窗口、主题这些"重家伙"
3. 主窗口一切就绪、即将登场的前一瞬间，splash 消失
4. 弹出 star 弹窗 → 检查 Ollama 状态
5. 进入事件循环（程序开始响应鼠标键盘，直到用户关闭窗口）

运行方式（开发时，菜单栏/Dock 会显示 snowcat 喵）：
    open snowcat.app
或直接：
    .venv/bin/python main.py

为什么导入顺序这么讲究：
import 是要花时间的（Qt 界面模块加载约半秒）。
以前它们写在文件顶部，程序启动的头半秒"一片漆黑什么都没有"；
现在先弹 splash 再导入，用户双击的第一帧就有画面了喵。
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from config import xhangge_settings as xhangge_config
from gui.xhangge_splash import XhanggeSplash


def main():
    """软件主函数：一切从这里开始。"""
    # ---- 1. 创建 Qt 应用（界面的一切都要踩着它）----
    app = QApplication(sys.argv)
    app.setApplicationName(xhangge_config.APP_NAME)
    app.setOrganizationName(xhangge_config.APP_AUTHOR)

    # ---- 2. 字体和图标（轻量，立刻能做）----
    # 按操作系统自动挑选好看的中文字体（Mac 苹方 / Windows 微软雅黑）
    font = QFont()
    font.setFamilies(xhangge_config.get_font_families())
    font.setPointSize(13)
    app.setFont(font)

    # 应用图标：任务栏/系统标题栏用雪花喵头像（Windows 用 .ico 更清晰）
    assets_dir = Path(__file__).resolve().parent / "assets" / "xhangge_catgirl"
    icon_path = (
        assets_dir / "avatar.ico"
        if sys.platform == "win32"
        else assets_dir / "avatar.png"
    )
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Windows：给进程设一个独立的 AppUserModelID，任务栏才会显示上面的自定义图标
    # （否则任务栏会按宿主进程 pythonw.exe 显示 Python 图标，而不是窗口图标）
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "snowcat.learning.assistant"
        )

    # ---- 3. 启动画面第一时间弹出（用户双击后的第一帧就有它）----
    splash = XhanggeSplash()
    splash.show()
    # processEvents：马上把手头攒着的事件处理掉（包括"画 splash"），
    # 不然它要等下面这一大段 import 全跑完才被画出来，就白做了
    app.processEvents()

    # ---- 4. 重量级导入：趁 splash 露脸时才加载 ----
    # （写在函数里而不是文件顶部，就是为了这一步喵）
    from gui.xhangge_main_window import XhanggeMainWindow
    from gui.xhangge_themes import XHANGGE_THEMES

    # 先把所有数据目录建好（~/.xh_snowcat/ 及下面的向量库、文件副本目录）
    xhangge_config.xhangge_ensure_dirs()
    settings = xhangge_config.load_xhangge_settings()

    # 启动时后台探测一次 Ollama + 当前本地模型状态，结果缓存，
    # 设置窗打开时直接读缓存、不再重复跑脚本（只在切换模型时再探测一次）。
    from services.xhangge_ollama_deploy import XhanggeLocalStatusWorker

    _startup_status_worker = XhanggeLocalStatusWorker(
        settings.get("local_model", xhangge_config.XHANGGE_MODEL_NAME)
    )
    _startup_status_worker.start()

    window = XhanggeMainWindow(settings)

    # 先应用用户上次选的主题（给整个应用"换皮肤"）
    theme_key = settings.get("theme", "pink")
    app.setStyleSheet(
        XHANGGE_THEMES.get(theme_key, XHANGGE_THEMES["pink"])
    )

    # ---- 5. 主窗口即将登场：splash 瞬间消失 ----
    splash.close()
    splash.deleteLater()
    window.show()

    # ---- 6. 启动弹窗 + Ollama 状态检查（在主窗口画完之后才弹）----
    # singleShot(150, ...) = 延迟 150 毫秒再执行，
    # 让主窗口先完整画出来，弹窗再登场，观感更好
    QTimer.singleShot(150, lambda: xhangge_startup_checks(window))

    # ---- 7. 事件循环：程序在这里持续运行，直到窗口被关闭 ----
    sys.exit(app.exec())


def xhangge_startup_checks(window):
    """启动检查：先弹 star 弹窗，再检查 Ollama 服务和模型是否就绪。"""
    # 这些导入放在函数里：等主窗口都显示了才加载，不拖慢启动
    from gui.xhangge_dialogs import show_star_dialog, show_warning_dialog
    from services.xhangge_chat_service import check_ollama_status

    # 需求：每次打开软件弹出"支持xhangge请帮忙点个star喵 🌟"
    show_star_dialog(window)

    # 用户如果已经切到在线 API，本地 Ollama 装没装都无所谓，
    # 这时候还弹"连不上 Ollama"就是纯打扰了，直接跳过检查。
    if window.db.xhangge_get_active_model_config() is not None:
        return

    # 检查本地 Ollama 服务（连不上就提前告诉用户，别等到发消息才报错）
    # 用户在设置里选了哪个本地模型，就检查那一个，不是永远检查默认的那个。
    local_model = window.xhangge_all_settings.get(
        "local_model", xhangge_config.XHANGGE_MODEL_NAME
    )
    alive, model_ready = check_ollama_status(model=local_model)
    if not alive:
        show_warning_dialog(
            window,
            "连不上 Ollama 喵呜呜 😿",
            "雪花喵找不到本地的大模型服务喵！\n\n"
            "请确认：\n"
            "1. Ollama 已经启动（终端里运行：ollama serve）\n"
            "2. 服务地址正确：" + xhangge_config.OLLAMA_BASE_URL + "\n\n"
            "如果你想用在线 API，点标题栏的 ⚙️ 去设置里切换就行喵～",
        )
    elif not model_ready:
        show_warning_dialog(
            window,
            "模型还没下载喵 😿",
            "Ollama 在运行，但还没有找到模型「" + local_model + "」喵。\n\n"
            "点标题栏的 ⚙️ → 🧠 模型喵 → 「⬇️ 一键下载喵」就能装好，\n"
            "也可以自己在终端里运行：\n"
            "ollama pull " + local_model,
        )


def xhangge_selftest():
    """自检模式：导入所有重家伙（含原生模块 pydantic_core 等），打印结果退出。

    用途：验证"从 Finder 双击启动"和"从终端启动"行为是否一致
    （macOS 的库验证只在 LaunchServices 启动链路上拦截不同团队签名的
    原生库，终端启动会绕过——所以要用这个在两种环境下分别测喵）。
    """
    results = []
    try:
        import pydantic_core  # noqa: F401
        results.append("pydantic_core ok")
    except Exception as e:
        results.append(f"pydantic_core FAIL: {e}")
    try:
        from services.xhangge_llm_router import _xhangge_build_llm  # noqa: F401
        results.append("llm_router ok")
    except Exception as e:
        results.append(f"llm_router FAIL: {e}")
    line = "SELFTEST: " + "; ".join(results)
    print(line, flush=True)
    # 从 Finder 双击启动时 stdout 会丢，所以同时写一份到文件里
    try:
        from datetime import datetime

        log = xhangge_config.XHANGGE_DATA_DIR / "xhangge_selftest.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {line}\n")
    except OSError:
        pass
    return 0 if all("ok" in r for r in results) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(xhangge_selftest())
    main()
