# Author: xhangge
# This project is created by xhangge
"""
xhangge_schemas —— 层与层之间传数据用的结构定义

为什么需要这个文件：
如果各层之间直接传裸字典（dict），谁也说不清里面到底有哪些字段，
写代码时全靠记忆，拼错一个键名就是一个隐蔽的 bug。
用 dataclass 定义好结构后，字段名写错会立刻报错，
编辑器也能自动提示有哪些字段，省心很多喵。

这些类只是"数据的容器"，不含任何业务逻辑。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class XhanggeKbInfo:
    """一个知识库的元信息（不含向量，向量在 Chroma 里）"""
    id: int
    name: str                 # 知识库名字，用户自己起的
    collection_name: str      # 对应的 Chroma collection 名（xhangge_kb_<id>）
    used_bytes: int           # 已经用掉多少字节（用来算容量条和判断超限）
    created_at: str
    file_count: int = 0       # 里面有几个文件（列表页显示用）

    @property
    def used_mb(self):
        """已用容量换算成 MB，方便界面直接显示"""
        return self.used_bytes / 1024 / 1024


@dataclass
class XhanggeKbFile:
    """知识库里的一个文件"""
    id: int
    kb_id: int                # 属于哪个知识库
    file_name: str            # 原始文件名（显示给用户看）
    copy_path: str            # 副本的绝对路径（在 ~/.xh_snowcat/xhangge_kb_files/ 下）
    size_bytes: int
    chunk_count: int          # 被切成了多少个知识块
    imported_at: str

    @property
    def size_mb(self):
        return self.size_bytes / 1024 / 1024


@dataclass
class XhanggeModelConfig:
    """一个在线大模型 API 的配置（通义千问 / DeepSeek 等）"""
    id: int
    name: str                 # 用户起的名字，如"我的DeepSeek"
    base_url: str             # 接口地址
    api_key: str              # 密钥（界面上用密码框输入，日志里永不打印）
    model_name: str           # 模型名，如 deepseek-chat
    is_active: bool           # 是不是当前正在用的那个
    created_at: str = ""


@dataclass
class XhanggeRetrievedChunk:
    """从知识库检索出来的一个片段"""
    text: str                 # 片段正文
    score: float              # 相似度得分（越大越相关）
    kb_name: str              # 来自哪个知识库
    file_name: str            # 来自哪个文件（用来显示"📎 参考：xxx.pdf"）


@dataclass
class XhanggeSessionState:
    """一个会话的"当前状态"，切换会话时用来恢复界面

    这三样东西都是每个会话独立记忆的：
    - 是 Chat 模式还是 Agent 模式
    - 知识库检索开关开没开
    - 绑定了哪几个知识库
    """
    session_id: int
    chat_mode: str = "chat"           # chat / agent
    rag_enabled: bool = False         # 检索开关
    kb_ids: List[int] = field(default_factory=list)  # 绑定的知识库 id 列表（最多 3 个）
