# Author: xhangge
# This project is created by xhangge
"""
xhangge_db —— SQLite 数据库层（负责"记忆"）
所有数据都保存在本地一个 SQLite 数据库文件里：
    ~/.xh_snowcat/xhangge_chat.db

数据表结构（原有 2 张 + 新增 5 张）：

1. sessions   会话表：id / title / created_at
              改造后追加两列：xhangge_chat_mode、xhangge_rag_enabled
2. messages   消息表：id / session_id / role / content / created_at
3. xhangge_knowledge_bases    知识库元信息（名字、容量、对应的 Chroma collection）
4. xhangge_kb_files           每个知识库里有哪些文件（含副本路径、块数）
5. xhangge_session_kb_links   会话 ↔ 知识库 绑定关系（多对多，每会话最多 3 个）
6. xhangge_model_configs      在线大模型 API 配置（全表只有一行 is_active=1）
7. xhangge_skill_tasks        学习文档 / 问答集的生成记录

向量数据放在独立的 Chroma 向量库里边：（~/.xh_snowcat/xhangge_chroma/），这个数据库只存元信息。

说明：数据库操作主要发生在主线程（界面线程）。后台线程只在任务，结束时写一次，SQLite 自带写锁且写入频率极低，不需要额外加锁。

"""

import sqlite3
from datetime import datetime
from pathlib import Path

