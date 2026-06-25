# 批量生成500道英语四级题目 - 修复版（去掉source字段）
from db.database import SessionLocal
from models.question import Question
import random

# 英语四级标准配置（完全匹配你们系统）
QUESTION_TYPES = ["听力", "阅读", "词汇", "翻译", "写作"]
DFFICULTY_LEVEL = ["1", "2", "3"]   # 1=基础 2=进阶 3=冲刺
KNOWLEDGE_POINTS = [1, 2, 3, 4, 5]

def generate_cet4_question():
    """生成1道标准四级题"""
    q_type = random.choice(QUESTION_TYPES)
    diff = random.choice(DFFICULTY_LEVEL)
    kid = random.choice(KNOWLEDGE_POINTS)
    
    content = f"CET4 Question {random.randint(1000, 9999)} | {q_type} | Difficulty {diff}"
    answer = "A" if q_type in ["听力", "阅读", "词汇"] else "Sample answer"
    analysis = f"本题考点：四级{q_type}，难度{diff}，强化知识点{kid}"

    return {
        "content": content,
        "type": q_type,
        "difficulty": diff,
        "answer": answer,
        "analysis": analysis,
        "knowledge_id": kid,
        "score": 1
    }

def insert_batch(count=500):
    db = SessionLocal()
    try:
        questions = [Question(**generate_cet4_question()) for _ in range(count)]
        db.bulk_save_objects(questions)
        db.commit()
        print(f"✅ 成功插入 {count} 道英语四级题目！")
    except Exception as e:
        print(f"❌ 插入失败：{str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    insert_batch(500)