# Author: xhangge
# This project is created by xhangge
"""
xhangge_ollama_deploy —— 一键部署本地模型

功能：在软件里点一个按钮，就能把大模型下载到本地，
不用让用户自己开终端敲 `ollama pull qwen2.5:7b`。

【怎么实现的】
底层就是调用 Ollama 的命令行工具：
    ollama pull qwen2.5:7b
用 Python 的 subprocess 启动这个命令，然后一行一行读它打印的输出，
从里面把下载进度（百分比）解析出来，通过 Qt 信号发给界面的进度条。

【为什么必须放在后台线程（QThread）】
下载一个模型要好几分钟。如果在界面线程里等，整个窗口会卡死成"白屏无响应"。
放到后台线程后，界面照样能拖动、能聊天，进度条实时跳动。

【安全说明】
调用命令时用的是"参数数组"形式 ["ollama", "pull", 模型名]，
而不是把命令拼成一个字符串交给 shell 执行。
这样即使模型名里包含特殊字符，也不会被当成命令执行（防命令注入）。
"""

import re
import shutil
import subprocess

import requests
from PySide6.QtCore import QThread, Signal

from config import xhangge_settings as xhangge_config


def xhangge_find_ollama():
    """找到 ollama 命令在哪儿。

    为什么要找：从 .app / 快捷方式双击启动时，程序拿到的 PATH 环境变量
    和你在终端里的不一样，直接调 "ollama" 会报 FileNotFoundError。
    所以先用 shutil.which 找，找不到就去几个常见安装位置碰运气。

    返回 ollama 可执行文件的完整路径，实在找不到返回 None。
    """
    import os
    import sys

    found = shutil.which("ollama")
    if found:
        return found

    # Windows 上还要试一下带扩展名的命令名（有些安装不会往 PATH 注册裸 `ollama`）
    if sys.platform == "win32":
        for name in ("ollama.exe", "ollama.bat", "ollama.cmd"):
            found = shutil.which(name)
            if found:
                return found

    # 常见安装位置（macOS / Linux / Windows 各来一份）
    home = os.path.expanduser("~")
    candidates = (
        # macOS / Linux
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
        "/usr/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
        # Windows（Ollama 默认装进用户目录的 Programs 下）
        os.path.join(home, "AppData", "Local", "Programs", "Ollama", "ollama.exe"),
        os.path.join(home, "AppData", "Local", "Programs", "Ollama", "ollama app.exe"),
        "C:/Program Files/Ollama/ollama.exe",
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def xhangge_list_installed_models():
    """查本地已经装了哪些模型（走 Ollama 的 HTTP 接口，不用命令行）。

    返回模型名列表，例如 ["qwen2.5:7b", "bge-m3:latest"]。
    连不上 Ollama 时返回空列表（而不是报错），
    让界面能平静地显示"一个都没有"。
    """
    try:
        r = requests.get(
            xhangge_config.OLLAMA_BASE_URL + "/api/tags",
            timeout=(3, 10),
        )
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError):
        return []


def xhangge_is_model_installed(model_name):
    """某个模型装了没有（三路探测：Ollama 已装 + 本地脚本 + local_model 文件夹）。

    要做前缀匹配，因为 Ollama 返回的名字可能带 :latest 后缀——
    用户选的是 "bge-m3"，而接口返回的是 "bge-m3:latest"，
    直接用等号比会误判成"没装"。
    """
    installed = xhangge_list_installed_models()
    for name in installed:
        if name == model_name:
            return True
        # "bge-m3:latest" 应该能匹配上用户输入的 "bge-m3"
        if name.split(":")[0] == model_name.split(":")[0]:
            if ":" not in model_name or name == model_name:
                return True
    # local_model 文件夹里的 gguf 也算"装了"：按模型基名模糊匹配文件名
    base = model_name.split(":")[0].lower()
    for gguf in xhangge_scan_local_models():
        stem = gguf[:-5].lower().replace("_", "").replace("-", "").replace(".", "")
        if base.replace(".", "") in stem:
            return True
    return False


# 状态缓存：启动时探测一次，设置窗直接读，别每次打开都跑 ollama -v + /api/tags
_xhangge_status_cache = None  # {"ollama_ok", "version", "models", "model_id"}


