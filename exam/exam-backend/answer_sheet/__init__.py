from utils.auth import require_teacher
from fastapi import Depends
"""
解析PDF管理模块 — PDF类型检测、解析PDF存储、答案匹配
"""
import os
import re
import json
from fastapi import APIRouter, UploadFile, File
from db.database import SessionLocal
from models.question import Question
from models.answer_sheet import AnswerSheet
from answer_parser import parse_answer_pdf

router = APIRouter(tags=["解析管理"])
os.makedirs("data/answer_pdf", exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# PDF 类型检测 & 文件名归一化
# ═══════════════════════════════════════════════════════════════════

def detect_pdf_type(filename):
    """检测 PDF 类型: 'exam' | 'answer' | 'unknown'"""
    name = filename.lower()
    if '解析' in name:
        return 'answer'
    if '答案' in name:
        return 'answer'
    if '真题' in name:
        return 'exam'
    if '四级' in name and '答案' not in name and '解析' not in name:
        return 'exam'
    return 'unknown'


def extract_match_key(filename):
    """从文件名中提取匹配键 (year_month, suite_number)
    e.g.:
      '2025.12四级真题第1套.pdf' -> ('2025.12', 1)
      '2025.12英语四级解析第1套.pdf' -> ('2025.12', 1)
      '2024年12月英语四级真题(第1套).pdf' -> ('2024.12', 1)
      '2024年6月四级真题解析【第一套】.pdf' -> ('2024.06', 1)
    """
    name = os.path.basename(filename)

    # 年月: YYYY.MM 或 YYYY年MM月
    ym = ''
    m1 = re.search(r'(\d{4})[\.。年](\d{1,2})[月\.]?', name)
    if m1:
        year = m1.group(1)
        month = m1.group(2).zfill(2)
        ym = f'{year}.{month}'

    # 套数
    suite = 1
    m2 = re.search(r'第\s*(\d+)\s*套', name)
    if m2:
        suite = int(m2.group(1))
    else:
        # "第一套" 等中文数字
        cn_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5}
        m3 = re.search(r'第\s*([一二三四五])\s*套', name)
        if m3:
            suite = cn_map.get(m3.group(1), 1)
        else:
            # 也尝试从括号中提取
            m4 = re.search(r'[\(（]\s*第?\s*(\d)\s*套?\s*[\)）]', name)
            if m4:
                suite = int(m4.group(1))

    return ym, suite


# ═══════════════════════════════════════════════════════════════════
# 答案匹配
# ═══════════════════════════════════════════════════════════════════

def find_matching_exam_source(ym, suite):
    """在 question 表中查找匹配的 source 文件名"""
    db = SessionLocal()
    try:
        sources = db.query(Question.source).filter(
            Question.source != None, Question.source != ""
        ).distinct().all()
        for (src,) in sources:
            if not src:
                continue
            src_ym, src_suite = extract_match_key(src)
            if src_ym == ym and src_suite == suite:
                return src
        return None
    finally:
        db.close()


def apply_answers_to_questions(answer_sheet_id):
    """将解析表中的答案填充到对应的 Question 记录中"""
    db = SessionLocal()
    try:
        sheet = db.query(AnswerSheet).filter(AnswerSheet.id == answer_sheet_id).first()
        if not sheet or not sheet.matched_exam_source or not sheet.answers_json:
            db.close()
            return 0

        answers = sheet.answers_json if isinstance(sheet.answers_json, list) else json.loads(sheet.answers_json)
        if not answers:
            db.close()
            return 0

        # 类型映射：解析PDF中的题型 -> Question表中的题型
        type_map = {"听力": "听力", "阅读": "阅读"}

        count = 0
        for ans in answers:
            qnum = ans.get("question_number")
            answer = ans.get("answer", "")
            analysis = ans.get("analysis", "")
            ans_type = ans.get("type", "")

            if not qnum or not answer:
                continue

            # 查找匹配的题目: same source + question_number + matching type
            filters = [
                Question.source == sheet.matched_exam_source,
                Question.question_number == qnum,
            ]
            # 加上题型过滤（写作和翻译没有客观答案，不匹配）
            mapped_type = type_map.get(ans_type)
            if mapped_type:
                filters.append(Question.type == mapped_type)

            q = db.query(Question).filter(*filters).first()

            if q:
                q.answer = str(answer)
                if analysis:
                    q.analysis = str(analysis)
                count += 1

        sheet.match_count = count
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        return 0
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# DeepSeek 辅助提取
# ═══════════════════════════════════════════════════════════════════

