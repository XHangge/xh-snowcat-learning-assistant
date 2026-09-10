# Author: xhangge
# This project is created by xhangge
"""
database —— SQLite 数据库层（负责"记忆"）
所有会话列表和聊天记录都保存在本地一个 SQLite 数据库文件里：
    ~/.xh_snowcat/xhangge_chat.db

数据表结构（两张表）：
1. sessions（会话表）：id / title（标题）/ created_at（创建时间）
2. messages（消息表）：id / session_id（属于哪个会话）/ role（user 或 assistant）
                      / content（消息内容）/ created_at（创建时间）

说明：本项目的所有数据库操作都发生在主线程（界面线程），
模型请求在后台线程进行但不动数据库，因此不需要加线程锁。
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from core import xhangge_config


class XhanggeDatabase:
    """雪花喵的"记忆管理员"：所有会话/消息的增删改查都通过这个类完成"""

    def __init__(self, db_path=None):
        """打开（或创建）数据库文件，并建好需要的表。

        这段在干什么：
        1. 确定数据库文件路径（默认用全局配置里的路径，也支持传别的路径方便测试）
        2. 确保数据目录存在
        3. 连接数据库并执行建表语句
        """
        if db_path is None:
            db_path = xhangge_config.DB_PATH
        self.db_path = Path(db_path)
        # 数据库文件放在 ~/.xh_snowcat/ 里，目录不存在就先创建
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 连接数据库（文件不存在时 sqlite 会自动创建）
        # check_same_thread=False：允许非创建线程使用（保险起见打开，本项目主要在主线程用）
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        # 让查询结果可以像字典一样按列名取值，例如 row["title"]
        self._conn.row_factory = sqlite3.Row
        # 打开外键支持：删除会话时，自动连带删除它下面的所有消息
        self._conn.execute("PRAGMA foreign_keys = ON")
        # 建表
        self._create_tables()

    # --------------------------------------------------------
    # 内部工具
    # --------------------------------------------------------
    def _create_tables(self):
        """建表（如果表已经存在就跳过，不会重复创建）"""
        # IF NOT EXISTS：表已存在时不报错，保证重复启动程序也安全
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL DEFAULT '新会话喵',
                created_at TEXT    NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                created_at TEXT    NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _now():
        """返回当前时间的字符串（例如 2026-09-10 15:30:00），用于记录创建时间"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --------------------------------------------------------
    # 会话（session）相关操作
    # --------------------------------------------------------
    def create_session(self):
        """新建一个会话，返回它的 id。

        这段在干什么：
        往 sessions 表里插一行，标题先用默认值"新会话喵"，
        等用户发出第一个问题后，再由 ensure_session_title() 把标题改成问题的前 20 个字。
        """
        cursor = self._conn.execute(
            "INSERT INTO sessions (title, created_at) VALUES (?, ?)",
            (xhangge_config.DEFAULT_SESSION_TITLE, self._now()),
        )
        self._conn.commit()
        # lastrowid 就是刚插入这一行的 id
        return cursor.lastrowid

    def rename_session(self, session_id, new_title):
        """重命名会话标题（右键菜单里"重命名"功能用它实现）"""
        title = (new_title or "").strip()
        # 标题不允许改成空的，空的话保持原样
        if not title:
            return
        self._conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?",
            (title, session_id),
        )
        self._conn.commit()

    def delete_session(self, session_id):
        """删除会话。

        这段在干什么：
        只需要删 sessions 表里的一行——
        因为建表时设置了 ON DELETE CASCADE（级联删除），
        该会话下的所有消息会被 SQLite 自动连带删除，不会留下孤儿数据。
        """
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()

    def list_sessions(self):
        """取出所有会话，按创建时间倒序（最新创建的排在最前面）。

        返回值是一个字典列表：[{"id": 1, "title": "xx", "created_at": "xx"}, ...]
        """
        rows = self._conn.execute(
            "SELECT id, title, created_at FROM sessions ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_session_title(self, session_id):
        """查询单个会话的标题"""
        row = self._conn.execute(
            "SELECT title FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row["title"] if row else None

    def ensure_session_title(self, session_id, first_question):
        """如果会话还是默认标题，就用用户的第一个问题做标题。

        这段在干什么（对应需求"每个会话的默认标题 = 第一个问题的前 20 个字"）：
        1. 先看当前标题是不是还是默认值"新会话喵"
        2. 是的话，把用户的问题去掉首尾空白、截取前 20 个字，作为新标题
        3. 已经改过标题的会话不会被覆盖（用户手动重命名过就尊重用户）
        """
        current_title = self.get_session_title(session_id)
        if current_title != xhangge_config.DEFAULT_SESSION_TITLE:
            return  # 已经有正式标题了，不动它
        question = (first_question or "").strip()
        if not question:
            return
        # 截取前 20 个字作为标题
        new_title = question[: xhangge_config.SESSION_TITLE_MAX_LEN]
        self.rename_session(session_id, new_title)

    # --------------------------------------------------------
    # 消息（message）相关操作
    # --------------------------------------------------------
    def add_message(self, session_id, role, content):
        """往某个会话里保存一条消息。

        参数：
            role    —— "user"（用户说的）或 "assistant"（雪花喵回答的）
            content —— 消息内容
        """
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, self._now()),
        )
        self._conn.commit()

    def get_messages(self, session_id):
        """取出某个会话的全部消息，按时间正序（先问的在前）。

        返回值：[{"role": "user", "content": "xx"}, ...]
        这个列表会被直接拼进发给 Ollama 的请求里，实现"会话记忆"。
        """
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # --------------------------------------------------------
    # 收尾
    # --------------------------------------------------------
    def close(self):
        """关闭数据库连接（程序退出时调用，养成好习惯喵）"""
        try:
            self._conn.close()
        except sqlite3.Error:
            pass
