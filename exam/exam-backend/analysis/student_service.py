"""
学生个人分析服务
"""
from db.database import SessionLocal
from models.exam_record import ExamRecord
from models.user import User

TYPE_QUESTIONS = {"写作": [1], "听力": list(range(2, 27)), "阅读": list(range(27, 57)), "翻译": [57]}
OBJECTIVE_TYPES = {"听力", "阅读"}


def _get_user_info(db, student_name):
    """根据学生姓名查找对应的系统用户信息"""
    user = db.query(User).filter(
        (User.username == student_name) | (User.email == student_name)
    ).first()
    if user:
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "email": user.email,
        }
    return None


def get_student_analysis(exam_id: str, student_name: str):
    db = SessionLocal()
    try:
        records = db.query(ExamRecord).filter(
            ExamRecord.exam_id == exam_id, ExamRecord.student_name == student_name).all()
        if not records: return {"code": 404, "msg": "未找到该学生记录"}

        total_score = sum(r.score for r in records)
        total_full = sum(r.full_score for r in records)
        type_scores = {}
        for type_name, q_nums in TYPE_QUESTIONS.items():
            qs = [r for r in records if r.question_id in q_nums]
            if qs:
                is_obj = type_name in OBJECTIVE_TYPES
                correct = sum(1 for r in qs if r.score >= r.full_score) if is_obj else None
                type_scores[type_name] = {"score": round(sum(r.score for r in qs), 1),
                    "full_score": sum(r.full_score for r in qs), "count": len(qs),
                    "correct": correct,
                    "accuracy": round(correct / len(qs), 4) if is_obj and qs else None,
                    "is_objective": is_obj,
                    "score_rate": round(sum(r.score for r in qs) / sum(r.full_score for r in qs), 4) if sum(r.full_score for r in qs) else 0}

        details = sorted([{"question_id": r.question_id, "score": r.score, "full_score": r.full_score}
                          for r in records], key=lambda x: x["question_id"])
        class_name = records[0].class_name
        class_records = db.query(ExamRecord).filter(ExamRecord.exam_id == exam_id,
                                                     ExamRecord.class_name == class_name).all()
        all_records = db.query(ExamRecord).filter(ExamRecord.exam_id == exam_id).all()

        user_info = _get_user_info(db, student_name)

        return {"code": 200, "data": {"student_name": student_name, "class_name": class_name,
                "total_score": round(total_score, 1), "total_full": total_full,
                "score_rate": round(total_score / total_full, 4) if total_full else 0,
                "class_rank": _rank(class_records, student_name)["rank"],
                "class_total": _rank(class_records, student_name)["total"],
                "exam_rank": _rank(all_records, student_name)["rank"],
                "exam_total": _rank(all_records, student_name)["total"],
                "type_scores": type_scores, "details": details,
                "user_info": user_info}}
    finally:
        db.close()


def get_students_by_exam(exam_id: str):
    db = SessionLocal()
    try:
        rows = db.query(ExamRecord.student_name, ExamRecord.class_name).filter(
            ExamRecord.exam_id == exam_id).distinct().all()
        seen = set()
        students = []
        for name, cls in rows:
            if name not in seen:
                seen.add(name)
                user_info = _get_user_info(db, name)
                students.append({"student_name": name, "class_name": cls, "user_info": user_info})
        return {"code": 200, "data": sorted(students, key=lambda x: x["student_name"])}
    finally:
        db.close()


def _rank(records, target):
    totals = {}
    for r in records:
        totals.setdefault(r.student_name, 0)
        totals[r.student_name] += r.score
    sorted_students = sorted(totals.items(), key=lambda x: -x[1])
    rank = 1
    for s, _ in sorted_students:
        if s == target: break
        rank += 1
    return {"rank": rank, "total": len(sorted_students)}
