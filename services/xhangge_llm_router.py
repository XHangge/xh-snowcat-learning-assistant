# Author: xhangge
# This project is created by xhangge
"""
xhangge_llm_router —— 模型路由（整个软件的"电源总闸"）

它解决一个问题：软件里有四个地方要用大模型
（普通聊天、Agent、知识库问答、生成学习文档），
不能每处都自己去连模型，否则用户换个后端就要改四处。

所以统一在这里造模型实例，别处都来这里取：
    llm = xhangge_get_llm()

【本地和在线是互斥的，只能选一个】
用户在设置里要么用本地 Ollama，要么用某一份在线 API 配置。
数据库 xhangge_model_configs 表里 is_active 恒定只有一行是 1，
这里就按它来决定造哪种模型。

【为什么统一用 LangChain 的 ChatModel 接口】
本地 Ollama 和在线的 DeepSeek/通义千问，原生 SDK 各不相同。
LangChain 把它们都包装成同一个接口（都有 .invoke() 和 .stream()），
所以上层代码完全不用关心"现在连的到底是谁"，换后端不用改一行。

【热切换怎么实现】
把造好的模型实例缓存起来（_xhangge_llm_cache）。
用户在设置里一改后端，就调 xhangge_reload_llm() 把缓存清掉，
下一次取模型时自然会按新配置重新造一个。不需要重启软件。
"""

from config import xhangge_settings as xhangge_config

# 缓存造好的模型实例。
# 为什么要缓存：每次造实例都要初始化 HTTP 客户端，
# 聊天时一句话造一次太浪费。缓存后只在切换后端时重建。
_xhangge_llm_cache = None
# 缓存对应的"配置指纹"，用来判断配置有没有变过
_xhangge_cache_key = None


def _xhangge_build_config_key(active_cfg, local_model):
    """给当前配置算一个"指纹"。

    指纹一样就说明配置没变，可以继续用缓存里的实例；
    指纹变了（用户换了后端、改了模型名、换了 Key）就要重建。
    """
    if active_cfg is None:
        return ("local", local_model, xhangge_config.OLLAMA_BASE_URL)
    return ("online", active_cfg.base_url, active_cfg.model_name, active_cfg.api_key)


def xhangge_get_llm(db, streaming=True, fresh=False, temperature=0.7):
    """拿到当前该用的模型实例（全项目唯一入口）。

    参数：
        db          —— 数据库对象，用来查"现在激活的是哪个后端"
        streaming   —— 是否需要流式输出（聊天要，后台批量生成不需要）
        fresh       —— True：现造一个全新的实例，不读也不写缓存。
                       Agent 模式必须用 True，原因见下方注释。
        temperature —— 随机性。聊天用默认 0.7（活泼）；
                       Agent 任务建议传 0（要的是稳定地调工具，不是文采）

    返回：
        一个 LangChain ChatModel 对象，有 .invoke() 和 .stream() 方法

    这段在干什么：
    1. 查数据库，看用户选的是本地还是某份在线配置
    2. 算配置指纹，和缓存对比；一样就直接返回缓存的实例
    3. 不一样就按新配置造一个新的，存进缓存再返回
    """
    global _xhangge_llm_cache, _xhangge_cache_key

    active_cfg = db.xhangge_get_active_model_config()
    settings = xhangge_config.load_xhangge_settings()
    local_model = settings.get("local_model", xhangge_config.XHANGGE_MODEL_NAME)

    # fresh=True：Agent 每次任务都现造一个。
    # 为什么 Agent 不能用缓存：Agent 在后台线程里用 asyncio 跑，
    # 每次任务的 asyncio 事件循环都是新建的、跑完就关。
    # 而缓存里的实例内部抱着 httpx 的连接池，那些连接绑死在
    # 第一次的循环上——第二次任务一用就报 "Event loop is closed"
    # （真踩过的坑：第一次好好的，第二次必炸）。
    # 现造实例 = 新连接池绑新循环，天然没这个问题。
    if fresh:
        return _xhangge_build_llm(active_cfg, local_model, streaming, temperature)

    key = _xhangge_build_config_key(active_cfg, local_model)
    # 指纹没变 → 复用缓存，省掉重复初始化
    if _xhangge_llm_cache is not None and _xhangge_cache_key == key:
        return _xhangge_llm_cache

    llm = _xhangge_build_llm(active_cfg, local_model, streaming)
    _xhangge_llm_cache = llm
    _xhangge_cache_key = key
    return llm


