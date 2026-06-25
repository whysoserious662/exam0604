"""
题库模块 — 题目CRUD + PDF上传解析（管理接口需教师权限）
"""
import os
import json
from fastapi import APIRouter, UploadFile, File, Depends
from pydantic import BaseModel
from sqlalchemy import text
from db.database import SessionLocal
from models.question import Question
from cet4_parser import parse_cet4_pdf
from answer_sheet import detect_pdf_type
from utils.auth import get_current_user, require_teacher

router = APIRouter(tags=["题库"])
os.makedirs("data/pdf_upload", exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────

class QuestionUpdate(BaseModel):
    type: str; content: str; answer: str; analysis: str; difficulty: int

class QuestionCreate(BaseModel):
    type: str; content: str; answer: str = ""; analysis: str = ""; difficulty: int


# ── PDF 上传 ──────────────────────────────────────────────────────────

@router.post("/api/pdf/upload")
def upload_pdf(file: UploadFile = File(...), teacher = Depends(require_teacher)):
    if not file.filename.lower().endswith(".pdf"):
        return {"code": 400, "msg": "仅支持PDF文件"}

    # 检测PDF类型
    pdf_type = detect_pdf_type(file.filename)
    if pdf_type == 'answer':
        return {
            "code": 400,
            "msg": "检测到这是解析PDF，请使用「解析管理」功能上传",
            "pdf_type": "answer",
            "suggest": "请前往解析管理页面或使用 /api/answer-sheet/upload 接口"
        }

    save_path = f"data/pdf_upload/{file.filename}"
    with open(save_path, "wb") as f:
        f.write(file.file.read())
    try:
        questions_data, full_text = parse_cet4_pdf(save_path)
        if not questions_data:
            return {"code": 404, "msg": "未识别到真题内容，请确认PDF为文字版（非扫描图片）"}

        db = SessionLocal()
        count = 0
        section_count = {}
        for qd in questions_data:
            # 解析 options JSON
            try:
                options_val = json.loads(qd["options"]) if qd.get("options") else None
            except (TypeError, json.JSONDecodeError):
                options_val = None

            db.add(Question(
                content=qd["content"],
                type=qd["type"],
                difficulty=qd.get("difficulty", 2),
                answer=qd.get("answer", ""),
                analysis=qd.get("analysis", ""),
                knowledge_id=qd.get("knowledge_id", 1),
                score=qd.get("score", 1),
                options=options_val,
                question_number=qd.get("question_number"),
                section=qd.get("section"),
                source=qd.get("source"),
                passage_text=qd.get("passage_text"),
            ))
            count += 1
            sec = qd.get("section", "未知")
            section_count[sec] = section_count.get(sec, 0) + 1

        db.commit()
        db.close()

        return {
            "code": 200,
            "msg": f"上传成功！共导入 {count} 道题目",
            "count": count,
            "filename": file.filename,
            "text_length": len(full_text),
            "sections": section_count,
            "text_preview": full_text[:500],
        }
    except Exception as e:
        return {"code": 500, "msg": "处理失败", "error": str(e)}


# ── 音频服务 ──────────────────────────────────────────────────────────

from fastapi import Request
from fastapi.responses import StreamingResponse

@router.get("/api/audio/{question_id}")
def serve_audio(question_id: int, request: Request):
    """从数据库 audio_files 表读取音频并流式返回（支持Range拖拽）"""
    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q or not q.audio_url:
            return {"code": 404, "msg": "该题目没有关联音频文件"}

        # 从 audio_url 提取文件名，查 audio_files 表
        fname = os.path.basename(q.audio_url)
        row = db.execute(text("SELECT data FROM audio_files WHERE filename=:fn"), {"fn": fname}).fetchone()
        if not row:
            return {"code": 404, "msg": f"音频文件不在数据库中: {fname}"}

        audio_data = row[0]
        file_size = len(audio_data)
        range_header = request.headers.get("range")

        if range_header:
            import re as _re
            match = _re.match(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                start = int(match.group(1))
                end_str = match.group(2)
                end = int(end_str) if end_str else file_size - 1

                if start >= file_size:
                    return StreamingResponse(
                        iter([b""]), status_code=416,
                        headers={"Content-Range": f"bytes */{file_size}"}
                    )

                chunk_size = end - start + 1

                def blob_iterator(data, offset, length):
                    pos = offset
                    remaining = length
                    while remaining > 0:
                        chunk = data[pos:pos + min(8192, remaining)]
                        if not chunk: break
                        yield chunk
                        pos += len(chunk)
                        remaining -= len(chunk)

                return StreamingResponse(
                    blob_iterator(audio_data, start, chunk_size),
                    status_code=206,
                    media_type="audio/mpeg",
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Accept-Ranges": "bytes",
                        "Content-Length": str(chunk_size),
                    }
                )

        # 完整返回
        def full_blob_iterator(data):
            pos = 0
            while pos < len(data):
                yield data[pos:pos + 8192]
                pos += 8192

        return StreamingResponse(
            full_blob_iterator(audio_data),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            }
        )
    finally:
        db.close()


