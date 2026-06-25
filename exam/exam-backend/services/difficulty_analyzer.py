"""
双维度难度评估模块 — 阶段1：NLP静态文本特征分析

基于 textstat 提取可读性指标，融合为 1-5 级难度分。
后续阶段接入 Elo 动态调整和 AI 大模型评估。
"""
import re
import math
import textstat


# ── 指标提取 ──────────────────────────────────────────────

def extract_english_text(content, question_type=None):
    """从混合内容中提取纯英文部分。翻译题保留中文源文本。"""
    content = re.sub(r'【.*?】', '', content)
    content = re.sub(r'https?://\S+', '', content)
    content = re.sub(r'Part\s+(I|II|III|IV|V|VI+)', '', content)
    content = re.sub(r'Questions?\s*\d+\s*(to|and)\s*\d+\s*are\s*based', '', content, flags=re.I)

    if question_type == "翻译":
        # 保留中文源文本，仅过滤格式噪声
        content = re.sub(r'\(\d+\s*minutes?\)', '', content, flags=re.I)
        content = re.sub(r'Directions?\s*:\s*For this part.*?English\.', '', content, flags=re.I | re.DOTALL)
        content = re.sub(r'You should write.*?Sheet \d\.', '', content, flags=re.I | re.DOTALL)
    else:
        content = re.sub(r'[一-鿿]+', '', content)

    return content.strip()


def compute_text_features(text):
    """提取所有文本可读性特征"""
    if not text or len(text.split()) < 10:
        return None

    features = {}

    # 基础统计
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if len(s.split()) > 1]

    features["word_count"] = len(words)
    features["sentence_count"] = len(sentences) if sentences else 1
    features["avg_sentence_length"] = features["word_count"] / max(features["sentence_count"], 1)

    # 词汇复杂度
    char_count = sum(len(w) for w in words)
    features["avg_word_length"] = char_count / max(features["word_count"], 1)

    syllable_count = textstat.syllable_count(text)
    features["total_syllables"] = syllable_count
    features["avg_syllables_per_word"] = syllable_count / max(features["word_count"], 1)

    # 复杂词占比（≥3音节）
    complex_words = sum(1 for w in words if textstat.syllable_count(w) >= 3)
    features["complex_word_ratio"] = complex_words / max(features["word_count"], 1)

    # ═══ 核心可读性指标 ═══
    features["flesch_reading_ease"] = textstat.flesch_reading_ease(text)
    features["flesch_kincaid_grade"] = textstat.flesch_kincaid_grade(text)
    features["gunning_fog"] = textstat.gunning_fog(text)
    features["smog_index"] = textstat.smog_index(text)
    features["automated_readability_index"] = textstat.automated_readability_index(text)
    features["coleman_liau_index"] = textstat.coleman_liau_index(text)
    features["dale_chall_readability_score"] = textstat.dale_chall_readability_score(text)
    features["linsear_write_formula"] = textstat.linsear_write_formula(text)

    # 词汇多样性 (Type-Token Ratio)
    unique_words = set(w.lower() for w in words)
    features["type_token_ratio"] = len(unique_words) / max(features["word_count"], 1)

    return features


# ── 难度评分 ──────────────────────────────────────────────

