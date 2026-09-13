# Author: xhangge
# This project is created by xhangge
"""
gui —— 界面层（PySide6 / Qt6）

这一层只做三件事：
1. 把界面画出来
2. 把用户的操作通过 Qt 信号转发出去
3. 接收 services 层回传的信号，把结果显示出来

铁律：这一层不允许出现 langchain / chromadb / llama_index 的 import。
任何业务逻辑都要放到 services/ 里，界面只管展示。
"""