# ── 题目列表 ──────────────────────────────────────────────────────────

@router.get("/api/question/list")
def get_questions(page: int = 1, size: int = 10, type: str = None, difficulty: int = None, user = Depends(get_current_user)):
    try:
        db = SessionLocal()
        q = db.query(Question)
        if type: q = q.filter(Question.type == type)
        if difficulty is not None: q = q.filter(Question.difficulty == difficulty)
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        db.close()
        return {"code": 200, "total": total, "page": page, "size": size,
                "pages": (total + size - 1) // size,
                "data": [{"id": i.id, "content": i.content, "type": i.type,
                          "difficulty": i.difficulty, "answer": i.answer,
                          "analysis": i.analysis, "knowledge_id": i.knowledge_id,
                          "score": i.score,
                          "options": i.options, "question_number": i.question_number,
                          "section": i.section, "source": i.source,
                          "passage_text": i.passage_text,
                          "audio_url": i.audio_url} for i in items]}
    except Exception as e:
        return {"code": 500, "error": str(e)}


# ── 题目 CRUD ────────────────────────────────────────────────────────

@router.delete("/api/question/{question_id}")
def delete_question(question_id: int, teacher = Depends(require_teacher)):
    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q: return {"code": 404, "msg": "题目不存在"}
        db.delete(q); db.commit()
        return {"code": 200, "msg": "删除成功"}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "删除失败", "error": str(e)}
    finally:
        db.close()


@router.delete("/api/question/clear")
def clear_all_questions(teacher = Depends(require_teacher)):
    db = SessionLocal()
    try:
        c = db.query(Question).count()
        db.query(Question).delete(); db.commit()
        return {"code": 200, "msg": f"已清空{c}道题目"}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "清空失败", "error": str(e)}
    finally:
        db.close()


# ── 批量导入音频 ──────────────────────────────────────────────────────────

@router.post("/api/audio/batch-import")
def batch_import_audio(teacher = Depends(require_teacher)):
    """扫描测试题目文件夹，匹配MP3到听力题，并存入 audio_files 表"""
    from answer_sheet import extract_match_key
    audio_dir = r"d:\桌面\专业综合设计\第十三周\测试题目"

    # 收集所有MP3
    mp3_files = []
    for root, dirs, files in os.walk(audio_dir):
        for f in files:
            if f.endswith(".mp3"):
                mp3_files.append(os.path.join(root, f))

    db = SessionLocal()
    try:
        sources = [r[0] for r in db.query(Question.source).distinct().all()]

        matched = 0
        unmatched = []
        updated = 0
        stored_audio = 0

        for mp3_path in mp3_files:
            fname = os.path.basename(mp3_path)
            ym, suite = extract_match_key(fname)

            # 存入 audio_files 表（文件名去重）
            existing = db.execute(
                text("SELECT id FROM audio_files WHERE filename=:fn"), {"fn": fname}
            ).fetchone()
            if not existing:
                with open(mp3_path, "rb") as f:
                    db.execute(
                        text("INSERT INTO audio_files (filename, data) VALUES (:fn, :d)"),
                        {"fn": fname, "d": f.read()}
                    )
                    stored_audio += 1

            # 匹配题目源并更新 audio_url
            found = False
            for src in sources:
                if not src:
                    continue
                s_ym, s_suite = extract_match_key(src)
                if s_ym == ym and s_suite == suite:
                    # 存相对路径，方便跨平台
                    result = db.query(Question).filter(
                        Question.source == src,
                        Question.type == "听力"
                    ).update({"audio_url": f"audio/{fname}"})
                    updated += result
                    matched += 1
                    found = True
                    break
            if not found:
                unmatched.append(fname)

        db.commit()

        return {
            "code": 200,
            "msg": f"音频导入完成！匹配 {matched}/{len(mp3_files)} 个MP3，更新 {updated} 道听力题，入库 {stored_audio} 个音频文件",
            "data": {
                "total_mp3": len(mp3_files),
                "matched": matched,
                "unmatched": unmatched,
                "updated_questions": updated,
                "stored_audio": stored_audio,
            }
        }
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "音频导入失败", "error": str(e)}
    finally:
        db.close()