def features_to_difficulty(features, question_type):
    """
    将文本特征映射为 1-5 难度分。
    针对不同题型采用不同权重策略。
    """
    if features is None:
        return {"difficulty": "3", "level": "中等", "confidence": 0.0, "metrics": {}}

    scores = {}

    # 1. Flesch Reading Ease → 难度映射 (0-100, 越低越难)
    fre = features["flesch_reading_ease"]
    if fre <= 30:
        scores["flesch"] = 5
    elif fre <= 50:
        scores["flesch"] = 4
    elif fre <= 65:
        scores["flesch"] = 3
    elif fre <= 80:
        scores["flesch"] = 2
    else:
        scores["flesch"] = 1

    # 2. Flesch-Kincaid Grade Level → 难度映射
    fkg = features["flesch_kincaid_grade"]
    if fkg >= 14:
        scores["grade"] = 5
    elif fkg >= 12:
        scores["grade"] = 4
    elif fkg >= 9:
        scores["grade"] = 3
    elif fkg >= 6:
        scores["grade"] = 2
    else:
        scores["grade"] = 1

    # 3. Gunning Fog → 难度映射
    gf = features["gunning_fog"]
    if gf >= 16:
        scores["fog"] = 5
    elif gf >= 13:
        scores["fog"] = 4
    elif gf >= 10:
        scores["fog"] = 3
    elif gf >= 7:
        scores["fog"] = 2
    else:
        scores["fog"] = 1

    # 4. 平均句长贡献
    asl = features["avg_sentence_length"]
    if asl >= 25:
        scores["sentence"] = 5
    elif asl >= 20:
        scores["sentence"] = 4
    elif asl >= 15:
        scores["sentence"] = 3
    elif asl >= 10:
        scores["sentence"] = 2
    else:
        scores["sentence"] = 1

    # 5. 词汇复杂度贡献
    cwr = features["complex_word_ratio"]
    if cwr >= 0.20:
        scores["vocab"] = 5
    elif cwr >= 0.15:
        scores["vocab"] = 4
    elif cwr >= 0.10:
        scores["vocab"] = 3
    elif cwr >= 0.06:
        scores["vocab"] = 2
    else:
        scores["vocab"] = 1

    # ── 按题型加权 ──
    if question_type in ("阅读", "选词填空", "段落匹配", "仔细阅读"):
        weights = {"flesch": 0.25, "grade": 0.25, "fog": 0.15, "sentence": 0.20, "vocab": 0.15}
    elif question_type == "听力":
        weights = {"flesch": 0.20, "grade": 0.15, "fog": 0.10, "sentence": 0.35, "vocab": 0.20}
    elif question_type == "翻译":
        weights = {"flesch": 0.15, "grade": 0.15, "fog": 0.15, "sentence": 0.25, "vocab": 0.30}
    elif question_type == "写作":
        weights = {"flesch": 0.20, "grade": 0.20, "fog": 0.10, "sentence": 0.15, "vocab": 0.35}
    else:
        weights = {"flesch": 0.20, "grade": 0.20, "fog": 0.20, "sentence": 0.20, "vocab": 0.20}

    weighted = sum(weights[k] * scores[k] for k in weights)
    difficulty = round(weighted)
    difficulty = max(1, min(5, difficulty))

    level_map = {1: "基础", 2: "进阶", 3: "中等", 4: "较难", 5: "困难"}
    confidence = _compute_confidence(features)

    return {
        "difficulty": str(difficulty),
        "level": level_map[difficulty],
        "confidence": round(confidence, 2),
        "metrics": {
            "word_count": features["word_count"],
            "avg_sentence_length": round(features["avg_sentence_length"], 1),
            "avg_syllables_per_word": round(features["avg_syllables_per_word"], 2),
            "complex_word_ratio": round(features["complex_word_ratio"], 3),
            "flesch_reading_ease": round(features["flesch_reading_ease"], 1),
            "flesch_kincaid_grade": round(features["flesch_kincaid_grade"], 1),
            "gunning_fog": round(features["gunning_fog"], 1),
            "type_token_ratio": round(features["type_token_ratio"], 3),
        }
    }


def _compute_confidence(features):
    """基于文本长度计算置信度，短文本分析不可靠"""
    wc = features["word_count"]
    if wc >= 200:
        return 0.95
    elif wc >= 100:
        return 0.85
    elif wc >= 50:
        return 0.70
    elif wc >= 20:
        return 0.50
    else:
        return 0.30


# ── AI 混合分析（v2.x）────────────────────────────────────

