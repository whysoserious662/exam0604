from utils.auth import require_teacher
from fastapi import Depends
"""
难度分析模块 — AI+textstat混合评估（多线程并行加速）
"""
import threading
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter
from pydantic import BaseModel
from db.database import SessionLocal
from models.question import Question
from services.difficulty_analyzer import analyze_question, analyze_question_hybrid

router = APIRouter(tags=["难度分析"])

# ── 后台任务存储（内存） ──
_task_store = {}
_task_lock = threading.Lock()

# 并行线程数
MAX_WORKERS = 20


class DifficultyAnalyzeReq(BaseModel):
    content: str
    type: str
    use_ai: bool = True


@router.post("/api/difficulty/single")
def analyze_single_question(data: DifficultyAnalyzeReq, teacher = Depends(require_teacher)):
    try:
        if data.use_ai:
            result = analyze_question_hybrid(data.content, data.type)
        else:
            result = analyze_question(data.content, data.type)
        return {"code": 200, "data": result}
    except Exception as e:
        return {"code": 500, "msg": "分析失败", "error": str(e)}


@router.get("/api/difficulty/stats")
def get_difficulty_stats():
    db = SessionLocal()
    try:
        from sqlalchemy import func
        dist = db.query(Question.difficulty, func.count(Question.id)).group_by(Question.difficulty).all()
        stats = {d: c for d, c in dist}
        total = db.query(Question).count()
        return {
            "code": 200,
            "data": {
                "total": total,
                "distribution": stats,
                "levels": {"1": "基础", "2": "进阶", "3": "中等", "4": "较难", "5": "困难"}
            }
        }
    except Exception as e:
        return {"code": 500, "msg": "查询失败", "error": str(e)}
    finally:
        db.close()


@router.get("/api/difficulty/detail/{question_id}")
def get_difficulty_detail(question_id: int):
    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q:
            return {"code": 404, "msg": "题目不存在"}
        return {
            "code": 200,
            "data": {
                "id": q.id,
                "type": q.type,
                "difficulty": q.difficulty,
                "difficulty_detail": q.difficulty_detail,
            }
        }
    except Exception as e:
        return {"code": 500, "msg": "查询失败", "error": str(e)}
    finally:
        db.close()


def _analyze_one(q_id, q_content, q_type, q_difficulty, use_ai):
    """单题分析（线程内独立 DB session）。AI 调用受信号量限制防止限流。"""
    db = SessionLocal()
    try:
        if use_ai:
            result = analyze_question_hybrid(q_content, q_type)
        else:
            result = analyze_question(q_content, q_type)

        q_obj = db.query(Question).filter(Question.id == q_id).first()
        if not q_obj:
            return None

        new_difficulty = result["difficulty"]
        src = result.get("source", "textstat")
        changed = str(q_obj.difficulty) != str(new_difficulty)

        if changed:
            q_obj.difficulty = str(new_difficulty)

        # 合并而非覆盖，保留 Elo 等已有数据
        from sqlalchemy.orm.attributes import flag_modified
        existing = q_obj.difficulty_detail or {}
        existing.update({
            "version": "2.0",
            "source": src,
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ai_detail": result.get("ai_detail"),
            "metrics": result.get("metrics"),
        })
        q_obj.difficulty_detail = existing
        flag_modified(q_obj, "difficulty_detail")
        db.commit()

        return {
            "id": q_id, "type": q_type,
            "difficulty": new_difficulty,
            "level": result["level"],
            "source": src,
            "confidence": result["confidence"],
            "changed": changed,
        }
    except Exception:
        db.rollback()
        return {"id": q_id, "type": q_type, "difficulty": None, "level": "error", "changed": False}
    finally:
        db.close()


def _run_analysis_background(task_id, use_ai):
    """后台多线程并行执行全量难度分析"""
    db = SessionLocal()
    try:
        questions = db.query(Question).all()
    finally:
        db.close()

    total = len(questions)
    updated = 0
    completed = 0
    details = []

    with _task_lock:
        _task_store[task_id]["total"] = total
        _task_store[task_id]["message"] = f"并行分析中（{MAX_WORKERS}线程）..."

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                _analyze_one, q.id, q.content, q.type, q.difficulty, use_ai
            ): q for q in questions
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                details.append(result)
                if result.get("changed"):
                    updated += 1
                if result.get("difficulty") is None:
                    pass  # error already logged in result

            completed += 1

            # 每 10 题更新一次进度
            if completed % 10 == 0 or completed == total:
                with _task_lock:
                    _task_store[task_id]["progress"] = completed
                    _task_store[task_id]["message"] = f"已分析 {completed}/{total} 题"

    with _task_lock:
        _task_store[task_id]["status"] = "completed"
        _task_store[task_id]["progress"] = total
        _task_store[task_id]["message"] = f"分析完成：更新 {updated}/{total} 题"
        _task_store[task_id]["result"] = {
            "total": total, "updated": updated, "details": details[:100]
        }


