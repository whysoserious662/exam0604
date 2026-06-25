from utils.auth import require_teacher
from fastapi import Depends
"""
试卷分析模块 — 总体分析 + AI评语 + 学生个人分析
"""
from fastapi import APIRouter
from pydantic import BaseModel
from db.database import SessionLocal
from models.question import Question
from models.exam_record import ExamRecord
from models.knowledge_point import KnowledgePoint
from .calculator import full_analysis
from .ai_service import generate_comment
from .student_service import get_student_analysis, get_students_by_exam

router = APIRouter(tags=["试卷分析"])


# ── 总体分析 ──────────────────────────────────────────────────────────

@router.get("/api/analysis")
def get_analysis(exam_id: str):
    db = SessionLocal()
    try:
        records = db.query(ExamRecord).filter(ExamRecord.exam_id == exam_id).all()
        if not records: return {"code": 404, "msg": "该考试暂无答题记录"}
        qids = list(set(r.question_id for r in records))
        questions = db.query(Question).filter(Question.id.in_(qids)).all()
        question_info = {q.id: {"difficulty": q.difficulty, "content": q.content} for q in questions}

        # 构建 question_id -> knowledge_id 映射
        qid_to_kid = {q.id: q.knowledge_id for q in questions}

        # 查询知识点名称
        kid_set = set(kid for kid in qid_to_kid.values() if kid is not None)
        kps = db.query(KnowledgePoint).filter(KnowledgePoint.id.in_(kid_set)).all() if kid_set else []
        knowledge_map = {kp.id: kp.name for kp in kps}

        recs = [{"student_id": r.student_name, "score": r.score, "max_score": r.full_score,
                 "knowledge_id": qid_to_kid.get(r.question_id) or 0,
                 "question_number": r.question_id} for r in records]
        result = full_analysis(recs, question_info)
        result["exam_id"] = exam_id
        result["knowledge_map"] = knowledge_map
        return {"code": 200, "data": result}
    except Exception as e:
        return {"code": 500, "error": str(e)}
    finally:
        db.close()


# ── AI 评语 ───────────────────────────────────────────────────────────

class AICommentRequest(BaseModel):
    exam_id: str

@router.post("/api/analysis/ai-comment")
def get_ai_comment(req: AICommentRequest):
    db = SessionLocal()
    try:
        records = db.query(ExamRecord).filter(ExamRecord.exam_id == req.exam_id).all()
        if not records: return {"code": 404, "msg": "该考试暂无答题记录"}
        qids = list(set(r.question_id for r in records))
        questions = db.query(Question).filter(Question.id.in_(qids)).all()
        question_info = {q.id: {"difficulty": q.difficulty} for q in questions}
        qid_to_kid = {q.id: q.knowledge_id for q in questions}
        recs = [{"student_id": r.student_name, "score": r.score, "max_score": r.full_score,
                 "knowledge_id": qid_to_kid.get(r.question_id) or 0,
                 "question_number": r.question_id} for r in records]
        analysis = full_analysis(recs, question_info)
        comment, error = generate_comment(analysis)
        return {"code": 500, "msg": error} if error else {"code": 200, "data": {"comment": comment}}
    except Exception as e:
        return {"code": 500, "msg": "AI 评语生成失败", "error": str(e)}
    finally:
        db.close()


# ── 学生分析 ──────────────────────────────────────────────────────────

@router.get("/api/analysis/student")
def student_analysis(exam_id: str, student_name: str):
    return get_student_analysis(exam_id, student_name)

@router.get("/api/analysis/students")
def analysis_students(exam_id: str):
    return get_students_by_exam(exam_id)
