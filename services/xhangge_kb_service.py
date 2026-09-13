# Author: xhangge
# This project is created by xhangge
"""
xhangge_kb_service —— 知识库 RAG 服务层（模块五）

一个知识库的完整一生都在这个文件里：

    建库 → 导入文件（复制副本 → 解析文字 → 切块 → 向量化 → 存进 Chroma）
        → 检索（问题向量化 → 按相似度找出最相关的几段）
        → 删除（按文件精确删 / 整库删）

三个框架各干各擅长的事（项目原则）：
- LlamaIndex（readers-file）：只用来"读文件"，把 pdf/txt/md/docx 变成纯文字
- Ollama（bge-m3）：只用来"算向量"，把文字变成 1024 个数字
- ChromaDB：只用来"存向量、查相似"，每个知识库对应一个 collection

分层规矩（和项目其它部分一致）：
- 数据库里只存"档案"（哪个库、哪个文件、占了多少容量）——models 层管
- 磁盘上的副本文件、Chroma 里的向量，都由本文件负责删——各司其职
- 界面不碰这些，只调这里的方法

安全红线（和用户确认过的）：
删除只动 ~/.xh_snowcat/xhangge_kb_files/ 里我们自己复制的副本，
用户桌面/下载文件夹里的原始文件永远不碰喵。
"""

import json
import logging
import math
import re
import shutil
from datetime import datetime
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from config import xhangge_settings as xhangge_config
from models.xhangge_schemas import XhanggeRetrievedChunk

# llama-index 每发一次 HTTP 请求都会打一条 INFO 日志，
# 向量化几百块就是几百条，把控制台刷成瀑布。
# 这里把底层 httpx 的日志级别调高，只在出错时才说话。
logging.getLogger("httpx").setLevel(logging.WARNING)

# 导入时每多少块向量化一批、存一批（用配置里的 XHANGGE_EMBED_BATCH，
# 一次 HTTP 请求就能塞下这批，进度条和网络请求保持同步）。

# Chroma 客户端全局只建一次（连接有成本，而且 PersistentClient
# 多开可能锁库）。None 表示还没建过。
_xhangge_chroma_client = None


def _xhangge_get_chroma():
    """拿到全局唯一的 Chroma 客户端（连着 ~/.xh_snowcat/xhangge_chroma/）。

    embedding_function=None 是刻意的：
    我们自己用 Ollama 算向量、把向量直接喂给 Chroma，
    不让 Chroma 去加载它自带的默认向量化模型
    （那个会拖进来一堆 onnxruntime 之类的重依赖，打包会爆炸）。
    """
    global _xhangge_chroma_client
    if _xhangge_chroma_client is None:
        import chromadb

        xhangge_config.XHANGGE_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _xhangge_chroma_client = chromadb.PersistentClient(
            path=str(xhangge_config.XHANGGE_CHROMA_DIR),
        )
    return _xhangge_chroma_client


def _xhangge_get_collection(kb, create=False):
    """拿到某个知识库对应的 Chroma collection。

    参数：
        kb    —— XhanggeKbInfo（数据库里的档案，带 collection_name）
        create —— True：没有就建（导入第一个文件时用）
                  False：没有就返回 None（检索/删除时用，没有=没东西可查）
    """
    client = _xhangge_get_chroma()
    name = kb.collection_name
    try:
        # embedding_function=None：跳过默认向量化模型（见上）
        return client.get_collection(name, embedding_function=None)
    except Exception:
        if create:
            # hnsw:space=cosine：用余弦相似度算距离。
            # 不指定的话 Chroma 默认用 L2（直线距离），
            # 对文字语义检索来说余弦才是主流做法。
            return client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=None,
            )
        return None