@router.post("/api/difficulty/analyze-all")
def analyze_all_questions(use_ai: bool = True):
    """启动全量难度分析（后台运行），立即返回 task_id"""
    task_id = str(uuid.uuid4())[:8]

    with _task_lock:
        _task_store[task_id] = {
            "task_id": task_id,
            "status": "running",
            "progress": 0,
            "total": 0,
            "message": "任务已创建，即将开始...",
            "use_ai": use_ai,
            "result": None,
        }

    thread = threading.Thread(
        target=_run_analysis_background,
        args=(task_id, use_ai),
        daemon=True
    )
    thread.start()

    return {
        "code": 200,
        "msg": "难度分析已开始，后台运行中",
        "task_id": task_id,
    }


@router.get("/api/difficulty/task/{task_id}")
def get_task_status(task_id: str):
    """查询后台分析任务的进度"""
    with _task_lock:
        task = _task_store.get(task_id)
    if not task:
        return {"code": 404, "msg": "任务不存在或已过期"}

    return {
        "code": 200,
        "data": {
            "task_id": task["task_id"],
            "status": task["status"],
            "progress": task["progress"],
            "total": task["total"],
            "message": task["message"],
            "use_ai": task["use_ai"],
            "result": task["result"],
        }
    }


@router.post("/api/difficulty/batch-ai")
def batch_ai_analyze_by_type(types: list[str] = None, teacher = Depends(require_teacher)):
    from services.ai_gateway import analyze_by_ai
    import time as time_module

    db = SessionLocal()
    try:
        query = db.query(Question)
        if types:
            query = query.filter(Question.type.in_(types))
        questions = query.all()

        total = len(questions)
        success = 0
        failed = 0
        details = []

        for i, q in enumerate(questions, 1):
            ai_result = analyze_by_ai(q.content, q.type)

            if ai_result is not None:
                q.difficulty = str(ai_result["overall"])
                q.difficulty_detail = {
                    "version": "2.0",
                    "source": "ai",
                    "model": ai_result["model"],
                    "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ai_detail": {
                        "dimensions": ai_result["dimensions"],
                        "weights": ai_result["weights"],
                        "reasoning": ai_result["reasoning"],
                    },
                }
                success += 1
                details.append({
                    "id": q.id, "type": q.type,
                    "difficulty": str(ai_result["overall"]),
                    "reasoning": ai_result.get("reasoning", "")[:80]
                })
            else:
                failed += 1
                details.append({"id": q.id, "type": q.type, "difficulty": None, "reasoning": "AI分析失败，跳过"})

            time_module.sleep(0.3)

        db.commit()
        return {
            "code": 200,
            "msg": f"AI分析完成：成功{success}，失败{failed}，共{total}题",
            "data": {"total": total, "success": success, "failed": failed, "details": details}
        }
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "批量AI分析失败", "error": str(e)}
    finally:
        db.close()


# ── Elo 动态难度调整端点 ──────────────────────────────────────────

@router.post("/api/difficulty/elo/recalculate")
def trigger_elo_recalculate():
    """基于全部答题记录，重算所有题目的 Elo 动态难度"""
    from services.elo import recalculate_all_elo
    try:
        result = recalculate_all_elo()
        if "error" in result:
            return {"code": 500, "msg": "Elo重算失败", "error": result["error"]}
        return {"code": 200, "msg": "Elo重算完成", "data": result}
    except Exception as e:
        return {"code": 500, "msg": "Elo重算异常", "error": str(e)}


@router.get("/api/difficulty/elo/stats")
def get_elo_stats_endpoint():
    """获取 Elo 统计信息"""
    from services.elo import get_elo_stats
    try:
        stats = get_elo_stats()
        return {"code": 200, "data": stats}
    except Exception as e:
        return {"code": 500, "msg": "获取Elo统计失败", "error": str(e)}
