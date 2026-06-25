"""
Elo 动态难度调整引擎 — 阶段2

基于真实答题数据，对题目难度进行动态校准。
原理：答对率高 → 题目偏易 → 难度分降低；答对率低 → 题目偏难 → 难度分升高。
"""
import math
from collections import defaultdict
from sqlalchemy.orm.attributes import flag_modified
from db.database import SessionLocal
from models.question import Question
from models.exam_record import ExamRecord
from models.paper import ExamPaperMapping


# ── 题目 ID 映射工具 ──────────────────────────────────────

def _build_qid_mapping(db):
    """构建 (exam_id, paper_qid) → real_question_db_id 的映射表。

    ExamRecord.question_id 在在线考试场景中存储的是试卷内部题号（1-57），
    而非 Question 表的真实 ID。需要通过 ExamPaperMapping 翻译。
    对于无映射的 record（如 Excel 导入），直接使用 question_id。
    """
    mappings = db.query(ExamPaperMapping).all()
    qid_map = {}
    for m in mappings:
        qid_map[(m.exam_id, m.question_id)] = m.question_db_id
    return qid_map


def _resolve_question_id(record, qid_map):
    """将 ExamRecord 的 question_id 解析为真实的 Question.id"""
    key = (record.exam_id, record.question_id)
    return qid_map.get(key, record.question_id)


# ── Elo 参数 ──────────────────────────────────────────────

K_FACTOR = 24          # 单次调整幅度
MIN_SAMPLES = 5         # 最少答题人数阈值，达到后才调整难度
INITIAL_ELO = {        # 静态难度 → 初始 Elo 映射
    1: 900,
    2: 1150,
    3: 1400,
    4: 1650,
    5: 1900,
}
DEFAULT_STUDENT_ELO = 1200  # 新学生默认能力分
ELO_SCALE = 400             # 标准 Elo 缩放因子


# ── 核心计算 ──────────────────────────────────────────────

def expected_score(rating_a, rating_b):
    """A 对 B 的期望得分率（0~1）。rating_a 为学生，rating_b 为题目。"""
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / ELO_SCALE))


def update_elo(old_rating, expected, actual, k=K_FACTOR):
    """单次 Elo 更新。actual 为实际得分率（0~1）。
    学生表现低于预期 → 题目偏难 → Elo 升高。
    学生表现高于预期 → 题目偏易 → Elo 降低。"""
    return old_rating + k * (expected - actual)


def elo_to_difficulty(elo):
    """Elo 分 → 1-5 难度等级"""
    if elo < 1025:
        return 1
    elif elo < 1275:
        return 2
    elif elo < 1525:
        return 3
    elif elo < 1775:
        return 4
    else:
        return 5


def difficulty_to_elo(difficulty):
    """1-5 难度 → 初始 Elo"""
    d = int(difficulty) if difficulty else 3
    return INITIAL_ELO.get(d, 1400)


# ── 批量重算 ──────────────────────────────────────────────

