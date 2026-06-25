# clear_questions.py 一键清空题库（只删题目数据，不删表）
from db.database import SessionLocal
from models.question import Question

def clear_all_questions():
    db = SessionLocal()
    try:
        # 统计清空前的题目数量
        count_before = db.query(Question).count()
        print(f"清空前，题库共有 {count_before} 道题目")
        
        # 清空所有题目数据
        db.query(Question).delete()
        db.commit()
        
        print(f"✅ 已清空所有模拟题，共删除 {count_before} 道题目！")
    except Exception as e:
        print(f"❌ 清空失败：{str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # 加个确认步骤，防止误删
    confirm = input("⚠️  确认要清空所有题目吗？输入 'yes' 继续：")
    if confirm.lower() == "yes":
        clear_all_questions()
    else:
        print("已取消清空操作")