def xhangge_detect_status(model_id):
    """探测 Ollama + 已装模型并缓存。返回 (ollama_ok, version, models)。

    这是唯一的"真实探测"入口：启动时调用一次、切换模型时调用一次，
    设置窗只读缓存，不再重复跑脚本。
    """
    global _xhangge_status_cache
    ollama_ok, version = xhangge_detect_ollama()
    models = xhangge_list_installed_models() if ollama_ok else []
    _xhangge_status_cache = {
        "ollama_ok": ollama_ok,
        "version": version,
        "models": models,
        "model_id": model_id,
    }
    return ollama_ok, version, models


def xhangge_get_cached_status():
    """拿缓存的状态（可能为 None，表示还没探测过）。"""
    return _xhangge_status_cache


def xhangge_detect_ollama():
    """探测 Ollama 装没装、能不能用（实际跑一下 `ollama -v`）。

    比 shutil.which 更可靠——有的机器 PATH 里没有 ollama 但程序其实装了；
    也有"文件在但跑不起来"的情况。这里直接执行版本命令验证。
    返回 (装了吗, 版本号或 None)。
    """
    exe = xhangge_find_ollama()
    if exe is None:
        return False, None
    try:
        r = subprocess.run(
            [exe, "-v"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode == 0:
            line = (r.stdout or r.stderr or "").strip()
            return True, (line.splitlines()[0] if line else "已安装")
        return False, None
    except (OSError, subprocess.SubprocessError):
        return False, None


def xhangge_scan_local_models():
    """扫描本地手动下载的 gguf 模型（项目 local_model 文件夹 + 数据目录）。

    返回 gguf 文件名列表（如 ["qwen2.5-7b-instruct-q4_k_m.gguf"]）。
    只按扩展名识别，不做内容校验。
    """
    import os

    found = []
    for folder in (
        xhangge_config.XHANGGE_LOCAL_MODEL_DIR,
        xhangge_config.XHANGGE_DATA_DIR,
    ):
        try:
            for entry in os.scandir(folder):
                if entry.is_file() and entry.name.lower().endswith(".gguf"):
                    found.append(entry.name)
        except OSError:
            pass
    return found


class XhanggeOllamaPullWorker(QThread):
    """后台下载模型的工作线程。

    使用方式（由设置窗口调用）：
        worker = XhanggeOllamaPullWorker("qwen2.5:3b")
        worker.pull_progress.connect(进度条更新函数)
        worker.pull_finished.connect(下载结束的处理函数)
        worker.start()
    """

    # ---- 对外信号 ----
    # 进度更新（参数：百分比 0-100，给用户看的状态文字）
    # 百分比传 -1 表示"还不知道总量"，界面会切换成猫娘左右跑的不确定模式
    pull_progress = Signal(int, str)
    # 下载结束（参数：成功了吗，结果消息）
    pull_finished = Signal(bool, str)

    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.xhangge_model_name = model_name
        self._process = None        # subprocess 对象，取消时要杀掉它
        self._stop_requested = False

    def request_stop(self):
        """用户点了"取消下载"。

        这段在干什么：
        先做个标记，然后直接杀掉 ollama 进程。
        必须真的杀进程——光设标记没用，因为线程正卡在
        "读进程输出"这一行上等着，不杀它就永远等下去。
        """
        self._stop_requested = True
        if self._process is not None:
            try:
                self._process.terminate()   # 先礼貌地请它退出
            except Exception:
                pass

    def run(self):
        """线程主体：启动 ollama pull 并解析进度。"""
        exe = xhangge_find_ollama()
        if exe is None:
            self.pull_finished.emit(
                False,
                "找不到 Ollama 喵 😿\n\n"
                "请先去 https://ollama.com 下载安装 Ollama，\n"
                "安装好后重新打开雪花喵就行了喵～",
            )
            return

        try:
            # 用参数数组传命令，不经过 shell，避免命令注入
            self._process = subprocess.Popen(
                [exe, "pull", self.xhangge_model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,   # 把错误输出也合并进来一起读
                text=True,                  # 按文本模式读，省得自己解码
                bufsize=1,                  # 行缓冲，有一行就能读到一行
                encoding="utf-8",
                errors="replace",           # 遇到解不开的字符就替换，不要崩
            )
        except OSError as e:
            self.pull_finished.emit(False, f"启动下载失败喵 😿\n{e}")
            return

        self.pull_progress.emit(-1, "雪花喵正在联系模型仓库喵…")

        last_percent = -1
        try:
            # ollama pull 的输出会不断刷新进度行，逐行读出来解析
            for raw_line in self._process.stdout:
                if self._stop_requested:
                    break
                line = raw_line.strip()
                if not line:
                    continue

                percent, label = self._xhangge_parse_line(line)
                if percent is not None and percent != last_percent:
                    last_percent = percent
                    self.pull_progress.emit(percent, label)
                elif percent is None and label:
                    # 解析不出百分比（比如 "verifying sha256"），
                    # 就发 -1 让界面显示不确定进度 + 这句状态文字
                    self.pull_progress.emit(-1, label)
        except Exception as e:
            self.pull_finished.emit(False, f"下载过程中出错喵 😿\n{e}")
            return
        finally:
            # 等进程真正结束，拿到它的退出码
            try:
                self._process.wait(timeout=10)
            except Exception:
                pass

        if self._stop_requested:
            self.pull_finished.emit(False, "下载被取消了喵～")
            return

        code = self._process.returncode
        if code == 0:
            # 方案 C：ollama pull 返回 0 还不够，再核对一眼模型是不是真的
            # 出现在已安装列表里（避免"返回 0 但没落盘"的边界情况）。
            if xhangge_is_model_installed(self.xhangge_model_name):
                self.pull_progress.emit(100, "下载完成喵！")
                self.pull_finished.emit(
                    True,
                    f"模型「{self.xhangge_model_name}」已经装好啦喵 🎉\n"
                    "现在就可以在设置里选它来聊天了喵～",
                )
            else:
                self.pull_finished.emit(
                    False,
                    "下载好像没成功喵 😿\n\n"
                    "ollama pull 结束了，但模型没出现在已安装列表里。\n"
                    "可能是磁盘满了、或者下载到一半被中断，再试一次喵～",
                )
        else:
            self.pull_finished.emit(
                False,
                f"下载失败喵 😿（退出码 {code}）\n\n"
                "常见原因：\n"
                "1. 网络不通，或者模型仓库访问慢\n"
                "2. 模型名字打错了\n"
                "3. 磁盘空间不够了",
            )

    @staticmethod
    def _xhangge_parse_line(line):
        """从 ollama pull 的一行输出里解析出进度。

        ollama 的输出大致长这样：
            pulling manifest
            pulling 2bada8a74506... 45% ▕███████    ▏ 2.1 GB/4.7 GB
            verifying sha256 digest
            success

        返回 (百分比或None, 状态文字)。
        解析不出百分比时百分比返回 None，界面就显示不确定进度。
        """
        # 找 "45%" 这样的百分比
        m = re.search(r"(\d{1,3})\s*%", line)
        percent = None
        if m:
            percent = max(0, min(100, int(m.group(1))))

        # 找 "2.1 GB/4.7 GB" 这样的大小信息，拼进状态文字更直观
        size_m = re.search(
            r"([\d.]+\s*[KMGT]?B)\s*/\s*([\d.]+\s*[KMGT]?B)", line
        )

        low = line.lower()
        if "pulling manifest" in low:
            label = "正在读取模型信息喵…"
        elif "verifying" in low:
            label = "正在校验文件喵…"
        elif "writing" in low or "extracting" in low:
            label = "正在解包喵…"
        elif "success" in low:
            label = "下载完成喵！"
        elif "already exists" in low:
            label = "这个模型已经装过了喵～"
        elif percent is not None:
            if size_m:
                label = f"下载中喵 {size_m.group(1)} / {size_m.group(2)}"
            else:
                label = "下载中喵…"
        else:
            # 认不出来的行就不打扰用户了
            label = ""
        return percent, label


class XhanggeOllamaInstallWorker(QThread):
    """后台安装 Ollama：下载安装程序并启动（安装过程需要用户跟着点）。"""

    install_progress = Signal(int, str)
    install_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        import os
        import sys
        import tempfile

        key = "win32" if sys.platform == "win32" else "darwin"
        url = xhangge_config.XHANGGE_OLLAMA_INSTALL_URLS.get(key)
        if url is None:
            self.install_finished.emit(False, f"当前系统（{sys.platform}）还没有 Ollama 安装脚本喵")
            return

        tmp = tempfile.mkdtemp()
        ext = ".exe" if key == "win32" else ".zip"
        dest = os.path.join(tmp, "ollama_installer" + ext)
        try:
            self.install_progress.emit(-1, "正在下载 Ollama 安装程序喵…")
            with requests.get(url, stream=True, timeout=(10, 600)) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if self._stop_requested:
                            return
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.install_progress.emit(
                                int(done / total * 100),
                                f"正在下载安装程序喵 {done // 1024 // 1024}/{total // 1024 // 1024}MB",
                            )
            self.install_progress.emit(-1, "正在启动安装程序喵，请在弹出来的窗口里完成安装…")
            if key == "win32":
                # 阻塞等安装程序跑完（用户跟着向导点完）
                subprocess.run([dest], timeout=600)
            else:
                import zipfile
                with zipfile.ZipFile(dest) as z:
                    z.extractall(tmp)
                subprocess.Popen(["open", os.path.join(tmp, "Ollama.app")])
            # 装完再探测一次，确认真装好了
            ok, version = xhangge_detect_ollama()
            if ok:
                self.install_finished.emit(True, f"Ollama 装好啦喵 🎉（{version}）")
            else:
                self.install_finished.emit(
                    True, "安装程序已经跑完喵，如果刚才没装成功，去 https://ollama.com 手动装一下再回来～"
                )
        except Exception as e:
            self.install_finished.emit(False, f"安装 Ollama 没成功喵 😿（{type(e).__name__}）{str(e)[:120]}")


class XhanggeModelDownloadWorker(QThread):
    """后台把 gguf 模型下载到项目的 local_model 文件夹。"""

    download_progress = Signal(int, str)
    download_finished = Signal(bool, str)

    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.xhangge_model_name = model_name
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        url = xhangge_config.XHANGGE_MODEL_GGUF_URLS.get(self.xhangge_model_name)
        if url is None:
            self.download_finished.emit(
                False, f"模型「{self.xhangge_model_name}」还没有配置 gguf 下载地址喵"
            )
            return

        local_dir = xhangge_config.XHANGGE_LOCAL_MODEL_DIR
        local_dir.mkdir(parents=True, exist_ok=True)
        file_name = url.rstrip("/").split("/")[-1]
        dest = local_dir / file_name
        if dest.exists():
            self.download_finished.emit(True, f"模型「{self.xhangge_model_name}」已经下载好了喵 🎉")
            return

        try:
            self.download_progress.emit(-1, f"开始下载 {file_name} 喵…")
            with requests.get(url, stream=True, timeout=(10, 600)) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if self._stop_requested:
                            f.close()
                            dest.unlink(missing_ok=True)
                            self.download_finished.emit(False, "下载被取消了喵～")
                            return
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.download_progress.emit(
                                int(done / total * 100),
                                f"下载中喵 {done // 1024 // 1024}/{total // 1024 // 1024}MB",
                            )
            self.download_progress.emit(100, "下载完成喵")
            self.download_finished.emit(
                True, f"模型「{self.xhangge_model_name}」已下载到 local_model 文件夹喵 🎉"
            )
        except Exception as e:
            dest.unlink(missing_ok=True)
            self.download_finished.emit(False, f"下载失败喵 😿（{type(e).__name__}）{str(e)[:120]}")


class XhanggeLocalStatusWorker(QThread):
    """后台探测 Ollama 和已装模型状态。

    为什么开线程：/api/tags 的响应实测要 2 秒左右，同步调用会把
    设置窗口卡住；放到后台线程，窗口秒开，状态回来后再刷小药丸。

    只在启动时、切换模型时各探测一次；其余情况直接读缓存。
    """

    status_ready = Signal(bool, str, list)  # (Ollama装了没, 版本号, 已装模型名列表)

    def __init__(self, model_id, parent=None):
        super().__init__(parent)
        self.xhangge_model_id = model_id

    def run(self):
        ollama_ok, version, models = xhangge_detect_status(self.xhangge_model_id)
        self.status_ready.emit(ollama_ok, version, models)


class XhanggeOnlineTestWorker(QThread):
    """后台测试在线 API 配置能不能用（"🔌 测试连接喵"按钮）。

    为什么也要开线程：测试要发一次真实请求，网络慢的时候
    可能卡好几秒，放在界面线程里会让窗口假死。
    """

    # 测试结束（参数：成功了吗，消息）
    test_finished = Signal(bool, str)

    def __init__(self, base_url, api_key, model_name, parent=None):
        super().__init__(parent)
        self._base_url = base_url
        self._api_key = api_key
        self._model_name = model_name

    def run(self):
        from services.xhangge_llm_router import xhangge_test_online_config

        ok, msg = xhangge_test_online_config(
            self._base_url, self._api_key, self._model_name
        )
        self.test_finished.emit(ok, msg)
