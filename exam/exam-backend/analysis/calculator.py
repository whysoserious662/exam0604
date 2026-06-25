import numpy as np
from collections import defaultdict

def calc_discrimination(scores, max_scores):
    """
    区分度 = 高分组平均得分率 - 低分组平均得分率 (27%分组法)
    D >= 0.4 优秀, 0.3~0.4 良好, 0.2~0.3 一般, <0.2 不足
    """
    rates = np.array([s / m if m > 0 else 0 for s, m in zip(scores, max_scores)])
    if len(rates) < 10:
        return 0
    n = len(rates)
    k = max(int(n * 0.27), 1)
    idx = np.argsort(rates)
    low_avg = np.mean(rates[idx[:k]])
    high_avg = np.mean(rates[idx[-k:]])
    return round(high_avg - low_avg, 4)

def calc_knowledge_mastery(records):
    """知识点掌握率：按 knowledge_id 分组计算平均得分率"""
    groups = defaultdict(list)
    for r in records:
        kid = r.get("knowledge_id", 0)
        rate = r["score"] / r["max_score"] if r["max_score"] > 0 else 0
        groups[kid].append(rate)
    return {k: round(float(np.mean(v)), 4) for k, v in groups.items()}

def calc_score_distribution(scores, max_score, bins=10):
    """成绩分布直方图数据 — 从 0 到 max_score 等分为 bins 个区间"""
    arr = np.array(scores)
    if len(arr) == 0 or max_score <= 0:
        return []
    bin_width = max_score / bins
    bin_edges = [i * bin_width for i in range(bins + 1)]
    counts, _ = np.histogram(arr, bins=bin_edges)
    return [
        {"range_start": round(float(bin_edges[i]), 1),
         "range_end": round(float(bin_edges[i + 1]), 1),
         "count": int(counts[i])}
        for i in range(bins)
    ]

def full_analysis(records, question_info=None):
    """
    完整试卷分析
    records: [{student_id, score, max_score, knowledge_id, question_number}, ...]
    question_info: {question_number: {difficulty, knowledge_id, content, ...}, ...}
    """
    if not records:
        return {}

    n_students = len(set(r["student_id"] for r in records))
    n_questions = len(set(r["question_number"] for r in records))

    # 按题目分组
    question_scores = defaultdict(list)
    question_max = {}
    for r in records:
        question_scores[r["question_number"]].append(r["score"])
        question_max[r["question_number"]] = r["max_score"]

    # 每题分析
    question_analysis = []
    all_item_scores = []
    all_item_max = []
    for qnum in sorted(question_scores.keys()):
        sc_list = question_scores[qnum]
        m_sc = question_max[qnum]
        score_rate = round(float(np.mean(sc_list)) / m_sc, 4) if m_sc > 0 else 0
        disc = calc_discrimination(sc_list, [m_sc] * len(sc_list))
        avg_score = round(float(np.mean(sc_list)), 2)

        # 使用预设难度（来自 Question 表）
        preset_diff = None
        if question_info and qnum in question_info:
            preset_diff = question_info[qnum].get("difficulty")

        suggestion = _suggestion(disc)
        question_analysis.append({
            "question_number": qnum,
            "max_score": m_sc,
            "avg_score": avg_score,
            "score_rate": score_rate,
            "preset_difficulty": preset_diff,
            "discrimination": disc,
            "suggestion": suggestion
        })
        all_item_scores.append(sc_list)
        all_item_max.append(m_sc)

    # 学生总分
    student_totals = defaultdict(float)
    for r in records:
        student_totals[r["student_id"]] += r["score"]
    student_scores_list = list(student_totals.values())

    # 整体得分率
    total_rate = round(float(np.mean(student_scores_list)) / sum(question_max.values()), 4) if student_scores_list and sum(question_max.values()) else 0

    # 知识点掌握
    knowledge_mastery = calc_knowledge_mastery(records)

    # 成绩分布（从 0 到满分等分）
    score_distribution = calc_score_distribution(student_scores_list, max_score=float(sum(question_max.values())))

    return {
        "student_count": n_students,
        "question_count": n_questions,
        "total_possible": float(sum(question_max.values())),
        "avg_score": round(float(np.mean(student_scores_list)), 2),
        "avg_score_rate": total_rate,
        "question_analysis": question_analysis,
        "knowledge_mastery": knowledge_mastery,
        "score_distribution": score_distribution
    }

def _suggestion(disc):
    if disc >= 0.4:
        return "区分度优秀，能很好区分学生水平"
    elif disc >= 0.3:
        return "区分度良好，建议保留"
    elif disc >= 0.2:
        return "区分度一般，可考虑调整"
    return "区分度不足，建议修改或淘汰"
