# Author: xhangge
# This project is created by xhangge
"""
models —— 数据层
只负责"把数据存进去、把数据读出来"，不含任何业务判断。

包含：
- xhangge_db.py      SQLite 全部读写 + 启动时的数据库升级（迁移）
- xhangge_schemas.py 层与层之间传递数据用的结构定义
"""
