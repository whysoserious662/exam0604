"""检查数据库当前状态"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import SessionLocal
from models.question import Question

def check_db():
    db = SessionLocal()
    try:
        # 检查题目数量
        count = db.query(Question).count()
        print(f"数据库现有题目数量: {count}")
        
        # 列出前几个ID
        if count > 0:
            questions = db.query(Question).all()
            print()
            print(f"题目ID列表（前20个）:")
            for i, q in enumerate(questions[:20]):
                print(f"  {i+1}. ID={q.id}, 类型={q.type}, 选项={len(q.options) if q.options else 0}个")
        
        # 删除所有题目
        print()
        print("正在清空数据库...")
        db.query(Question).delete()
        db.commit()
        print("数据库已清空！")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
