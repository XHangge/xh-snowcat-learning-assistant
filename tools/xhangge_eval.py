# Author: xhangge
# This project is created by xhangge
"""
xhangge_eval —— RAG 检索召回率评测脚本

用法：
    # 无 Ollama 时用 mock 嵌入跑通流程（数字是"流程自检"，不代表真实语义召回）
    python tools/xhangge_eval.py

    # 有 Ollama + bge-m3 时，用真实向量模型评测（这才是有效数字）
    python tools/xhangge_eval.py --real

评测什么：
    把语料切成块 → 对每个问题做「向量召回 + BM25 关键词召回 + RRF 融合」，
    检查"正确答案块"有没有被检索到，算出：
        recall@k（k=1/3/5/10）：正确答案出现在前 k 个结果里的题目占比
        MRR：正确答案首次出现位置的倒数平均（越接近 1 越好）
"""

import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import xhangge_settings as xhangge_config
from services.xhangge_kb_service import _XhanggeBM25, xhangge_chunk_text
from tools.xhangge_eval_data import CORPUS, QA


# ============================================================
# 嵌入：mock（跑通流程） / 真实 bge-m3（有效评测）
# ============================================================
def _mock_embed(text):
    """字符 bigram 哈希成 256 维向量（确定性，只用来跑通评测流程）。"""
    vec = [0.0] * 256
    t = text.lower()
    for i in range(len(t) - 1):
        vec[(ord(t[i]) * 131 + ord(t[i + 1])) % 256] += 1.0
    for ch in t:
        vec[ord(ch) % 256] += 0.5
    return vec


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _make_real_embedder():
    from services.xhangge_kb_service import _xhangge_make_embedding

    embedder = _xhangge_make_embedding()

    def embed(texts):
        if isinstance(texts, str):
            return embedder.get_query_embedding(texts)
        return embedder.get_text_embedding_batch(texts)

    return embed


# ============================================================
# 检索（和 services/xhangge_kb_service.py 的混合检索一致）
# ============================================================
def _retrieve(chunk_texts, chunk_vecs, query, query_vec):
    """对 chunk_texts 做 向量+BM25+RRF，返回按得分降序的块下标列表。"""
    dense_top = xhangge_config.XHANGGE_DENSE_TOP_K
    sparse_top = xhangge_config.XHANGGE_SPARSE_TOP_K
    k = xhangge_config.XHANGGE_RRF_K

    # 向量召回（用预计算好的块向量）
    sims = [_cosine(query_vec, cv) for cv in chunk_vecs]
    dense_order = sorted(range(len(chunk_texts)), key=lambda i: sims[i], reverse=True)
    dense_ranked = dense_order[:dense_top]

    # BM25 关键词召回
    bm25 = _XhanggeBM25()
    bm25.fit(chunk_texts)
    bm_scores = bm25.scores(query)
    sparse_order = sorted(range(len(chunk_texts)), key=lambda i: bm_scores[i], reverse=True)
    sparse_ranked = sparse_order[:sparse_top]

    # RRF 融合
    rrf = {}
    for rank, idx in enumerate(dense_ranked):
        rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (k + rank + 1)
    for rank, idx in enumerate(sparse_ranked):
        rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (k + rank + 1)

    return sorted(rrf.keys(), key=lambda i: rrf[i], reverse=True)


def main():
    use_real = "--real" in sys.argv

    # 1. 切块（按"一句一个知识点"切，得到约 100 块，才能真实区分检索准不准）
    chunks = []
    for title, text in CORPUS:
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[。！？；.!?;])", text)
            if s.strip()
        ]
        for s in sentences:
            chunks.append((title, s))
    chunk_texts = [c for _, c in chunks]
    print(f"语料文档 {len(CORPUS)} 篇，按句子切出 {len(chunks)} 块")

    # 2. 准备嵌入
    if use_real:
        print("使用真实向量模型 bge-m3（需 Ollama 运行）…")
        embed = _make_real_embedder()
        # 预先把所有块向量化（真实模型较慢，一次算完）
        print("正在向量化全部块，请稍候…")
        chunk_vecs = embed(chunk_texts)
    else:
        print("使用 mock 嵌入（无 Ollama，仅验证评测流程）")
        embed = None
        chunk_vecs = [_mock_embed(t) for t in chunk_texts]

    # 3. 逐题评测
    k_values = [1, 3, 5, 10]
    recall_hits = {k: 0 for k in k_values}
    reciprocal_sum = 0.0
    valid = 0
    missed_gt = 0

    for question, answer in QA:
        # 找正确答案块：包含答案片段的块
        gt_idx = None
        for i, t in enumerate(chunk_texts):
            if answer in t:
                gt_idx = i
                break
        if gt_idx is None:
            missed_gt += 1
            continue

        valid += 1
        if use_real:
            qv = embed(question)
        else:
            qv = _mock_embed(question)
        ranked = _retrieve(chunk_texts, chunk_vecs, question, qv)

        # 正确答案首次出现在第几位（1 起）
        rank = None
        for pos, idx in enumerate(ranked, start=1):
            if idx == gt_idx:
                rank = pos
                break
        for k in k_values:
            if rank is not None and rank <= k:
                recall_hits[k] += 1
        if rank is not None:
            reciprocal_sum += 1.0 / rank

    # 4. 出报告
    print("\n===== 检索召回评测结果 =====")
    print(f"有效题目：{valid} / {len(QA)}（答案片段没匹配到块的题：{missed_gt}）\n")
    for k in k_values:
        r = recall_hits[k] / valid if valid else 0.0
        print(f"Recall@{k:>2} : {r:.3f}  ({recall_hits[k]}/{valid})")
    mrr = reciprocal_sum / valid if valid else 0.0
    print(f"\nMRR      : {mrr:.3f}")
    print("（Recall@k = 正确答案出现在前 k 个结果里的题目占比；MRR 越接近 1 越准）")


if __name__ == "__main__":
    main()
