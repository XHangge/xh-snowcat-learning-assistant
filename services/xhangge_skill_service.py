# Author: xhangge
# This project is created by xhangge
"""
xhangge_skill_service —— 学习文档 Skill（模块四）的逻辑层

这个 Skill 是干嘛的：把「刚才聊过的内容」变成可以复习的学习资料。
两种产物、四个档位：
    doc        普通学习文档（Markdown 结构化知识总结）
    qa_shallow 浅浅学喵问答集（10-20 题）
    qa_medium  中中学喵问答集（20-30 题）
    qa_deep    重重学喵问答集（30-50 题）

两种触发方式：
    1. 按钮：聊天区输入框上方的「📖 学习文档喵」按钮 → 弹菜单选档位
    2. 关键词：用户消息里出现「学习文档 / 浅浅学喵 / 中中学喵 / 重重学喵」等词

这个文件只管「判断和组装」，不管界面也不管线程：
- 识别关键词 → xhangge_detect_skill()
- 组装发给模型的消息 → build_skill_messages()
- 真正调模型还是复用 services/xhangge_chat_service.py 的线程，
  因为对模型来说这就是一次普通的流式请求，只是提示词不同。
"""

from config import xhangge_settings as xhangge_config
from config.xhangge_prompts import (
    SKILL_FINAL_INSTRUCTIONS,
    build_skill_system_prompt,
)

# ============================================================
# 关键词表
# ============================================================
# 用户消息里出现哪个词 → 触发哪个技能。
# 按列表顺序匹配，先命中先用（所以把更具体的词放在前面）。
#
# 为什么这些词可以放心当触发词：
# 「浅浅学喵」「中中学喵」「重重学喵」是我们自己造的词，
# 正常聊天里不会莫名其妙出现；「学习文档」「生成文档」
# 出现时用户几乎不可能是想干别的。
XHANGGE_SKILL_KEYWORDS = [
    ("qa_shallow", ("浅浅学喵", "浅浅学")),
    ("qa_medium", ("中中学喵", "中中学")),
    ("qa_deep", ("重重学喵", "重重学")),
    ("doc", ("学习文档", "生成文档", "整理成文档", "整理一份文档")),
]

# ============================================================
# 技能档案表（界面显示、写数据库都查这里）
# ============================================================
# (技能标识, 菜单上显示的名字, 写进数据库的类型, 写进数据库的档位)
# skill_type / depth 两个值要和 models/xhangge_db.py 的
# xhangge_add_skill_task() 注释里约定的取值一致。
XHANGGE_SKILL_MENU = [
    ("doc", "📄 普通学习文档喵", "doc", None),
    ("qa_shallow", "🌸 浅浅学喵 · 10-20题", "qa", "shallow"),
    ("qa_medium", "📖 中中学喵 · 20-30题", "qa", "medium"),
    ("qa_deep", "🎓 重重学喵 · 30-50题", "qa", "deep"),
]

# 技能标识 → (数据库里的 skill_type, 数据库里的 depth)
# 记流水（xhangge_skill_tasks 表）时用。
XHANGGE_SKILL_DB_TYPES = {key: (s_type, depth) for key, _, s_type, depth in XHANGGE_SKILL_MENU}


def xhangge_detect_skill(text):
    """看一眼用户消息，判断是不是在喊学习技能。

    参数 text：用户发出的消息原文
    返回：
        命中了 → 技能标识（"doc" / "qa_shallow" / ...）
        没命中 → None（调用方就按普通聊天走）
    """
    if not text:
        return None
    for skill_key, words in XHANGGE_SKILL_KEYWORDS:
        for word in words:
            if word in text:
                return skill_key
    return None


def xhangge_get_skill_label(skill_key):
    """拿某个技能在菜单上显示的名字（生成气泡提示时用）。"""
    for key, label, _, _ in XHANGGE_SKILL_MENU:
        if key == skill_key:
            return label
    return skill_key


def build_skill_messages(history, skill_key, username=""):
    """为一次技能生成组装完整的消息列表。

    参数：
        history   —— 本会话的历史消息，格式和数据库里一样：
                     [{"role": "user"/"assistant", "content": "..."}, ...]
        skill_key —— 技能标识
        username  —— 用户昵称（拼进人设用）

    返回：
        [{"role": "system", "content": 人设+技能任务书},
         ...最近 N 条历史（原样带上，模型才知道聊过什么）...,
         {"role": "user", "content": 开工指令}]

    为什么最后要补一条"开工指令"：
    历史发过去后，模型的本能是接着聊天（回答最后一句话）。
    追加一条明确的指令，把它的注意力拽到"开始生成文档"上来，
    这比在系统提示词里说一百遍"你的唯一任务是"都管用。
    """
    system_prompt = build_skill_system_prompt(skill_key, username)

    messages = [{"role": "system", "content": system_prompt}]
    # 只带最近 N 条，太久的聊天和当前主题基本无关（N 在配置文件里调）
    recent = history[-xhangge_config.XHANGGE_SKILL_CONTEXT_MESSAGES:]
    for msg in recent:
        messages.append({"role": msg["role"], "content": msg["content"]})
    # 开工指令放最后
    messages.append({
        "role": "user",
        "content": SKILL_FINAL_INSTRUCTIONS.get(skill_key, "请开始生成喵。"),
    })
    return messages