# ============================================================
# 解析和切块（纯函数，谁都能调，也方便测试）
# ============================================================
def xhangge_parse_file(file_path):
    """把一个文件读成纯文字。支持 pdf / txt / md / docx。

    直接按扩展名挑解析器，不再走 LlamaIndex 的 SimpleDirectoryReader：
    它为了"自动识别格式"要加载一大堆 reader，单个小文件也要花好几秒。
    换成直读后，docx 从 ~5s 降到 ~0.1s，pdf 也只依赖轻量的 pypdf。
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext == ".docx":
        import docx2txt

        return docx2txt.process(str(path)) or ""
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages)
    # txt / md 等纯文本：直接读。优先 UTF-8，失败退回 GBK（Windows 记事本默认）
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="replace")


def xhangge_chunk_text(text):
    """把一长段文字切成一块一块（语义切块）。

    和以前"固定 512 字硬切"的区别：先按句末标点和换行把文字切成一句一句，
    再把句子往块里装，装不下才另起一块——这样绝不会把一句话拦腰截断，
    检索到的每个块都是完整的语义单元，喂给模型才答得好。

    为什么要重叠：相邻块重叠 overlap 个字，让边界附近的内容
    在前后两块里都有备份，检索时不容易漏掉跨边界的答案。
    """
    # 压掉连续空白（PDF 解析常吐出一堆连续空格和换行）
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if not text:
        return []

    size = xhangge_config.XHANGGE_CHUNK_SIZE
    overlap = xhangge_config.XHANGGE_CHUNK_OVERLAP

    # 按句末标点 / 换行切成句子（标点保留在句尾）
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[。！？；.!?;])|\n", text)
        if s.strip()
    ]

    chunks = []
    current = ""
    for sent in sentences:
        # 单句就超过块大小（超长句子，罕见）：硬切成 size 大小，别让它撑爆
        if len(sent) > size:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(sent), size):
                chunks.append(sent[i:i + size])
            continue
        # 装不下就另起一块，并从上一块末尾带 overlap 个字当重叠
        if len(current) + len(sent) > size:
            if current:
                chunks.append(current)
            current = (current[-overlap:] if overlap > 0 else "") + sent
        else:
            current += sent

    if current:
        chunks.append(current)
    return chunks


def _xhangge_make_embedding():
    """造一个连着本地 Ollama 的向量化器（bge-m3）。"""
    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(
        model_name=xhangge_config.XHANGGE_EMBED_MODEL,
        base_url=xhangge_config.OLLAMA_BASE_URL,
        # 一次 HTTP 请求向量化多少块：LlamaIndex 默认 10 太碎，
        # 块一多就来回发几十次请求；调大后一次请求顶好几批，导入明显变快。
        embed_batch_size=xhangge_config.XHANGGE_EMBED_BATCH,
        # 查询侧加检索指令：查询和文档不对称，加这句让 bge-m3 更懂"这是来检索的"
        query_instruction=xhangge_config.XHANGGE_QUERY_INSTRUCTION,
    )


def _xhangge_ollama_alive():
    """快速探测 Ollama 服务在不在（3 秒连接超时）。

    为什么要单独探一次：向量化前不探的话，Ollama 没开时
    llama-index 的 ollama 客户端要等它的连接超时才报错，卡十几秒，
    前端就干瞪眼。这里先快速探一下，不在就直接失败，别让用户等。
    """
    try:
        r = requests.get(xhangge_config.OLLAMA_BASE_URL + "/api/tags", timeout=3)
        return r.ok
    except requests.RequestException:
        return False


# ============================================================
# 导入文件的后台线程（界面调用）
# ============================================================
class XhanggeKbImportWorker(QThread):
    """把一个文件完整导入知识库的后台线程。

    使用方式（由知识库窗口调用）：
        worker = XhanggeKbImportWorker(db, kb_id, "资料.pdf")
        worker.import_progress.connect(进度条更新)   # (百分比或-1, 状态文字)
        worker.import_finished.connect(结束处理)     # (成功了吗, 消息)
        worker.start()

    完整流程（每一步都发进度）：
        1. 检查容量（30MB 上限）        —— 快
        2. 复制一份到我们自己的目录      —— 快
        3. 解析成纯文字                  —— 快
        4. 切块（约512字/块）           —— 快
        5. 分批向量化 + 存进 Chroma      —— 最慢，进度条按批次走
        6. 登记进数据库                  —— 快
    """

    import_progress = Signal(int, str)   # (百分比 0-100 或 -1=不确定, 状态文字)
    import_finished = Signal(bool, str)  # (成功了吗, 给用户看的消息)
    file_registered = Signal()           # 文件已登记进数据库（界面刷新容量/文件列表用）

    def __init__(self, db, kb_id, file_path, parent=None):
        super().__init__(parent)
        self.db = db
        self.kb_id = kb_id
        # Path() 统一处理路径：自动去掉引号、兼容各种写法
        self.file_path = Path(file_path)
        self._stop_requested = False

    def request_stop(self):
        """用户点了取消：立个标志，线程在批次之间检查它。"""
        self._stop_requested = True

    # ---------------- 各阶段的小函数 ----------------
    def _fail(self, message):
        """失败了：清干净现场（副本、半个记录、半个向量），再报信。"""
        # 副本文件（如果已经复制了）
        if getattr(self, "_copy_path", None) is not None:
            try:
                Path(self._copy_path).unlink(missing_ok=True)
            except OSError:
                pass
        # 数据库记录（如果已经登记了）——删记录会把容量还回去
        if getattr(self, "_file_id", None) is not None:
            try:
                self.db.xhangge_delete_kb_file(self._file_id)
            except Exception:
                pass
        # 已经存进 Chroma 的向量（按 file_id 精确清掉）
        if getattr(self, "_file_id", None) is not None:
            try:
                kb = self.db.xhangge_get_kb(self.kb_id)
                if kb is not None:
                    coll = _xhangge_get_collection(kb, create=False)
                    if coll is not None:
                        coll.delete(where={"xhangge_file_id": self._file_id})
            except Exception:
                pass
        self.import_finished.emit(False, message)

    def run(self):
        # ---- 0. 基本检查 ----
        if not self.file_path.exists():
            self._fail("找不到这个文件喵：" + str(self.file_path))
            return
        ext = self.file_path.suffix.lower()
        if ext not in xhangge_config.XHANGGE_ALLOWED_DOC_EXTS:
            self._fail(
                "只支持这些格式喵："
                + " / ".join(xhangge_config.XHANGGE_ALLOWED_DOC_EXTS)
                + "（收到的是 " + (ext or "没有扩展名") + "）"
            )
            return
        size = self.file_path.stat().st_size
        ok, remain = self.db.xhangge_kb_has_room(self.kb_id, size)
        if not ok:
            self._fail(
                "这个知识库装不下了喵 😿\n\n"
                "单个知识库上限 "
                + f"{xhangge_config.XHANGGE_MAX_KB_BYTES / 1024 / 1024:.0f}MB，"
                + f"现在只剩 {remain / 1024 / 1024:.1f}MB，"
                + f"这个文件要 {size / 1024 / 1024:.1f}MB。\n"
                "可以先删掉一些旧文件腾地方喵～"
            )
            return

        # ---- 1. 复制副本（原始文件永远不动，只动我们的副本）----
        self.import_progress.emit(-1, "正在复制文件喵…")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 副本名 = 时间戳 + 文件id位置 + 原名：时间戳防重名
        copy_dir = xhangge_config.XHANGGE_KB_FILES_DIR
        copy_dir.mkdir(parents=True, exist_ok=True)
        self._copy_path = str(copy_dir / (stamp + "_" + self.file_path.name))
        try:
            shutil.copy2(self.file_path, self._copy_path)
        except OSError as e:
            self._fail("复制文件失败喵 😿\n" + str(e))
            return

        # ---- 2. 解析成纯文字 ----
        self.import_progress.emit(-1, "正在读取内容喵…")
        try:
            text = xhangge_parse_file(self.file_path)
        except Exception as e:
            self._fail(
                "这个文件读不出来喵 😿\n\n"
                "常见原因：\n1. 文件加密或损坏\n2. PDF 是扫描图片（没有文字层）\n\n"
                "（" + type(e).__name__ + "）"
            )
            return
        # 解析这一步也可能很慢（大 PDF），点取消后这里就该停
        if self._stop_requested:
            self._fail("导入被取消了喵～（半成品已清理干净）")
            return
        if not text.strip():
            self._fail("文件里没有读到文字喵（扫描版 PDF 会这样，需要 OCR 才行）")
            return

        # ---- 3. 切块 ----
        self.import_progress.emit(-1, "正在切块喵…")
        chunks = xhangge_chunk_text(text)
        if self._stop_requested:
            self._fail("导入被取消了喵～（半成品已清理干净）")
            return
        if not chunks:
            self._fail("切块后没有内容喵")
            return
        # 读到了多少字、切成几块，让用户知道进度在往前走（而不是干等）
        self.import_progress.emit(
            -1, f"读到了 {len(text)} 个字，切成 {len(chunks)} 块，开始向量化喵…"
        )

        # ---- 3.5 向量化前先快速探一下 Ollama 在不在 ----
        # 不在就直接失败，别去初始化 Chroma、也别登记文件——用户要的是
        # "几秒内知道 Ollama 没开"，而不是卡十几秒看到一堆半成品。
        if not _xhangge_ollama_alive():
            self._fail(
                "连不上 Ollama 喵 😿\n\n"
                "向量化用的是本地模型 " + xhangge_config.XHANGGE_EMBED_MODEL
                + "，需要 Ollama 开着喵。\n"
                "终端里运行：ollama serve"
            )
            return

        # ---- 4. 先登记文件，拿到 file_id ----
        # file_id 必须先拿到：它要写进每个块的 metadata，
        # 将来删文件时才能 where={"xhangge_file_id": id} 精确清向量。
        # 块数此刻还不知道，先记 0，全部存完再回填真实值。
        self._file_id = self.db.xhangge_add_kb_file(
            self.kb_id, self.file_path.name, self._copy_path, size, 0
        )
        # 文件登记好了 → 通知界面刷新容量条和文件列表（不用等导入结束）
        self.file_registered.emit()

        # ---- 5. 分批向量化 + 存进 Chroma ----
        kb = self.db.xhangge_get_kb(self.kb_id)
        if kb is None:
            self._fail("知识库不存在了喵（可能刚被删除）")
            return
        coll = _xhangge_get_collection(kb, create=True)

        embedder = _xhangge_make_embedding()
        total = len(chunks)
        stored = 0
        try:
            for i in range(0, total, xhangge_config.XHANGGE_EMBED_BATCH):
                if self._stop_requested:
                    self._fail("导入被取消了喵～（半成品已清理干净）")
                    return
                batch = chunks[i : i + xhangge_config.XHANGGE_EMBED_BATCH]
                # 一次性把这一批都变成向量
                vectors = embedder.get_text_embedding_batch(batch)
                # 每块一个独立的 id（库id-文件id-第几块），永不重复
                ids = [
                    f"xhangge_c_{self._file_id}_{i + j}"
                    for j in range(len(batch))
                ]
                # metadata 带 file_id：删除的"精确制导"就靠它
                metas = [
                    {
                        "xhangge_kb_id": self.kb_id,
                        "xhangge_file_id": self._file_id,
                        "xhangge_source": self.file_path.name,
                    }
                    for _ in batch
                ]
                coll.add(ids=ids, embeddings=vectors, documents=batch, metadatas=metas)
                stored += len(batch)
                percent = int(stored / total * 100)
                self.import_progress.emit(
                    percent, f"正在向量化喵 {stored}/{total} 块"
                )
        except (requests.exceptions.ConnectionError, ConnectionError):
            # 注意：llama-index 的 OllamaEmbedding 底层用 ollama 客户端（httpx），
            # Ollama 没开时抛的是内置的 ConnectionError（OSError 子类），
            # 不是 requests 的 ConnectionError——两个都要接住，别让用户看到一堆堆栈。
            self._fail(
                "连不上 Ollama 喵 😿\n\n"
                "向量化用的是本地模型 " + xhangge_config.XHANGGE_EMBED_MODEL
                + "，需要 Ollama 开着喵。\n"
                "终端里运行：ollama serve"
            )
            return
        except Exception as e:
            self._fail("向量化或入库时出错了喵 😿\n（" + type(e).__name__ + "）" + str(e)[:200])
            return

        # ---- 6. 回填真实块数，收工 ----
        self.db.xhangge_update_kb_file_chunks(self._file_id, stored)
        self.import_progress.emit(100, "导入完成喵！")
        self.import_finished.emit(
            True,
            f"「{self.file_path.name}」导入好了喵 🎉\n"
            f"切成 {stored} 块，全部向量化完成～",
        )


# ============================================================
# 删除（只动副本和向量，绝不碰用户原文件）
# ============================================================
def xhangge_delete_kb_file_everywhere(db, file_id):
    """彻底删掉知识库里的一个文件：向量 + 副本 + 数据库记录。"""
    f = db.xhangge_get_kb_file(file_id)
    if f is None:
        return
    # 1. Chroma 里这个文件的所有向量（按 file_id 精确命中，不会误删别的文件）
    kb = db.xhangge_get_kb(f.kb_id)
    if kb is not None:
        coll = _xhangge_get_collection(kb, create=False)
        if coll is not None:
            try:
                coll.delete(where={"xhangge_file_id": file_id})
            except Exception:
                pass
    # 2. 我们目录里的副本（只删 ~/.xh_snowcat/xhangge_kb_files/ 下面的，
    #    用户的原文件永远不碰）
    try:
        copy = Path(f.copy_path)
        if copy.parent == xhangge_config.XHANGGE_KB_FILES_DIR:
            copy.unlink(missing_ok=True)
    except OSError:
        pass
    # 3. 数据库记录（同时把容量还回去）
    db.xhangge_delete_kb_file(file_id)


def xhangge_delete_kb_everywhere(db, kb_id):
    """彻底删掉一整个知识库：所有向量 + 所有副本 + collection + 记录。

    数据库那边的级联删除会自动清掉文件记录和会话绑定关系。
    """
    # 1. 先把每个文件的磁盘副本删掉（记录删了就找不到副本路径了）
    for f in db.xhangge_list_kb_files(kb_id):
        try:
            copy = Path(f.copy_path)
            if copy.parent == xhangge_config.XHANGGE_KB_FILES_DIR:
                copy.unlink(missing_ok=True)
        except OSError:
            pass
    # 2. 删掉整个 Chroma collection（向量一锅端）
    kb = db.xhangge_get_kb(kb_id)
    if kb is not None:
        try:
            _xhangge_get_chroma().delete_collection(kb.collection_name)
        except Exception:
            pass  # collection 本来就不存在（空库）也当成功
    # 3. 删数据库记录（级联清掉文件记录和绑定）
    db.xhangge_delete_kb(kb_id)


# ============================================================
# 混合检索（向量 + 关键词）+ 本地大模型重排
# ============================================================
class _XhanggeBM25:
    """极简 Okapi BM25 关键词检索（稀疏召回），零第三方依赖。

    项目刻意控制依赖体积，BM25 评分公式就几十行，不值得为一个公式
    再引一个包进来。中文没有空格分词，这里把"每个汉字 + 相邻两字"
    都当 token，英文则按空格切小写单词——中英文都能做关键词召回。
    """

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self._docs = []
        self._df = {}
        self._avgdl = 0.0
        self._n = 0

    @staticmethod
    def _tokenize(text):
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        cjk = re.findall(r"[一-鿿]", text)
        tokens.extend(cjk)
        tokens.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
        return tokens

    def fit(self, corpus):
        self._docs = [self._tokenize(t) for t in corpus]
        self._n = len(self._docs)
        for toks in self._docs:
            for tok in set(toks):
                self._df[tok] = self._df.get(tok, 0) + 1
        total = sum(len(t) for t in self._docs)
        self._avgdl = total / self._n if self._n else 0.0

    def scores(self, query):
        """返回每个文档相对 query 的 BM25 分（列表，顺序同 corpus）。"""
        q_toks = self._tokenize(query)
        if self._n == 0 or not q_toks:
            return [0.0] * self._n
        out = []
        for toks in self._docs:
            dl = len(toks)
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            s = 0.0
            for t in set(q_toks):
                df = self._df.get(t, 0)
                if df == 0:
                    continue
                idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1.0)
                f = tf.get(t, 0)
                if f == 0:
                    continue
                denom = f + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
                s += idf * f * (self.k1 + 1.0) / denom
            out.append(s)
        return out


def _xhangge_rerank_by_llm(db, query, candidates):
    """用大模型对候选片段做二段重排（listwise，一次调用）。

    做法：把候选一次性全塞给模型，让它按相关度给每个片段打 0-10 分，
    再按分数重排。只做一次模型调用，避免逐个打分拖慢速度。

    兜底：模型没开、JSON 解析失败等任何异常，都原样返回（保持混合检索
    的顺序），绝不让"重排"这个优化环节把正常的检索搞崩。
    """
    if not candidates or len(candidates) <= 1:
        return candidates
    try:
        from config.xhangge_prompts import build_rerank_prompt
        from services.xhangge_llm_router import xhangge_get_llm

        # fresh=True：现造实例，避开缓存里的连接池（它绑在别的事件循环上，
        # Agent 场景下复用会报 Event loop is closed）。
        llm = xhangge_get_llm(db, streaming=False, fresh=True, temperature=0)
        prompt = build_rerank_prompt(query, candidates)
        reply = llm.invoke(prompt)
        text = getattr(reply, "content", None) or ""

        # 只取回复里第一个 [...] 当 JSON 数组
        m = re.search(r"\[[^\]]*\]", text)
        if not m:
            return candidates
        scores = json.loads(m.group(0))
        if not isinstance(scores, list):
            return candidates

        scored = []
        for i, c in enumerate(candidates):
            s = scores[i] if i < len(scores) and isinstance(scores[i], (int, float)) else 0.0
            scored.append((s, i, c))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [c for _, _, c in scored]
    except Exception:
        return candidates


# cross-encoder 重排模型缓存（首次加载后复用，避免每次检索都重载模型）
_xhangge_reranker = None


def _xhangge_cross_rerank(query, candidates):
    """用 bge-reranker 交叉编码器重排（点对点打分，比 LLM 打分更准）。

    需要 pip install sentence-transformers，且首次会下载模型。
    任何失败（没装依赖 / 没下模型 / 内存不够）都返回 None，调用方回退到 LLM 重排。
    """
    global _xhangge_reranker
    if len(candidates) <= 1:
        return candidates
    try:
        if _xhangge_reranker is None:
            from sentence_transformers import CrossEncoder

            _xhangge_reranker = CrossEncoder(
                xhangge_config.XHANGGE_RERANK_MODEL, max_length=512
            )
        pairs = [(query, c.text) for c in candidates]
        scores = _xhangge_reranker.predict(pairs)
        scored = sorted(zip(scores, candidates), key=lambda x: -x[0])
        return [c for _, c in scored]
    except Exception:
        return None


def xhangge_retrieve(db, query, kb_ids):
    """拿着用户的问题去绑定的知识库里找最相关的几段（混合检索 + 重排）。

    参数：
        query  —— 用户刚发出的那条消息
        kb_ids —— 这个会话绑定的知识库 id 列表
    返回：
        XhanggeRetrievedChunk 列表（已按相关度排序，最多 XHANGGE_TOP_K_FINAL 段）
        一个都没找到时返回空列表（调用方就当没用知识库，正常回答）

    检索流程（两路召回 → 融合 → 重排）：
    1. 向量召回（dense）：bge-m3 把问题算成向量，在 Chroma 里找最像的几段
    2. 关键词召回（sparse）：BM25 按字面词频找"出现相同词"的几段
    3. RRF 融合：两路各按名次打分再相加——既吃语义、又吃关键词
    4. 重排（rerank）：拿融合后的前几名，让大模型按相关度再精排一次
    """
    if not kb_ids or not query.strip():
        return []

    embedder = _xhangge_make_embedding()
    # 问题只需要向量化一次
    query_vec = embedder.get_query_embedding(query)

    # text -> [rrf_score, kb_name, file_name]，按 text 去重（同文只留一份）
    fused = {}
    for kb_id in kb_ids:
        kb = db.xhangge_get_kb(kb_id)
        if kb is None:
            continue  # 库刚被删了，跳过
        coll = _xhangge_get_collection(kb, create=False)
        if coll is None:
            continue  # 空库（一个文件都没导入过）
        try:
            data = coll.get(include=["documents", "metadatas"])
        except Exception:
            continue
        docs = data.get("documents") or []
        metas = data.get("metadatas") or [None] * len(docs)
        if not docs:
            continue

        # text -> 出处文件名（首个出现的为准；同文多份时内容一致，归属无所谓）
        text_meta = {}
        for doc, meta in zip(docs, metas):
            if doc not in text_meta:
                text_meta[doc] = (meta or {}).get("xhangge_source", "未知文件")

        # ---- 路一：向量召回（dense）----
        dense_texts = []
        try:
            res = coll.query(
                query_embeddings=[query_vec],
                n_results=min(xhangge_config.XHANGGE_DENSE_TOP_K, len(docs)),
                include=["documents"],
            )
            dense_texts = (res.get("documents") or [[]])[0]
        except Exception:
            dense_texts = []

        # ---- 路二：关键词召回（sparse / BM25）----
        sparse_texts = []
        try:
            bm25 = _XhanggeBM25()
            bm25.fit(docs)
            bm_scores = bm25.scores(query)
            order = sorted(range(len(docs)), key=lambda i: bm_scores[i], reverse=True)
            sparse_texts = [docs[i] for i in order[: xhangge_config.XHANGGE_SPARSE_TOP_K]]
        except Exception:
            sparse_texts = []

        # ---- RRF 融合：两路名次各贡献 1/(k+rank+1)，相加 ----
        k = xhangge_config.XHANGGE_RRF_K
        for rank, text in enumerate(dense_texts):
            if text in text_meta:
                fused.setdefault(text, [0.0, kb.name, text_meta[text]])[0] += 1.0 / (k + rank + 1)
        for rank, text in enumerate(sparse_texts):
            if text in text_meta:
                fused.setdefault(text, [0.0, kb.name, text_meta[text]])[0] += 1.0 / (k + rank + 1)

    if not fused:
        return []

    candidates = [
        XhanggeRetrievedChunk(
            text=text,
            score=val[0],
            kb_name=val[1],
            file_name=val[2],
        )
        for text, val in fused.items()
    ]
    candidates.sort(key=lambda c: c.score, reverse=True)

    # ---- 重排：融合后的前几名精排，池外的按融合分数跟在后面 ----
    # 按配置选重排方式：cross_encoder（更准）或 LLM（开箱即用），失败自动回退 LLM。
    if xhangge_config.XHANGGE_RERANK_ENABLED:
        pool = candidates[: xhangge_config.XHANGGE_RERANK_POOL]
        if xhangge_config.XHANGGE_RERANK_MODE == "cross_encoder":
            reranked = _xhangge_cross_rerank(query, pool)
            pool = (
                reranked
                if reranked is not None
                else _xhangge_rerank_by_llm(db, query, pool)
            )
        else:
            pool = _xhangge_rerank_by_llm(db, query, pool)
        candidates = pool + candidates[xhangge_config.XHANGGE_RERANK_POOL:]

    return candidates[: xhangge_config.XHANGGE_TOP_K_FINAL]