def _deepseek_extract(ocr_text):
    """用 DeepSeek 从 OCR 文字中提取答案"""
    try:
        import requests as req
        api_key = os.getenv('DEEPSEEK_API_KEY')
        base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/')
        model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

        all_answers = []
        chunk_size = 14000
        overlap = 1000
        chunks = []
        pos = 0
        while pos < len(ocr_text):
            chunks.append(ocr_text[pos:pos + chunk_size])
            pos += chunk_size - overlap
        chunks = chunks[:4]  # 最多4块

        for ci, chunk in enumerate(chunks):
            prompt = f'''从以下四级真题答案解析OCR文字中提取每道题的正确答案。
返回JSON数组：[{{"question_number": 题号, "answer": "答案字母", "type": "听力或阅读"}}]
听力题号1-25，阅读题号26-55。答案只保留一个字母。没有把握的不要返回。只返回JSON数组。

OCR文字（第{ci+1}/{len(chunks)}块）：
{chunk}'''
            try:
                resp = req.post(f'{base_url}/v1/chat/completions',
                    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                    json={'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                          'max_tokens': 4000, 'temperature': 0}, timeout=120)
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    import re as _re
                    jm = _re.search(r'\[.*\]', content, _re.DOTALL)
                    if jm:
                        chunk_ans = json.loads(jm.group())
                        all_answers.extend(chunk_ans)
            except Exception:
                continue

        # 去重
        seen = set()
        unique = []
        for a in all_answers:
            key = (a.get('question_number'), a.get('type'))
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════

@router.post("/api/answer-sheet/upload")
def upload_answer_pdf(file: UploadFile = File(...), teacher = Depends(require_teacher)):
    """上传解析PDF — 自动识别类型、解析并匹配"""
    if not file.filename.lower().endswith(".pdf"):
        return {"code": 400, "msg": "仅支持PDF文件"}

    pdf_type = detect_pdf_type(file.filename)
    if pdf_type not in ('answer', 'exam'):
        return {"code": 400, "msg": f"无法识别PDF类型（文件名需含'真题'或'解析'）: {file.filename}"}

    # 保存文件
    save_path = f"data/answer_pdf/{file.filename}"
    with open(save_path, "wb") as f:
        f.write(file.file.read())

    # 提取匹配键
    ym, suite = extract_match_key(file.filename)

    # 如果是题目PDF，引导用户使用正确的导入接口
    if pdf_type == 'exam':
        os.remove(save_path)
        return {"code": 400, "msg": "这是题目PDF，请使用「题库管理 → 导入PDF」功能上传"}

    # 解析答案PDF
    answers, full_text, has_text = parse_answer_pdf(save_path)

    # 如果文字无法提取（扫描版），尝试 OCR + DeepSeek
    ocr_used = False
    if not has_text or len(answers) == 0:
        try:
            from ocr_scanner import ocr_pdf
            ocr_text, ocr_pages = ocr_pdf(save_path)
            if ocr_text and len(ocr_text.strip()) > 200:
                full_text = ocr_text
                has_text = True
                ocr_used = True
                # 先用正则做初步提取
                from answer_parser import parse_ocr_text
                answers = parse_ocr_text(ocr_text)
                # 再用 DeepSeek 提取（分块发送OCR文字）
                ds_answers = _deepseek_extract(ocr_text)
                # 合并：DeepSeek优先，正则补充
                ds_nums = set(a['question_number'] for a in ds_answers)
                for a in answers:
                    if a['question_number'] not in ds_nums:
                        ds_answers.append(a)
                answers = ds_answers
        except Exception as e:
            import traceback
            traceback.print_exc()
            pass  # OCR 失败，保持原有结果

    # 查找匹配的题目source
    matched_source = find_matching_exam_source(ym, suite)

    # 存入数据库
    db = SessionLocal()
    try:
        sheet = AnswerSheet(
            filename=file.filename,
            pdf_path=save_path,
            year_month=ym,
            suite_number=suite,
            has_extracted_text=has_text,
            full_text=full_text[:50000] if full_text else "",
            answers_json=answers,
            matched_exam_source=matched_source,
        )
        db.add(sheet)
        db.commit()
        sheet_id = sheet.id

        # 如果匹配到了题目，自动应用答案
        match_count = 0
        if matched_source and answers:
            match_count = apply_answers_to_questions(sheet_id)

        return {
            "code": 200,
            "msg": f"解析PDF上传成功！{'[OCR识别] ' if ocr_used else ''}{('提取到 ' + str(len(answers)) + ' 条答案') if answers else '未提取到答案（文字版无内容或OCR识别失败）'}",
            "data": {
                "id": sheet_id,
                "filename": file.filename,
                "year_month": ym,
                "suite_number": suite,
                "has_text": has_text,
                "answers_count": len(answers),
                "matched_source": matched_source,
                "match_count": match_count,
                "answers": answers[:10],  # 预览前10条
            }
        }
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "处理失败", "error": str(e)}
    finally:
        db.close()


@router.get("/api/answer-sheet/list")
def list_answer_sheets(page: int = 1, size: int = 10):
    """列出所有解析PDF记录"""
    db = SessionLocal()
    try:
        q = db.query(AnswerSheet).order_by(AnswerSheet.created_at.desc())
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return {
            "code": 200,
            "total": total,
            "page": page,
            "size": size,
            "data": [{
                "id": s.id,
                "filename": s.filename,
                "year_month": s.year_month,
                "suite_number": s.suite_number,
                "has_extracted_text": s.has_extracted_text,
                "answers_count": len(s.answers_json) if s.answers_json else 0,
                "matched_exam_source": s.matched_exam_source,
                "match_count": s.match_count,
                "created_at": str(s.created_at) if s.created_at else "",
            } for s in items],
        }
    finally:
        db.close()


@router.post("/api/answer-sheet/{sheet_id}/apply")
def apply_sheet_answers(sheet_id: int, teacher = Depends(require_teacher)):
    """将指定解析表中的答案应用到题目中"""
    count = apply_answers_to_questions(sheet_id)
    return {"code": 200, "msg": f"成功为 {count} 道题目填充了答案和解析"}


@router.delete("/api/answer-sheet/{sheet_id}")
def delete_answer_sheet(sheet_id: int, teacher = Depends(require_teacher)):
    """删除解析PDF记录"""
    db = SessionLocal()
    try:
        sheet = db.query(AnswerSheet).filter(AnswerSheet.id == sheet_id).first()
        if not sheet:
            return {"code": 404, "msg": "记录不存在"}
        # 删除文件
        if sheet.pdf_path and os.path.exists(sheet.pdf_path):
            os.remove(sheet.pdf_path)
        db.delete(sheet)
        db.commit()
        return {"code": 200, "msg": "删除成功"}
    except Exception as e:
        db.rollback()
        return {"code": 500, "msg": "删除失败", "error": str(e)}
    finally:
        db.close()