def _xhangge_build_llm(active_cfg, local_model, streaming=True, temperature=0.7):
    """按配置造一个 LangChain ChatModel 实例（本地 Ollama 或在线 API）。"""
    if active_cfg is None:
        # ---- 情况一：用本地 Ollama ----
        # 延迟导入（import 放在函数里）：这些库加载要一两秒，
        # 放在文件顶部会拖慢软件启动速度。
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=local_model,
            base_url=xhangge_config.OLLAMA_BASE_URL,
            # temperature 控制"随机性"：值越大回答越天马行空。
            # 聊天 0.7 兼顾准确和活泼；Agent 任务传 0，稳定调工具。
            temperature=temperature,
        )
    # ---- 情况二：用在线 API ----
    # 用 ChatOpenAI 而不是各家自己的 SDK，是因为
    # DeepSeek、通义千问、月之暗面等国内厂商都提供了
    # "OpenAI 兼容接口"，填对 base_url 就能通用。
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=active_cfg.model_name,
        base_url=active_cfg.base_url,
        api_key=active_cfg.api_key,
        temperature=temperature,
        streaming=streaming,
    )


def xhangge_reload_llm():
    """清空缓存，强制下次重新造模型实例。

    用户在设置窗口里切换后端 / 改模型名 / 换 API Key 之后调用它。
    因为下一次 xhangge_get_llm() 会发现缓存已空而重新构建，
    所以切换后端不需要重启软件（热切换）。
    """
    global _xhangge_llm_cache, _xhangge_cache_key
    _xhangge_llm_cache = None
    _xhangge_cache_key = None


def xhangge_get_backend_label(db):
    """返回当前后端的可读名称，显示在界面上让用户一眼知道在用谁。

    例如："本地 qwen2.5:7b" 或 "在线 · 我的DeepSeek"
    """
    active_cfg = db.xhangge_get_active_model_config()
    if active_cfg is None:
        settings = xhangge_config.load_xhangge_settings()
        model = settings.get("local_model", xhangge_config.XHANGGE_MODEL_NAME)
        return f"本地 {model}"
    return f"在线 · {active_cfg.name}"


def xhangge_to_langchain_messages(messages):
    """把我们自己的消息格式转成 LangChain 的消息对象。

    我们数据库里存的是最朴素的字典：
        [{"role": "user", "content": "你好"}, ...]
    而 LangChain 要求用 SystemMessage / HumanMessage / AIMessage 三种对象。
    这个函数就是做这层翻译。

    为什么不直接传字典：LangChain 新版对消息类型做了严格校验，
    传对象能避免不同模型厂商之间的格式差异导致的诡异问题。
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    result = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            # 其它情况都当成用户说的话（user 或未知角色）
            result.append(HumanMessage(content=content))
    return result


def xhangge_test_online_config(base_url, api_key, model_name, timeout=20):
    """测试一份在线 API 配置能不能用（设置窗口的"🔌 测试连接喵"按钮）。

    做法：造一个临时实例，让模型回一个字，能回就说明通了。
    注意这个函数会阻塞几秒，所以界面上要放到后台线程里调用。

    返回 (成功了吗, 给用户看的消息)
    """
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=api_key,
            temperature=0,
            timeout=timeout,
            max_retries=0,   # 测试连接不重试，失败就立刻告诉用户
        )
        reply = llm.invoke("回复一个字：喵")
        text = (reply.content or "").strip()
        return True, f"连上啦喵！模型回了：{text[:30]}"
    except Exception as e:
        # 这里故意捕获所有异常：网络、鉴权、模型名错误等情况太多，
        # 统一转成一句友好提示给用户，而不是抛一堆看不懂的堆栈。
        # 注意只展示异常类型和简短信息，绝不把 API Key 打印出来。
        msg = str(e)
        if len(msg) > 160:
            msg = msg[:160] + "…"
        return False, f"连不上喵 😿（{type(e).__name__}）{msg}"
