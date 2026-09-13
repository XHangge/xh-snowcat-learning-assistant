# Author: xhangge
# This project is created by xhangge
"""
tools —— Agent 能使用的工具箱（LangChain Tools）

每个文件封装一种能力，交给 Agent 后由它自己判断该不该用。
其中"改文件、删文件、跑命令"属于高危操作，必须经过人工确认弹窗。

包含：
- xhangge_search_tool.py   联网搜索（Tavily 优先，没配 Key 就用 DuckDuckGo）
- xhangge_kb_tool.py       查知识库（作用范围锁定在当前会话绑定的知识库）
- xhangge_ide_tool.py      打开文件 / 执行终端命令
- xhangge_file_tool.py     读文件（免审）/ 写文件、删文件（必审）
- xhangge_sandbox_tool.py  在受限沙箱里跑 Python 代码
"""