def recalculate_all_elo():
    """基于全部答题记录，重算所有题目的 Elo 并更新 difficulty 字段。

    算法：
    1. 读取全部答题记录，按 question_id 分组
    2. 按 student 汇总每人的平均得分率 → student_ability
    3. 对每道题，计算 expected vs actual → 更新 Elo
    4. 映射回 1-5 难度分，写库
    """
    db = SessionLocal()
    try:
        records = db.query(ExamRecord).all()
        questions = db.query(Question).all()

        if not records:
            return {"processed": 0, "updated": 0, "msg": "无答题记录，跳过 Elo 调整"}

        # 构建 question_id 映射（试卷题号→真实ID）
        qid_map = _build_qid_mapping(db)

        # 1. 按题目分组原始数据（使用真实 question id）
        q_data = defaultdict(list)
        for r in records:
            real_qid = _resolve_question_id(r, qid_map)
            q_data[real_qid].append((r.student_name, r.score, r.full_score))

        # 2. 计算每个学生的全局能力分
        student_scores = defaultdict(list)
        for r in records:
            rate = r.score / r.full_score if r.full_score > 0 else 0
            student_scores[r.student_name].append(rate)

        student_elo = {}
        for name, rates in student_scores.items():
            avg_rate = sum(rates) / len(rates)
            student_elo[name] = DEFAULT_STUDENT_ELO + (avg_rate - 0.5) * ELO_SCALE

        avg_student_elo = sum(student_elo.values()) / len(student_elo) if student_elo else DEFAULT_STUDENT_ELO

        # 3. 对每道题执行 Elo 调整
        updated = 0
        details = []

        for q in questions:
            qid = q.id
            raw = q_data.get(qid, [])
            static_diff = int(q.difficulty) if q.difficulty else 3
            current_elo = q.difficulty_elo or difficulty_to_elo(static_diff)

            if not raw:
                # 无答题数据，保留静态难度，初始化 Elo
                if q.difficulty_elo is None:
                    q.difficulty_elo = difficulty_to_elo(static_diff)
                # 写入初始 detail（无样本数据）
                detail = q.difficulty_detail or {}
                detail["elo"] = {
                    "rating": q.difficulty_elo,
                    "static_diff": static_diff,
                    "samples": 0,
                    "avg_actual_rate": 0,
                    "avg_expected_rate": 0,
                    "adjustment": 0,
                    "msg": "无答题记录，使用静态难度初始化",
                }
                q.difficulty_detail = detail
                flag_modified(q, "difficulty_detail")
                updated += 1
                continue

            # 计算实际得分率（加权平均）
            total_score = sum(s for _, s, _ in raw)
            total_full = sum(f for _, _, f in raw)
            actual_rate = total_score / total_full if total_full > 0 else 0.5

            # 每个学生的期望 vs 实际
            elo_adjustments = []
            for student, score, full in raw:
                s_elo = student_elo.get(student, avg_student_elo)
                actual = score / full if full > 0 else 0
                expected = expected_score(s_elo, current_elo)
                elo_adjustments.append((expected, actual))

            # 平均调整
            avg_expected = sum(e for e, _ in elo_adjustments) / len(elo_adjustments)
            avg_actual = sum(a for _, a in elo_adjustments) / len(elo_adjustments)

            new_elo = update_elo(current_elo, avg_expected, avg_actual)
            # 钳制在合理范围
            new_elo = max(400, min(2400, new_elo))
            q.difficulty_elo = round(new_elo, 1)

            new_diff = elo_to_difficulty(new_elo)
            old_diff = int(q.difficulty) if q.difficulty else 3

            # 更新难度详情
            detail = q.difficulty_detail or {}
            detail["elo"] = {
                "rating": round(new_elo, 1),
                "static_diff": old_diff,
                "samples": len(raw),
                "avg_actual_rate": round(actual_rate, 4),
                "avg_expected_rate": round(avg_expected, 4),
                "adjustment": round(new_elo - current_elo, 2),
                "k_factor": K_FACTOR,
            }
            q.difficulty_detail = detail
            flag_modified(q, "difficulty_detail")

            if new_diff != old_diff:
                q.difficulty = str(new_diff)

            details.append({
                "id": qid,
                "elo": round(new_elo, 1),
                "old_diff": old_diff,
                "new_diff": new_diff,
                "samples": len(raw),
                "actual_rate": round(actual_rate, 4),
                "adjustment": round(new_elo - current_elo, 2),
            })
            updated += 1

        db.commit()

        changed = sum(1 for d in details if d["old_diff"] != d["new_diff"])
        return {
            "processed": len(details),
            "updated": updated,
            "difficulty_changed": changed,
            "total_records": len(records),
            "details": details,
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def _calc_student_elo_map(db):
    """计算所有学生的全局能力分（缓存用）"""
    all_records = db.query(ExamRecord).all()
    student_scores = defaultdict(list)
    for r in all_records:
        rate = r.score / r.full_score if r.full_score > 0 else 0
        student_scores[r.student_name].append(rate)
    return {
        name: DEFAULT_STUDENT_ELO + (sum(rates) / len(rates) - 0.5) * ELO_SCALE
        for name, rates in student_scores.items()
    }


def recalculate_question_elo(question_id, min_samples=MIN_SAMPLES):
    """单题 Elo 重算（答题记录变更时调用）。

    只有当答题人数 ≥ min_samples 时才真正调整难度，
    避免少量噪声数据误导难度评分。
    """
    import time as _time
    _time.sleep(0.3)  # 等待主线程事务提交可见

    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            return

        # 通过映射表查找对应此真实 question_id 的记录
        qid_map = _build_qid_mapping(db)
        # 找到所有映射到此 question_db_id 的 (exam_id, paper_qid)
        mapped_keys = [(k[0], k[1]) for k, v in qid_map.items() if v == question_id]

        records = []
        if mapped_keys:
            for exam_id, paper_qid in mapped_keys:
                recs = db.query(ExamRecord).filter(
                    ExamRecord.exam_id == exam_id,
                    ExamRecord.question_id == paper_qid
                ).all()
                records.extend(recs)
        # 同时查直接匹配的记录（Excel导入等）
        direct = db.query(ExamRecord).filter(
            ExamRecord.question_id == question_id
        ).all()
        for r in direct:
            key = (r.exam_id, r.question_id)
            if key not in qid_map:
                records.append(r)

        static_diff = int(q.difficulty) if q.difficulty else 3
        current_elo = q.difficulty_elo or difficulty_to_elo(static_diff)

        n = len(records)

        # 初始化 Elo（无记录时）
        if n == 0:
            if q.difficulty_elo is None:
                q.difficulty_elo = difficulty_to_elo(static_diff)
                db.commit()
            return

        # 样本不足：更新 Elo 值但不调整难度等级
        if n < min_samples:
            if q.difficulty_elo is None:
                q.difficulty_elo = difficulty_to_elo(static_diff)
            # 仍更新 detail 记录样本数
            detail = q.difficulty_detail or {}
            detail["elo"] = {
                "rating": current_elo,
                "static_diff": static_diff,
                "samples": n,
                "avg_actual_rate": round(
                    sum(r.score / r.full_score if r.full_score > 0 else 0 for r in records) / n, 4
                ),
                "avg_expected_rate": 0,
                "adjustment": 0,
                "pending": True,
                "msg": f"样本不足（{n}/{min_samples}），暂不调整难度",
            }
            q.difficulty_detail = detail
            flag_modified(q, "difficulty_detail")
            db.commit()
            return

        # 样本充足：正常 Elo 调整
        student_elo = _calc_student_elo_map(db)
        avg_se = sum(student_elo.values()) / len(student_elo) if student_elo else DEFAULT_STUDENT_ELO

        adjustments = []
        for r in records:
            s_elo = student_elo.get(r.student_name, avg_se)
            actual = r.score / r.full_score if r.full_score > 0 else 0
            expected = expected_score(s_elo, current_elo)
            adjustments.append((expected, actual))

        avg_expected = sum(e for e, _ in adjustments) / len(adjustments)
        avg_actual = sum(a for _, a in adjustments) / len(adjustments)

        new_elo = update_elo(current_elo, avg_expected, avg_actual)
        new_elo = max(400, min(2400, new_elo))
        q.difficulty_elo = round(new_elo, 1)

        new_diff = elo_to_difficulty(new_elo)
        old_diff = int(q.difficulty) if q.difficulty else 3

        detail = q.difficulty_detail or {}
        detail["elo"] = {
            "rating": round(new_elo, 1),
            "static_diff": static_diff,
            "samples": n,
            "avg_actual_rate": round(avg_actual, 4),
            "avg_expected_rate": round(avg_expected, 4),
            "adjustment": round(new_elo - current_elo, 2),
            "threshold_met": True,
        }
        q.difficulty_detail = detail
        flag_modified(q, "difficulty_detail")

        if new_diff != old_diff:
            q.difficulty = str(new_diff)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Elo] recalculate_question_elo error: {e}")
    finally:
        db.close()