def analyze_question_hybrid(content, question_type):
    """
    AI + textstat 混合分析，AI优先，失败时降级为textstat。

    Returns:
        dict: {
            "difficulty": "1"-"5",
            "level": str,
            "confidence": float,
            "source": "ai" | "textstat_fallback",
            "ai_detail": dict | None,   # AI维度明细（仅AI成功时有）
            "metrics": dict | {}        # textstat指标
        }
    """
    from .ai_gateway import analyze_by_ai

    ai_result = analyze_by_ai(content, question_type)

    extracted_text = extract_english_text(content, question_type)
    features = compute_text_features(extracted_text)
    textstat_result = features_to_difficulty(features, question_type)

    if ai_result is not None:
        return {
            "difficulty": str(ai_result["overall"]),
            "level": {1: "基础", 2: "进阶", 3: "中等", 4: "较难", 5: "困难"}[ai_result["overall"]],
            "confidence": ai_result["confidence"],
            "source": "ai",
            "ai_detail": {
                "model": ai_result["model"],
                "dimensions": ai_result["dimensions"],
                "weights": ai_result["weights"],
                "reasoning": ai_result["reasoning"],
            },
            "metrics": textstat_result.get("metrics", {}),
        }

    return {
        "difficulty": textstat_result["difficulty"],
        "level": textstat_result["level"],
        "confidence": textstat_result["confidence"],
        "source": "textstat_fallback",
        "ai_detail": None,
        "metrics": textstat_result.get("metrics", {}),
    }


# ── 对外统一接口 ──────────────────────────────────────────

def analyze_question(content, question_type):
    """
    分析单道题的静态难度。

    Args:
        content: 题目文本内容
        question_type: 题型（写作/听力/阅读/翻译）

    Returns:
        dict: {"difficulty": "1"-"5", "level": str, "confidence": float, "metrics": dict}
    """
    extracted_text = extract_english_text(content, question_type)
    features = compute_text_features(extracted_text)
    return features_to_difficulty(features, question_type)


# ── Elo 集成（v3.0）─────────────────────────────────────────

def get_full_difficulty(question_id, db_session=None):
    """获取题目完整难度评估：静态 + AI + Elo 三元合一。

    Returns:
        dict: {
            "difficulty": str (最终难度 1-5),
            "static_diff": int (静态分析难度),
            "ai_diff": int | None (AI分析难度),
            "elo_diff": int | None (Elo动态难度),
            "elo_rating": float | None (Elo分值),
            "elo_samples": int (Elo样本数),
            "source": str (primary source for difficulty),

        }
    """
    from models.question import Question
    from .elo import elo_to_difficulty

    own_db = db_session is None
    if own_db:
        from db.database import SessionLocal
        db = SessionLocal()
    else:
        db = db_session

    try:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            return None

        static_diff = int(q.difficulty) if q.difficulty else 3

        detail = q.difficulty_detail or {}
        ai_data = detail.get("ai_detail")
        elo_data = detail.get("elo")

        ai_diff = None
        if ai_data and ai_data.get("dimensions"):
            ai_diff = int(detail.get("source") == "ai" and static_diff)

        elo_diff = None
        elo_rating = q.difficulty_elo
        elo_samples = 0
        if elo_data:
            elo_diff = elo_to_difficulty(elo_data["rating"]) if elo_data.get("rating") else None
            elo_rating = elo_data.get("rating")
            elo_samples = elo_data.get("samples", 0)

        # 最终难度：优先 Elo（有足够样本）→ AI → 静态
        if elo_diff is not None and elo_samples >= 5:
            final_diff = str(elo_diff)
            source = "elo"
        elif ai_data and detail.get("source") == "ai":
            final_diff = str(static_diff)
            source = "ai"
        else:
            final_diff = str(static_diff)
            source = "static"

        return {
            "difficulty": final_diff,
            "static_diff": static_diff,
            "ai_diff": ai_diff,
            "elo_diff": elo_diff,
            "elo_rating": elo_rating,
            "elo_samples": elo_samples,
            "source": source,
        }
    finally:
        if own_db:
            db.close()


def analyze_batch(questions, progress_callback=None):
    """
    批量分析题目。

    Args:
        questions: [(id, content, type), ...]
        progress_callback: 可选回调，每道题分析完调用

    Returns:
        list of (id, result_dict)
    """
    results = []
    for i, (qid, content, qtype) in enumerate(questions):
        result = analyze_question(content, qtype)
        results.append((qid, result))
        if progress_callback:
            progress_callback(i + 1, len(questions), qid, result)
    return results
