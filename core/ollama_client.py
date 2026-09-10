# Author: xhangge
# This project is created by xhangge
"""
ollama_client —— 和本地 Ollama 大模型对话的"传令兵"
负责把聊天记录发给本地部署的 qwen2.5:7b 模型，并把模型的回答
一块一块地（流式）传回界面，实现"打字机效果"。

为什么需要后台线程（QThread）：
模型生成回答需要几十秒，如果在界面线程里直接等待，
整个窗口会卡死（不能拖动、不能点按钮）。
所以把"等待模型"这件事放到后台线程，界面始终保持流畅；
后台线程每收到一小段文字，就通过 Qt 信号（Signal）通知界面更新。
"""

import json

import requests
from PySide6.QtCore import QThread, Signal

from core import xhangge_config


class XhanggeChatWorker(QThread):
    """后台聊天工作线程：负责一次"发出问题 → 流式接收回答"的完整过程。

    使用方式（由主窗口调用）：
        worker = XhanggeChatWorker(messages)
        worker.chunk_received.connect(界面追加文字)     # 每收到一小段就调用
        worker.stream_finished.connect(回答完成的处理)   # 正常结束或被手动停止
        worker.stream_error.connect(出错的提示)         # 连不上模型等错误
        worker.start()                                  # 启动后台线程
    """

    # ---- Qt 信号定义（后台线程 → 界面线程 的"传话筒"）----
    # 每收到一小段回答文字就发一次（参数：这一小段文字）
    chunk_received = Signal(str)
    # 回答结束（参数：完整的回答全文；用户中途停止时也走这里，带已生成的部分）
    stream_finished = Signal(str)
    # 出错了（参数：给用户看的友好中文错误信息）
    stream_error = Signal(str)

    def __init__(self, messages, base_url=None, model=None, parent=None):
        """初始化工作线程。

        参数：
            messages  —— 发给模型的消息列表，格式：
                         [{"role": "system", "content": 系统提示词},
                          {"role": "user", "content": "问题"}, ...]
        """
        super().__init__(parent)
        self.messages = messages
        self.base_url = base_url or xhangge_config.OLLAMA_BASE_URL
        self.model = model or xhangge_config.XHANGGE_MODEL_NAME
        # 用户是否请求了"停止生成"
        self._stop_requested = False
        # 正在进行中的 HTTP 响应对象（停止时需要把它关掉）
        self._response = None

    # --------------------------------------------------------
    # 对外方法
    # --------------------------------------------------------
    def request_stop(self):
        """请求停止生成（界面上的"停止喵"按钮调用）。

        这段在干什么：
        1. 设置停止标志，后台循环看到标志就不再继续
        2. 直接关闭 HTTP 连接——正在进行的"等待模型输出"会立刻被打断
           （不关闭的话，模型可能还会继续生成好几秒才停）
        """
        self._stop_requested = True
        if self._response is not None:
            try:
                self._response.close()
            except Exception:
                # 关闭失败也不影响，循环标志兜底
                pass

    # --------------------------------------------------------
    # 线程主体（worker.start() 之后，这段代码在后台线程里运行）
    # --------------------------------------------------------
    def run(self):
        full_text = ""  # 累积模型的完整回答

        try:
            # ---- 1. 发起流式请求 ----
            # stream=True：不要等模型全部想完再返回，而是边生成边传输
            self._response = requests.post(
                self.base_url + "/api/chat",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "stream": True,
                },
                stream=True,
                timeout=xhangge_config.XHANGGE_REQUEST_TIMEOUT,
            )
            # 如果服务器返回了错误状态码（如 404 模型不存在），这里会抛出异常
            self._response.raise_for_status()

            # ---- 2. 逐行读取流式回答 ----
            # Ollama 每生成一小段，就发来一行 JSON，例如：
            # {"message": {"role": "assistant", "content": "喵"}, "done": false}
            for line in self._response.iter_lines(decode_unicode=True):
                # 用户点了停止，立刻退出循环
                if self._stop_requested:
                    break
                # 空行跳过
                if not line:
                    continue
                # 把这一行 JSON 文本解析成字典；个别行解析失败就跳过，不让程序崩溃
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # 取出这一小段回答文字
                piece = (data.get("message") or {}).get("content", "")
                if piece:
                    full_text += piece          # 累积到全文
                    self.chunk_received.emit(piece)  # 通知界面：追加这一小段
                # Ollama 发来 done: true 表示回答结束
                if data.get("done"):
                    break

            # ---- 3. 正常收尾（包括用户中途停止的情况）----
            # 把已生成的完整文字（可能是全部，也可能是停止前的部分）交给界面保存
            self.stream_finished.emit(full_text)

        except requests.exceptions.ConnectionError:
            # 连不上 Ollama 服务（最常见：Ollama 没启动）
            self.stream_error.emit(
                "喵呜呜！连不上 Ollama 喵 😿\n\n"
                "请检查一下：\n"
                "1. Ollama 是否已经启动？（终端里运行：ollama serve）\n"
                "2. 服务地址是否正确？（当前配置："
                + self.base_url + "）"
            )
        except requests.exceptions.Timeout:
            # 连接或读取超时
            self.stream_error.emit(
                "等待 Ollama 回应超时了喵 ⏰\n"
                "可能模型正在忙或者电脑负载太高，稍等一下再试试喵～"
            )
        except requests.exceptions.HTTPError as e:
            # 服务器返回错误状态码
            status = e.response.status_code if e.response is not None else "?"
            if status == 404:
                # Ollama 返回 404 通常是"模型不存在"
                self.stream_error.emit(
                    "找不到模型「" + self.model + "」喵 😿\n\n"
                    "请先在终端里下载模型：\n"
                    "ollama pull " + self.model
                )
            else:
                self.stream_error.emit(
                    "Ollama 返回了错误（状态码 " + str(status) + "）喵：\n" + str(e)
                )
        except Exception as e:
            # 其它预料之外的错误
            self.stream_error.emit("发生了未知错误喵 😿\n" + str(e))
        finally:
            # 无论成功失败，都把响应对象清空，避免占用连接
            self._response = None


def check_ollama_status(base_url=None, model=None):
    """检查 Ollama 服务和模型是否就绪（程序启动时调用）。

    这段在干什么：
    1. 访问 Ollama 的 /api/tags 接口，拿到本机已安装的模型列表
    2. 返回两个布尔值：(服务是否在线, 指定模型是否已下载)

    返回：
        (True, True)   —— 一切就绪
        (True, False)  —— Ollama 在运行，但 qwen2.5:7b 还没下载
        (False, False) —— Ollama 没在运行
    """
    base_url = base_url or xhangge_config.OLLAMA_BASE_URL
    model = model or xhangge_config.XHANGGE_MODEL_NAME
    try:
        resp = requests.get(base_url + "/api/tags", timeout=3)
        if not resp.ok:
            return False, False
        # 解析模型列表，例如 ["qwen2.5:7b", "bge-m3:latest"]
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        # 名字完全相同，或是同名带变体后缀（如 qwen2.5:7b-q4）都算可用
        model_ready = any(n == model or n.startswith(model + "-") for n in names)
        return True, model_ready
    except requests.RequestException:
        # 连不上、超时等一切网络问题，都视为服务不在线
        return False, False
