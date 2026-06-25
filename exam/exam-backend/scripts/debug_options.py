"""调试选项保存和恢复功能"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from db.database import SessionLocal
from models.question import Question

def test_options():
    db = SessionLocal()
    try:
        # 创建一个测试问题，包含选项
        test_options = ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"]
        options_json = json.dumps(test_options)
        print(f"选项JSON: {options_json}")
        
        # 保存到数据库
        q = Question(
            id=999,
            content="Test question content",
            type="choice",
            difficulty=2,
            options=options_json,
            source="Test"
        )
        db.add(q)
        db.commit()
        
        # 查询并验证
        result = db.query(Question).filter(Question.id == 999).first()
        print(f"从数据库读取的options: {result.options}")
        
        # 解析JSON
        parsed_options = json.loads(result.options)
        print(f"解析后的选项: {parsed_options}")
        
        # 清理测试数据
        db.delete(q)
        db.commit()
        
        print("测试成功！")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_options()
