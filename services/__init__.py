# Author: xhangge
# This project is created by xhangge
"""
services —— 业务逻辑层（整个软件的"发动机舱"）

界面层（gui/）只会调用这一层的方法，然后等 Qt 信号把结果送回来。
所有耗时的活儿（问模型、下载模型、解析文档、跑 Agent）都在这一层
的 QThread 里进行，保证界面永远不卡。

包含：
- xhangge_llm_router.py     模型路由：本地 Ollama / 在线 API 二选一，可热切换
- xhangge_chat_service.py   普通聊天（流式）
- xhangge_agent_service.py  Agent 编排（工具调用 + 人工检查点）
- xhangge_ollama_deploy.py  一键下载本地模型（带进度）
- xhangge_skill_service.py  生成学习文档 / 问答集
- xhangge_rag_service.py    知识库：导入、检索、删除
"""
