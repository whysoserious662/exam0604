from utils.auth import require_teacher
from fastapi import Depends
"""
答题记录模块 — CRUD + 筛选 + Excel导入 + 学生总成绩
"""
import os
from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from db.database import SessionLocal
from models.exam_record import ExamRecord
from sqlalchemy import func

router = APIRouter(tags=["答题记录"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_DIR = os.path.join(BASE_DIR, "excel_templates")
TEMPLATE_PATH = os.path.join(EXCEL_DIR, "答题记录导入模板.xlsx")


class ExamRecordCreate(BaseModel):
    exam_id: str; student_name: str; class_name: str = ""
    question_id: int; score: float; full_score: float = 1.0

class ExamRecordUpdate(BaseModel):
    exam_id: str = None; student_name: str = None; class_name: str = None
    question_id: int = None; score: float = None; full_score: float = None


def qtype(qid: int) -> str:
    if qid == 1: return "写作"
    if 2 <= qid <= 26: return "听力"
    if 27 <= qid <= 56: return "阅读"
    if qid == 57: return "翻译"
    return "未知"


@router.get("/api/exam-record/list")
def get_exam_records(page: int = 1, size: int = 20, exam_id: str = None,
                     class_name: str = None, student_name: str = None):
    db = SessionLocal()
    try:
        q = db.query(ExamRecord)
        if exam_id: q = q.filter(ExamRecord.exam_id == exam_id)
        if class_name: q = q.filter(ExamRecord.class_name == class_name)
        if student_name: q = q.filter(ExamRecord.student_name.like(f"%{student_name}%"))
        total = q.count()
        rows = q.order_by(ExamRecord.id.desc()).offset((page - 1) * size).limit(size).all()
        return {"code": 200, "total": total, "page": page, "size": size,
                "pages": (total + size - 1) // size,
                "data": [{"id": r.id, "exam_id": r.exam_id, "student_name": r.student_name,
                          "class_name": r.class_name, "question_id": r.question_id,
                          "score": r.score, "full_score": r.full_score,
                          "question_type": qtype(r.question_id)} for r in rows]}
    except Exception as e:
        return {"code": 500, "error": str(e)}
    finally:
        db.close()


@router.get("/api/exam-record/filters")
def get_exam_record_filters():
    db = SessionLocal()
    try:
        exams = db.query(ExamRecord.exam_id).distinct().all()
        classes = db.query(ExamRecord.class_name).distinct().all()
        return {"code": 200, "exam_ids": [e[0] for e in exams if e[0]],
                "class_names": [c[0] for c in classes if c[0]]}
    except Exception as e:
        return {"code": 500, "error": str(e)}
    finally:
        db.close()


@router.post("/api/exam-record")
def create_exam_record(data: ExamRecordCreate):
    db = SessionLocal()
    try:
        r = ExamRecord(**data.model_dump()); db.add(r); db.commit()
        return {"code": 200, "msg": "新增成功", "id": r.id}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "新增失败", "error": str(e)}
    finally:
        db.close()


@router.put("/api/exam-record/{record_id}")
def update_exam_record(record_id: int, data: ExamRecordUpdate):
    db = SessionLocal()
    try:
        r = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
        if not r: return {"code": 404, "msg": "记录不存在"}
        for k, v in {k: v for k, v in data.model_dump().items() if v is not None}.items():
            setattr(r, k, v)
        db.commit()
        return {"code": 200, "msg": "修改成功"}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "修改失败", "error": str(e)}
    finally:
        db.close()


@router.delete("/api/exam-record/{record_id}")
def delete_exam_record(record_id: int):
    db = SessionLocal()
    try:
        r = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
        if not r: return {"code": 404, "msg": "记录不存在"}
        db.delete(r); db.commit()
        return {"code": 200, "msg": "删除成功"}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "删除失败", "error": str(e)}
    finally:
        db.close()


# ── 学生总成绩（按学生分组） ──────────────────────────────────────────

