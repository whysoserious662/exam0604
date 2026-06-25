"""修复翻译题内容 — 从PDF重新提取包含中文源文本的完整翻译题"""
import os
import re
import pdfplumber
from db.database import SessionLocal
from models.question import Question


def extract_translation_from_pdf(pdf_path):
    """从PDF提取翻译部分，保留中文源文本"""
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
    except Exception:
        return None

    # 定位翻译部分
    idx = full_text.find("Translation")
    if idx < 0:
        return None

    section = full_text[idx:]

    # 截断到下一个Section或版权信息
    cutoff = re.search(r'(20\d{2}年\d{1,2}月英语四级|Writing|Listening|Reading)', section[50:])
    if cutoff:
        section = section[:50 + cutoff.start()]

    # 清理噪声
    section = section.strip()
    section = re.sub(r'by:.*$', '', section, flags=re.M)
    section = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', section)
    section = re.sub(r'\n{3,}', '\n\n', section)

    return section.strip()


def repair_all_translations():
    """从PDF文件夹重新提取翻译内容并更新数据库"""
    db = SessionLocal()
    pdf_folder = "pdf_upload"
    pdf_files = sorted([f for f in os.listdir(pdf_folder) if f.endswith('.pdf')])

    print(f"找到 {len(pdf_files)} 个PDF文件\n")

    # 获取所有翻译题（按id排序，与PDF保持大致对应）
    translation_qs = db.query(Question).filter(
        Question.type == '翻译'
    ).order_by(Question.id).all()

    print(f"数据库中有 {len(translation_qs)} 道翻译题\n")

    updated = 0
    for i, pdf_file in enumerate(pdf_files):
        if i >= len(translation_qs):
            break

        pdf_path = os.path.join(pdf_folder, pdf_file)
        content = extract_translation_from_pdf(pdf_path)

        if content and len(content) > 100:
            q = translation_qs[i]
            old_len = len(q.content)
            q.content = "【四级翻译部分】\n" + content
            updated += 1
            print(f"  PDF: {pdf_file[:50]}...")
            print(f"  -> ID={q.id} 长度 {old_len} → {len(q.content)} 字符")
            preview = content[:120].replace('\n', ' ')
            print(f"  -> 原文: {preview}...")
            print()
        else:
            q = translation_qs[i]
            print(f"  ⚠ {pdf_file[:50]}... -> 未提取到翻译内容 (ID={q.id})\n")

    db.commit()
    db.close()
    print(f"完成！修复 {updated}/{len(translation_qs)} 道翻译题")


if __name__ == "__main__":
    repair_all_translations()