# ── 批量导入 PDF 文件夹 ──────────────────────────────────────────────

@router.post("/api/pdf/batch-import")
def batch_import_pdfs(teacher = Depends(require_teacher)):
    """导入 pdf_upload 文件夹中的所有 PDF"""
    pdf_dir = "pdf_upload"
    if not os.path.exists(pdf_dir):
        return {"code": 404, "msg": f"文件夹 {pdf_dir} 不存在"}

    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        return {"code": 404, "msg": "没有找到PDF文件"}

    db = SessionLocal()
    total_imported = 0
    file_results = []

    for filename in pdf_files:
        pdf_path = os.path.join(pdf_dir, filename)
        try:
            questions_data, _ = parse_cet4_pdf(pdf_path)
        except Exception as e:
            file_results.append({"file": filename, "count": 0, "error": str(e)})
            continue

        if not questions_data:
            file_results.append({"file": filename, "count": 0, "error": "未识别到内容"})
            continue

        try:
            for qd in questions_data:
                try:
                    options_val = json.loads(qd["options"]) if qd.get("options") else None
                except (TypeError, json.JSONDecodeError):
                    options_val = None

                db.add(Question(
                    content=qd["content"],
                    type=qd["type"],
                    difficulty=qd.get("difficulty", 2),
                    answer=qd.get("answer", ""),
                    analysis=qd.get("analysis", ""),
                    knowledge_id=qd.get("knowledge_id", 1),
                    score=qd.get("score", 1),
                    options=options_val,
                    question_number=qd.get("question_number"),
                    section=qd.get("section"),
                    source=qd.get("source"),
                    passage_text=qd.get("passage_text"),
                ))
                total_imported += 1
            db.commit()
            file_results.append({"file": filename, "count": len(questions_data)})
        except Exception as e:
            db.rollback()
            file_results.append({"file": filename, "count": 0, "error": str(e)})

    db.close()
    return {
        "code": 200,
        "msg": f"批量导入完成，共导入 {total_imported} 道题目",
        "total": total_imported,
        "files": file_results,
    }


@router.put("/api/question/{question_id}")
def update_question(question_id: int, data: QuestionUpdate, teacher = Depends(require_teacher)):
    db = SessionLocal()
    try:
        q = db.query(Question).filter(Question.id == question_id).first()
        if not q: return {"code": 404, "msg": "题目不存在"}
        for k, v in data.model_dump().items(): setattr(q, k, v)
        db.commit()
        return {"code": 200, "msg": "修改成功"}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "修改失败", "error": str(e)}
    finally:
        db.close()


@router.post("/api/question")
def create_question(data: QuestionCreate, teacher = Depends(require_teacher)):
    db = SessionLocal()
    try:
        db.add(Question(**data.model_dump())); db.commit()
        return {"code": 200, "msg": "题目新增成功"}
    except Exception as e:
        db.rollback(); return {"code": 500, "msg": "新增失败", "error": str(e)}
    finally:
        db.close()