from config import xhangge_settings as xhangge_config


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
        # 升级老数据库（给 sessions 补上新增的两列）
        self._xhangge_migrate()

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
        # ---------------- 以下是改造后新增的 5 张表 ----------------

        # 知识库元信息。注意这里只存"档案卡"，
        # 真正的向量在 Chroma 里，靠 collection_name 对应上。
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xhangge_knowledge_bases (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL UNIQUE,
                collection_name TEXT    NOT NULL UNIQUE,
                used_bytes      INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT    NOT NULL
            )
            """
        )
        # 每个知识库导入了哪些文件。
        # copy_path 是副本路径——导入时会把文件复制到我们自己的目录，
        # 这样用户移动或删除原文件都不影响知识库。
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xhangge_kb_files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                kb_id       INTEGER NOT NULL,
                file_name   TEXT    NOT NULL,
                copy_path   TEXT    NOT NULL,
                size_bytes  INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                imported_at TEXT    NOT NULL,
                FOREIGN KEY (kb_id) REFERENCES xhangge_knowledge_bases(id)
                    ON DELETE CASCADE
            )
            """
        )
        # 会话 ↔ 知识库 的绑定关系（多对多）。
        # 用联合主键防止重复绑定同一个库；
        # 两个外键都带级联删除，所以删会话或删知识库时绑定关系自动清理，
        # 不会留下指向空气的记录。
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xhangge_session_kb_links (
                session_id INTEGER NOT NULL,
                kb_id      INTEGER NOT NULL,
                PRIMARY KEY (session_id, kb_id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (kb_id) REFERENCES xhangge_knowledge_bases(id)
                    ON DELETE CASCADE
            )
            """
        )
        # 在线大模型 API 配置。is_active 全表恒定只有一行是 1，
        # 因为用户"不可能同时用本地和在线"（互斥单选）。
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xhangge_model_configs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                base_url   TEXT    NOT NULL,
                api_key    TEXT    NOT NULL,
                model_name TEXT    NOT NULL,
                is_active  INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL
            )
            """
        )
        # 学习文档 / 问答集的生成记录（方便以后做"我的作业本"之类的功能）
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xhangge_skill_tasks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                skill_type TEXT    NOT NULL,
                depth      TEXT,
                created_at TEXT    NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
                    ON DELETE CASCADE
            )
            """
        )
        self._conn.commit()

    def _xhangge_migrate(self):
        """把老版本的数据库升级到新版（给 sessions 表补列）。

        这段在干什么（用大白话说）：
        你之前的数据库里，sessions 表只有 id/title/created_at 三列。
        现在每个会话还要记住"是 Chat 还是 Agent 模式""检索开关开没开"，
        所以要给这张表加两列。

        为什么这样做很安全：
        1. 先用 PRAGMA table_info 查现在到底有哪些列
        2. 只给"缺失的列"执行 ADD COLUMN，已经有了就跳过
        3. ADD COLUMN 带 DEFAULT 值是 SQLite 里最温和的操作，
           你已有的会话和聊天记录一条都不会动，
           老会话会自动获得默认值（chat 模式 + 检索关闭）
        4. 因为每次只补缺失的列，这个函数可以反复执行不出错
        """
        # 查出 sessions 表当前有哪些列名
        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        # 需要确保存在的新列：(列名, 建列语句)
        wanted = [
            (
                "xhangge_chat_mode",
                "ALTER TABLE sessions ADD COLUMN xhangge_chat_mode "
                "TEXT NOT NULL DEFAULT 'chat'",
            ),
            (
                "xhangge_rag_enabled",
                "ALTER TABLE sessions ADD COLUMN xhangge_rag_enabled "
                "INTEGER NOT NULL DEFAULT 0",
            ),
        ]
        changed = False
        for column_name, ddl in wanted:
            if column_name not in existing:
                self._conn.execute(ddl)
                changed = True

        # ---- messages 表也补一列：这条消息是不是"学习技能的产出" ----
        # 背景：学习文档/问答集也是存在 messages 表里的 assistant 消息。
        # 但生成新的学习资料时，上下文里不该带上旧的资料
        # （实测模型会把旧问答集整段抄进新文档里），
        # 所以给这类消息打上标记，取的时候可以按需排除。
        # 普通聊天的上下文依然包含它们——用户问"第3题再讲讲"时模型得看得到第3题。
        msg_existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "xhangge_is_skill" not in msg_existing:
            self._conn.execute(
                "ALTER TABLE messages ADD COLUMN xhangge_is_skill "
                "INTEGER NOT NULL DEFAULT 0"
            )
            changed = True

        if changed:
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
    def add_message(self, session_id, role, content, is_skill=False):
        """往某个会话里保存一条消息。

        参数：
            role     —— "user"（用户说的）或 "assistant"（雪花喵回答的）
            content  —— 消息内容
            is_skill —— 这条是不是"学习技能的产出"（生成的文档/问答集）。
                        默认 False。打上标记后，get_messages 的
                        exclude_skill 参数就能把它筛出去。
        """
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, xhangge_is_skill, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, 1 if is_skill else 0, self._now()),
        )
        self._conn.commit()

    def get_messages(self, session_id, exclude_skill=False):
        """取出某个会话的全部消息，按时间正序（先问的在前）。

        参数 exclude_skill：
            False（默认）—— 全部都要。普通聊天用这个：
                           用户可能问"第3题再讲讲"，模型得看得到之前生成的第3题。
            True          —— 排除学习技能的产出（文档/问答集）。
                           生成新的学习资料用这个：素材是"聊过的内容"，
                           不是"之前生成的资料"——不然模型会把旧资料整段抄进新文档。

        返回值：[{"role": "user", "content": "xx", "xhangge_is_skill": 0}, ...]
        （多带一个"是否技能产出"的标记，界面加载历史时靠它决定
        要不要给这条消息挂「💾 导出喵」按钮；拼请求的代码只取
        role 和 content，多出来的字段不影响它们喵）
        """
        if exclude_skill:
            rows = self._conn.execute(
                "SELECT role, content, xhangge_is_skill FROM messages "
                "WHERE session_id = ? AND xhangge_is_skill = 0 ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT role, content, xhangge_is_skill FROM messages "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # --------------------------------------------------------
    # 会话状态：Chat/Agent 模式、知识库检索开关、绑定的知识库
    # （这三样都是"每个会话独立记忆"的）
    # --------------------------------------------------------
    def xhangge_get_session_state(self, session_id):
        """读取一个会话的状态，返回 XhanggeSessionState 对象。

        切换会话时调用它，把界面上的胶囊开关、检索开关、
        绑定菜单恢复成这个会话上次的样子。
        """
        from models.xhangge_schemas import XhanggeSessionState

        row = self._conn.execute(
            "SELECT xhangge_chat_mode, xhangge_rag_enabled FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            # 会话不存在（理论上不会发生），给一份默认状态兜底
            return XhanggeSessionState(session_id=session_id)
        return XhanggeSessionState(
            session_id=session_id,
            chat_mode=row["xhangge_chat_mode"],
            rag_enabled=bool(row["xhangge_rag_enabled"]),
            kb_ids=self.xhangge_get_session_kb_ids(session_id),
        )

    def xhangge_set_session_mode(self, session_id, chat_mode):
        """记住这个会话用的是 Chat 还是 Agent 模式。

        参数 chat_mode 只接受 'chat' 或 'agent'，
        传别的值一律当成 'chat'（防御性处理，避免脏数据进库）。
        """
        mode = chat_mode if chat_mode in ("chat", "agent") else "chat"
        self._conn.execute(
            "UPDATE sessions SET xhangge_chat_mode = ? WHERE id = ?",
            (mode, session_id),
        )
        self._conn.commit()

    def xhangge_set_session_rag_enabled(self, session_id, enabled):
        """记住这个会话的知识库检索开关是开还是关。

        注意：关掉开关不会解除绑定关系。
        打个比方——绑定是"把参考书放在桌上"，开关是"允不允许雪花喵翻书"。
        关掉只是不让翻，书还在桌上，下次打开原来那几本还在。
        """
        self._conn.execute(
            "UPDATE sessions SET xhangge_rag_enabled = ? WHERE id = ?",
            (1 if enabled else 0, session_id),
        )
        self._conn.commit()

    def xhangge_get_session_kb_ids(self, session_id):
        """查这个会话绑定了哪几个知识库，返回 id 列表（可能是空列表）"""
        rows = self._conn.execute(
            "SELECT kb_id FROM xhangge_session_kb_links "
            "WHERE session_id = ? ORDER BY kb_id ASC",
            (session_id,),
        ).fetchall()
        return [row["kb_id"] for row in rows]

    def xhangge_bind_kb(self, session_id, kb_id):
        """给会话绑定一个知识库。

        返回：
            True  —— 绑定成功
            False —— 已经绑满 3 个了（上限由 config 里的
                     XHANGGE_MAX_KB_PER_SESSION 决定），界面据此弹提示

        为什么限制 3 个：每多绑一个就多一轮检索，塞进上下文的片段也更多，
        模型注意力被稀释，速度变慢、回答反而更糊。
        """
        current = self.xhangge_get_session_kb_ids(session_id)
        if kb_id in current:
            return True  # 已经绑过了，当作成功
        if len(current) >= xhangge_config.XHANGGE_MAX_KB_PER_SESSION:
            return False
        self._conn.execute(
            "INSERT OR IGNORE INTO xhangge_session_kb_links (session_id, kb_id) "
            "VALUES (?, ?)",
            (session_id, kb_id),
        )
        self._conn.commit()
        return True

    def xhangge_unbind_kb(self, session_id, kb_id):
        """解除一个会话和某个知识库的绑定"""
        self._conn.execute(
            "DELETE FROM xhangge_session_kb_links WHERE session_id = ? AND kb_id = ?",
            (session_id, kb_id),
        )
        self._conn.commit()

    def xhangge_get_kb_session_ids(self, kb_id):
        """查一个知识库绑定了哪些会话，返回会话 id 列表。"""
        rows = self._conn.execute(
            "SELECT session_id FROM xhangge_session_kb_links "
            "WHERE kb_id = ? ORDER BY session_id ASC",
            (kb_id,),
        ).fetchall()
        return [row["session_id"] for row in rows]

    # --------------------------------------------------------
    # 知识库元信息
    # --------------------------------------------------------
    def xhangge_create_kb(self, name):
        """新建一个知识库。

        返回：
            知识库 id —— 建成功了
            None      —— 名字重复，或者已经建满 10 个（硬限制）

        collection_name 用 "xhangge_kb_<id>" 的格式，
        所以要先插入拿到 id，再回填这个字段。
        """
        clean_name = (name or "").strip()
        if not clean_name:
            return None
        # 硬限制：最多 10 个知识库
        if self.xhangge_count_kb() >= xhangge_config.XHANGGE_MAX_KB_COUNT:
            return None
        try:
            cursor = self._conn.execute(
                "INSERT INTO xhangge_knowledge_bases "
                "(name, collection_name, used_bytes, created_at) VALUES (?, ?, 0, ?)",
                (clean_name, "pending", self._now()),
            )
            kb_id = cursor.lastrowid
            # 拿到 id 后回填 collection 名字
            self._conn.execute(
                "UPDATE xhangge_knowledge_bases SET collection_name = ? WHERE id = ?",
                (f"xhangge_kb_{kb_id}", kb_id),
            )
            self._conn.commit()
            return kb_id
        except sqlite3.IntegrityError:
            # UNIQUE 约束失败 = 名字already被用了
            return None

    def xhangge_count_kb(self):
        """现在一共有几个知识库（用来判断有没有到 10 个上限）"""
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM xhangge_knowledge_bases"
        ).fetchone()
        return row["c"] if row else 0

    def xhangge_list_kb(self):
        """列出所有知识库，返回 XhanggeKbInfo 列表（带文件数量）"""
        from models.xhangge_schemas import XhanggeKbInfo

        rows = self._conn.execute(
            """
            SELECT kb.id, kb.name, kb.collection_name, kb.used_bytes, kb.created_at,
                   (SELECT COUNT(*) FROM xhangge_kb_files f WHERE f.kb_id = kb.id)
                       AS file_count
            FROM xhangge_knowledge_bases kb
            ORDER BY kb.id ASC
            """
        ).fetchall()
        return [
            XhanggeKbInfo(
                id=r["id"],
                name=r["name"],
                collection_name=r["collection_name"],
                used_bytes=r["used_bytes"],
                created_at=r["created_at"],
                file_count=r["file_count"],
            )
            for r in rows
        ]

    def xhangge_get_kb(self, kb_id):
        """按 id 查一个知识库，查不到返回 None"""
        for kb in self.xhangge_list_kb():
            if kb.id == kb_id:
                return kb
        return None

    def xhangge_rename_kb(self, kb_id, new_name):
        """给知识库改名。返回 False 表示新名字和别的库重名了。"""
        clean_name = (new_name or "").strip()
        if not clean_name:
            return False
        try:
            self._conn.execute(
                "UPDATE xhangge_knowledge_bases SET name = ? WHERE id = ?",
                (clean_name, kb_id),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def xhangge_delete_kb(self, kb_id):
        """删除知识库的元信息。

        注意：这里只删数据库里的记录。
        Chroma 里的 collection 和磁盘上的文件副本要由
        services/xhangge_rag_service.py 负责清理——
        数据层不碰文件系统，各司其职。

        因为建表时设了级联删除，这一句会自动连带清掉：
        - 该库下所有 xhangge_kb_files 记录
        - 所有会话对它的绑定关系
        """
        self._conn.execute(
            "DELETE FROM xhangge_knowledge_bases WHERE id = ?", (kb_id,)
        )
        self._conn.commit()

    def xhangge_kb_has_room(self, kb_id, incoming_bytes):
        """这个知识库还装得下 incoming_bytes 这么多字节吗？

        返回 (装得下吗, 还剩多少字节)。
        界面拿这两个值去决定"直接导入"还是"弹提示拒绝"。
        """
        kb = self.xhangge_get_kb(kb_id)
        if kb is None:
            return False, 0
        remain = xhangge_config.XHANGGE_MAX_KB_BYTES - kb.used_bytes
        return incoming_bytes <= remain, max(0, remain)

    # --------------------------------------------------------
    # 知识库文件
    # --------------------------------------------------------
    def xhangge_add_kb_file(self, kb_id, file_name, copy_path, size_bytes, chunk_count):
        """登记一个导入成功的文件，同时累加知识库的已用容量。

        返回这条文件记录的 id —— 这个 id 非常重要：
        存进 Chroma 的每个文本块都会在 metadata 里带上它，
        将来删文件时就能用 `where={"xhangge_file_id": 这个id}`
        一次性精确删掉该文件的所有向量，不用大模型、不会误删。
        """
        cursor = self._conn.execute(
            "INSERT INTO xhangge_kb_files "
            "(kb_id, file_name, copy_path, size_bytes, chunk_count, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kb_id, file_name, copy_path, size_bytes, chunk_count, self._now()),
        )
        # 累加已用容量
        self._conn.execute(
            "UPDATE xhangge_knowledge_bases SET used_bytes = used_bytes + ? WHERE id = ?",
            (size_bytes, kb_id),
        )
        self._conn.commit()
        return cursor.lastrowid

    def xhangge_update_kb_file_chunks(self, file_id, chunk_count):
        """回填一个文件实际切成的块数。

        为什么需要它：导入流程是"先登记文件拿到 file_id（块数先记 0），
        → 向量化时把 file_id 写进每个块的 metadata → 最后才知道确切块数"。
        file_id 必须在向量化之前就有，否则删文件的精确删除就没了着落。
        """
        self._conn.execute(
            "UPDATE xhangge_kb_files SET chunk_count = ? WHERE id = ?",
            (chunk_count, file_id),
        )
        self._conn.commit()

    def xhangge_list_kb_files(self, kb_id):
        """列出某个知识库里的所有文件"""
        from models.xhangge_schemas import XhanggeKbFile

        rows = self._conn.execute(
            "SELECT id, kb_id, file_name, copy_path, size_bytes, chunk_count, "
            "imported_at FROM xhangge_kb_files WHERE kb_id = ? ORDER BY id ASC",
            (kb_id,),
        ).fetchall()
        return [
            XhanggeKbFile(
                id=r["id"],
                kb_id=r["kb_id"],
                file_name=r["file_name"],
                copy_path=r["copy_path"],
                size_bytes=r["size_bytes"],
                chunk_count=r["chunk_count"],
                imported_at=r["imported_at"],
            )
            for r in rows
        ]

    def xhangge_get_kb_file(self, file_id):
        """按 id 查一个文件记录，查不到返回 None"""
        from models.xhangge_schemas import XhanggeKbFile

        r = self._conn.execute(
            "SELECT id, kb_id, file_name, copy_path, size_bytes, chunk_count, "
            "imported_at FROM xhangge_kb_files WHERE id = ?",
            (file_id,),
        ).fetchone()
        if r is None:
            return None
        return XhanggeKbFile(
            id=r["id"],
            kb_id=r["kb_id"],
            file_name=r["file_name"],
            copy_path=r["copy_path"],
            size_bytes=r["size_bytes"],
            chunk_count=r["chunk_count"],
            imported_at=r["imported_at"],
        )

    def xhangge_delete_kb_file(self, file_id):
        """删除一条文件记录，并把容量还给知识库。

        同样只管数据库，磁盘上的副本文件和 Chroma 里的向量
        由 rag_service 负责删。
        """
        f = self.xhangge_get_kb_file(file_id)
        if f is None:
            return
        self._conn.execute("DELETE FROM xhangge_kb_files WHERE id = ?", (file_id,))
        # 归还容量。用 MAX(0, ...) 兜底，避免出现负数
        self._conn.execute(
            "UPDATE xhangge_knowledge_bases "
            "SET used_bytes = MAX(0, used_bytes - ?) WHERE id = ?",
            (f.size_bytes, f.kb_id),
        )
        self._conn.commit()

    def xhangge_clear_kb_files(self, kb_id):
        """清空某个知识库的所有文件记录，容量归零（"清空内容"功能用）"""
        self._conn.execute("DELETE FROM xhangge_kb_files WHERE kb_id = ?", (kb_id,))
        self._conn.execute(
            "UPDATE xhangge_knowledge_bases SET used_bytes = 0 WHERE id = ?",
            (kb_id,),
        )
        self._conn.commit()

    # --------------------------------------------------------
    # 在线大模型 API 配置
    # --------------------------------------------------------
    def xhangge_add_model_config(self, name, base_url, api_key, model_name):
        """保存一份在线模型配置，返回它的 id。

        新加的配置默认不激活（is_active=0），
        需要用户在设置里明确选中才会生效。
        """
        cursor = self._conn.execute(
            "INSERT INTO xhangge_model_configs "
            "(name, base_url, api_key, model_name, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (name.strip(), base_url.strip(), api_key.strip(),
             model_name.strip(), self._now()),
        )
        self._conn.commit()
        return cursor.lastrowid

    def xhangge_list_model_configs(self):
        """列出所有已保存的在线模型配置"""
        from models.xhangge_schemas import XhanggeModelConfig

        rows = self._conn.execute(
            "SELECT id, name, base_url, api_key, model_name, is_active, created_at "
            "FROM xhangge_model_configs ORDER BY id ASC"
        ).fetchall()
        return [
            XhanggeModelConfig(
                id=r["id"],
                name=r["name"],
                base_url=r["base_url"],
                api_key=r["api_key"],
                model_name=r["model_name"],
                is_active=bool(r["is_active"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def xhangge_get_active_model_config(self):
        """拿到当前激活的在线模型配置。

        返回 None 有两种含义：一是用户选的是本地 Ollama，
        二是压根还没配过在线 API。两种情况下都该用本地模型。
        """
        for cfg in self.xhangge_list_model_configs():
            if cfg.is_active:
                return cfg
        return None

    def xhangge_activate_model_config(self, config_id):
        """激活某一份在线配置（传 None 表示改回用本地 Ollama）。

        关键：先把全表 is_active 全部清 0，再把目标那行置 1。
        这样保证"全表永远只有一行是激活的"——
        因为用户不可能同时用本地和在线，这是互斥单选。
        """
        self._conn.execute("UPDATE xhangge_model_configs SET is_active = 0")
        if config_id is not None:
            self._conn.execute(
                "UPDATE xhangge_model_configs SET is_active = 1 WHERE id = ?",
                (config_id,),
            )
        self._conn.commit()

    def xhangge_delete_model_config(self, config_id):
        """删掉一份在线模型配置"""
        self._conn.execute(
            "DELETE FROM xhangge_model_configs WHERE id = ?", (config_id,)
        )
        self._conn.commit()

    # --------------------------------------------------------
    # Skill 生成记录
    # --------------------------------------------------------
    def xhangge_add_skill_task(self, session_id, skill_type, depth=None):
        """记一条"生成了学习文档/问答集"的流水。

        参数：
            skill_type —— "doc"（普通知识文档）或 "qa"（问答集）
            depth      —— 问答集的档位：shallow / medium / deep，
                          普通文档传 None
        """
        cursor = self._conn.execute(
            "INSERT INTO xhangge_skill_tasks (session_id, skill_type, depth, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, skill_type, depth, self._now()),
        )
        self._conn.commit()
        return cursor.lastrowid

    # --------------------------------------------------------
    # 收尾
    # --------------------------------------------------------
    def close(self):
        """关闭数据库连接（程序退出时调用，养成好习惯喵）"""
        try:
            self._conn.close()
        except sqlite3.Error:
            pass
