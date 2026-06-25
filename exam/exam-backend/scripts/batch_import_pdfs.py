"""批量导入pdf_upload文件夹中的所有PDF文件"""
import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_parser import load_questions_from_pdf
from db.database import SessionLocal
from models.question import Question

def batch_import():
    pdf_folder = "pdf_upload"
    
    if not os.path.exists(pdf_folder):
        print(f"文件夹 {pdf_folder} 不存在！")
        return
    
    total_added = 0
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')]
    
    print(f"找到 {len(pdf_files)} 个PDF文件")
    print("=" * 60)
    
    # 获取当前最大ID，避免冲突
    db = SessionLocal()
    current_max_id = 0
    max_q = db.query(Question).order_by(Question.id.desc()).first()
    if max_q:
        current_max_id = max_q.id
    db.close()
    
    for pdf_index, filename in enumerate(pdf_files):
        pdf_path = os.path.join(pdf_folder, filename)
        print(f"正在处理: {filename}")
        
        try:
            # 直接解析题目并手动添加（这样可以控制ID偏移）
            questions = load_questions_from_pdf(pdf_path)
            
            # 重新设置ID，避免冲突
            for q in questions:
                current_max_id += 1
                q.id = current_max_id
            
            # 用简单的编号作为source
            simple_source = f"PDF{pdf_index+1:02d}"
            
            # 导入题目
            added = 0
            db = SessionLocal()
            try:
                difficulty_map = {"easy": 1, "medium": 2, "hard": 3}
                import json
                for q in questions:
                    db_question = Question(
                        id=q.id,
                        content=q.content,
                        type=q.type,
                        difficulty=difficulty_map.get(q.difficulty, 2),
                        answer="",
                        analysis="",
                        knowledge_id=1,
                        score=q.score,
                        source=simple_source,
                        audio_url="",
                        options=json.dumps(q.options) if q.options else None
                    )
                    db.add(db_question)
                    added += 1
                db.commit()
            finally:
                db.close()
            
            print(f"  → 新增 {added} 道题目 (ID从{current_max_id - added + 1}到{current_max_id})")
            total_added += added
        except Exception as e:
            print(f"  → 处理失败: {e}")
        
        print("-" * 60)
    
    print()
    print(f"批量导入完成！共新增 {total_added} 道题目")

    # 显示题库统计
    db = SessionLocal()
    total = db.query(Question).count()
    db.close()
    print(f"题库总计: {total} 道")

if __name__ == "__main__":
    batch_import()
