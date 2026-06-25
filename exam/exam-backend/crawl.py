# crawl.py 【最终版】批量解析本地PDF + 自动入库数据库
import os
import re
import pdfplumber
from db.database import SessionLocal
from models.question import Question

# ===================== 你的PDF解析函数（和后端完全一致） =====================
def parse_cet4_pdf(pdf_path):
    questions = []
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    page_text = re.sub(r"\s+", " ", page_text)
                    full_text += page_text + "\n\n"
    except Exception as e:
        print(f"⚠️  解析PDF失败: {e}")
        return []

    def clean_txt(s):
        s = s.strip()
        s = re.sub(r"\n+", "\n", s)
        s = re.sub(r" +", " ", s)
        return s

    # 写作
    write_rule = re.compile(r"Writing\s*(.*?)(?=Listening Comprehension|Section A|$)", re.DOTALL | re.I)
    w = write_rule.search(full_text)
    if w and len(clean_txt(w.group(1))) > 30:
        questions.append({
            "content": "【四级写作】\n" + clean_txt(w.group(1)),
            "type": "写作", "difficulty": "2", "score": 1,
            "answer": "官方范文", "analysis": "解析待补充", "knowledge_id": 5
        })

    # 听力
    listen_rule = re.compile(r"Listening Comprehension\s*(.*?)(?=Reading Comprehension|Section B|$)", re.DOTALL | re.I)
    l = listen_rule.search(full_text)
    if l and len(clean_txt(l.group(1))) > 50:
        questions.append({
            "content": "【四级听力】\n" + clean_txt(l.group(1)),
            "type": "听力", "difficulty": "2", "score": 1,
            "answer": "听力答案", "analysis": "解析待补充", "knowledge_id": 1
        })

    # 阅读
    read_rule = re.compile(r"Reading Comprehension\s*(.*?)(?=Translation|Section C|$)", re.DOTALL | re.I)
    r = read_rule.search(full_text)
    if r and len(clean_txt(r.group(1))) > 50:
        questions.append({
            "content": "【四级阅读】\n" + clean_txt(r.group(1)),
            "type": "阅读", "difficulty": "2", "score": 1,
            "answer": "阅读答案", "analysis": "解析待补充", "knowledge_id": 3
        })

    # 翻译
    trans_rule = re.compile(r"Translation\s*(.*?)(?=Writing|Part|$)", re.DOTALL | re.I)
    t = trans_rule.search(full_text)
    if t and len(clean_txt(t.group(1))) > 20:
        questions.append({
            "content": "【四级翻译】\n" + clean_txt(t.group(1)),
            "type": "翻译", "difficulty": "2", "score": 1,
            "answer": "翻译译文", "analysis": "解析待补充", "knowledge_id": 4
        })

    return questions

# ===================== 批量入库核心代码 =====================
def batch_import_pdfs():
    db = SessionLocal()
    success_count = 0
    pdf_folder = "pdf_upload"  # 固定文件夹，放你的真题PDF

    # 遍历文件夹所有PDF
    for file in os.listdir(pdf_folder):
        if file.lower().endswith(".pdf"):
            path = os.path.join(pdf_folder, file)
            print(f"\n📄 处理文件: {file}")

            # 解析题目
            qs = parse_cet4_pdf(path)
            if not qs:
                print("❌ 未识别到题目")
                continue

            # 入库 + 去重
            for item in qs:
                exists = db.query(Question).filter(Question.content == item["content"]).first()
                if not exists:
                    db.add(Question(**item))
                    success_count += 1
                    print(f"✅ 已入库: {item['type']}")
                else:
                    print(f"⚠️  已存在: {item['type']}")

    db.commit()
    db.close()
    print(f"\n🎉 批量导入完成！总共新增题目：{success_count} 道")

if __name__ == "__main__":
    batch_import_pdfs()