def recalculate_batch_elo(question_ids, min_samples=MIN_SAMPLES):
    """批量 Elo 重算（答题变更批量触发）。比逐题重算更高效（共享学生能力缓存）。"""
    import time as _time
    _time.sleep(0.3)

    db = SessionLocal()
    try:
        student_elo = _calc_student_elo_map(db)
        avg_se = sum(student_elo.values()) / len(student_elo) if student_elo else DEFAULT_STUDENT_ELO
        qid_map = _build_qid_mapping(db)

        updated = 0
        for qid in set(question_ids):
            q = db.query(Question).filter(Question.id == qid).first()
            if not q:
                continue

            # 通过映射表查找记录
            mapped_keys = [(k[0], k[1]) for k, v in qid_map.items() if v == qid]
            records = []
            if mapped_keys:
                for exam_id, paper_qid in mapped_keys:
                    recs = db.query(ExamRecord).filter(
                        ExamRecord.exam_id == exam_id,
                        ExamRecord.question_id == paper_qid
                    ).all()
                    records.extend(recs)
            direct = db.query(ExamRecord).filter(
                ExamRecord.question_id == qid
            ).all()
            for r in direct:
                key = (r.exam_id, r.question_id)
                if key not in qid_map:
                    records.append(r)
            n = len(records)
            static_diff = int(q.difficulty) if q.difficulty else 3
            current_elo = q.difficulty_elo or difficulty_to_elo(static_diff)

            if n == 0:
                if q.difficulty_elo is None:
                    q.difficulty_elo = difficulty_to_elo(static_diff)
                continue

            if n < min_samples:
                if q.difficulty_elo is None:
                    q.difficulty_elo = difficulty_to_elo(static_diff)
                detail = q.difficulty_detail or {}
                detail["elo"] = {
                    "rating": current_elo, "static_diff": static_diff,
                    "samples": n, "pending": True,
                    "msg": f"样本不足（{n}/{min_samples}）",
                }
                q.difficulty_detail = detail
                flag_modified(q, "difficulty_detail")
                updated += 1
                continue

            adjustments = [
                (expected_score(student_elo.get(r.student_name, avg_se), current_elo),
                 r.score / r.full_score if r.full_score > 0 else 0)
                for r in records
            ]
            avg_expected = sum(e for e, _ in adjustments) / len(adjustments)
            avg_actual = sum(a for _, a in adjustments) / len(adjustments)

            new_elo = update_elo(current_elo, avg_expected, avg_actual)
            new_elo = max(400, min(2400, new_elo))
            q.difficulty_elo = round(new_elo, 1)

            new_diff = elo_to_difficulty(new_elo)
            old_diff = int(q.difficulty) if q.difficulty else 3

            detail = q.difficulty_detail or {}
            detail["elo"] = {
                "rating": round(new_elo, 1), "static_diff": static_diff,
                "samples": n, "avg_actual_rate": round(avg_actual, 4),
                "avg_expected_rate": round(avg_expected, 4),
                "adjustment": round(new_elo - current_elo, 2),
                "threshold_met": True,
            }
            q.difficulty_detail = detail
            flag_modified(q, "difficulty_detail")

            if new_diff != old_diff:
                q.difficulty = str(new_diff)
            updated += 1

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Elo] batch error: {e}")
    finally:
        db.close()


def get_elo_stats():
    """获取 Elo 统计信息"""
    db = SessionLocal()
    try:
        total = db.query(Question).count()
        has_elo = db.query(Question).filter(Question.difficulty_elo.isnot(None)).count()
        has_records = db.query(ExamRecord.question_id).distinct().count()

        # 手动分桶统计（兼容 MySQL only_full_group_by）
        buckets = [(400, 900), (900, 1025), (1025, 1275), (1275, 1525), (1525, 1775), (1775, 2400)]
        labels = ["<900", "900-1025", "1025-1275", "1275-1525", "1525-1775", ">1775"]
        dist = {}
        for (lo, hi), label in zip(buckets, labels):
            cnt = db.query(Question).filter(
                Question.difficulty_elo >= lo,
                Question.difficulty_elo < hi
            ).count()
            if cnt > 0:
                dist[label] = cnt

        return {
            "total_questions": total,
            "questions_with_elo": has_elo,
            "questions_with_records": has_records,
            "elo_distribution": dist,
            "params": {
                "k_factor": K_FACTOR,
                "scale": ELO_SCALE,
                "init_map": INITIAL_ELO,
            },
        }
    finally:
        db.close()