@router.get("/api/exam-record/student-summary")
def get_student_summary(exam_id: str = None, class_name: str = None, student_name: str = None):
    db = SessionLocal()
    try:
        q = db.query(
            ExamRecord.exam_id, ExamRecord.student_name, ExamRecord.class_name,
            func.sum(ExamRecord.score).label("total_score"),
            func.sum(ExamRecord.full_score).label("total_full"),
            func.count(ExamRecord.id).label("question_count"),
        ).group_by(ExamRecord.exam_id, ExamRecord.student_name, ExamRecord.class_name)
        if exam_id: q = q.filter(ExamRecord.exam_id == exam_id)
        if class_name: q = q.filter(ExamRecord.class_name == class_name)
        if student_name: q = q.filter(ExamRecord.student_name.like(f"%{student_name}%"))
        rows = q.order_by(func.sum(ExamRecord.score).desc()).all()
        data = []
        for r in rows:
            rate = round(r.total_score / r.total_full * 100, 1) if r.total_full else 0
            data.append({"exam_id": r.exam_id, "student_name": r.student_name,
                         "class_name": r.class_name, "total_score": round(r.total_score, 1),
                         "total_full": round(r.total_full, 1), "score_rate": rate,
                         "question_count": r.question_count})
        return {"code": 200, "data": data, "total": len(data)}
    except Exception as e:
        return {"code": 500, "error": str(e)}
    finally:
        db.close()


# ── Excel 模板下载 ─────────────────────────────────────────────────

@router.get("/api/exam-record/download-template")
def download_template():
    if not os.path.exists(TEMPLATE_PATH):
        return {"code": 404, "msg": "模板文件不存在，请重新生成"}
    return FileResponse(TEMPLATE_PATH, filename="答题记录导入模板.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Excel 批量导入 ────────────────────────────────────────────────

@router.post("/api/exam-record/import-excel")
async def import_excel(file: UploadFile = File(...)):
    # 保存上传文件
    os.makedirs(EXCEL_DIR, exist_ok=True)
    save_path = os.path.join(EXCEL_DIR, file.filename)
    with open(save_path, "wb") as f:
        f.write(await file.read())

    try:
        import openpyxl
        wb = openpyxl.load_workbook(save_path)
        ws = wb.active

        rows = []
        errors = []
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if all(v is None for v in row):
                continue  # skip empty rows
            if len(row) < 6:
                errors.append(f"第{i}行：列数不足，需要6列")
                continue
            exam_id, student_name, class_name, question_id, score, full_score = row[:6]
            if not exam_id or not student_name:
                errors.append(f"第{i}行：考试ID和学生姓名为必填")
                continue
            try:
                qid = int(question_id)
                s = float(score) if score is not None else 0
                fs = float(full_score) if full_score is not None else 1
                rows.append({
                    "exam_id": str(exam_id).strip(),
                    "student_name": str(student_name).strip(),
                    "class_name": str(class_name).strip() if class_name else "",
                    "question_id": qid,
                    "score": s,
                    "full_score": fs,
                })
            except (ValueError, TypeError):
                errors.append(f"第{i}行：数字格式错误（题号/得分/满分须为数字）")
                continue

        if not rows:
            return {"code": 400, "msg": "文件中没有有效的答题记录", "errors": errors}

        # 批量写入数据库（使用原生SQL避免重复记录检查）
        db = SessionLocal()
        try:
            success = 0
            updated = 0
            for r in rows:
                # 检查是否已存在
                exist = db.query(ExamRecord).filter(
                    ExamRecord.exam_id == r["exam_id"],
                    ExamRecord.student_name == r["student_name"],
                    ExamRecord.question_id == r["question_id"],
                ).first()
                if exist:
                    exist.score = r["score"]
                    exist.full_score = r["full_score"]
                    if r["class_name"]: exist.class_name = r["class_name"]
                    updated += 1
                else:
                    db.add(ExamRecord(**r))
                    success += 1
            db.commit()
            return {"code": 200, "msg": f"导入完成：新增{success}条，更新{updated}条",
                    "total": len(rows), "inserted": success, "updated": updated,
                    "errors": errors if errors else None}
        except Exception as e:
            db.rollback()
            return {"code": 500, "msg": "导入失败", "error": str(e), "errors": errors}
        finally:
            db.close()
    except Exception as e:
        return {"code": 500, "msg": "文件解析失败", "error": str(e)}
