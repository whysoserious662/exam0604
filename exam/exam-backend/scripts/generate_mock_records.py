"""
生成 CET4 模拟答题数据（标准四级试卷 57题/710分）
听力/阅读为选择题：对=满分/错=0分
写作/翻译为主观题：连续分值
"""
import random
import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import SessionLocal
from models.exam_record import ExamRecord

EXAM_ID = "2026-06-CET4"

# CET4 标准试卷结构: (题号, 题型, 分值, 是否选择题)
PAPER = [
    (1, "写作", 106.5, False),
    *[(i, "听力", 7.1, True) for i in range(2, 9)],
    *[(i, "听力", 7.1, True) for i in range(9, 17)],
    *[(i, "听力", 14.2, True) for i in range(17, 27)],
    *[(i, "阅读", 3.55, True) for i in range(27, 37)],
    *[(i, "阅读", 7.1, True) for i in range(37, 47)],
    *[(i, "阅读", 14.2, True) for i in range(47, 57)],
    (57, "翻译", 106.5, False),
]

CLASSES = ["计算机1班", "计算机2班", "英语1班"]
STUDENTS_PER_CLASS = 15

# 学生水平档次
LEVELS = [
    ("优秀", 0.70, 0.95),
    ("中等", 0.45, 0.70),
    ("及格", 0.25, 0.45),
    ("较弱", 0.10, 0.25),
]

def generate():
    db = SessionLocal()
    try:
        existing = db.query(ExamRecord).filter(ExamRecord.exam_id == EXAM_ID).count()
        if existing:
            print(f"! 考试 {EXAM_ID} 已有 {existing} 条记录，将先清空")
            db.query(ExamRecord).filter(ExamRecord.exam_id == EXAM_ID).delete()
            db.flush()

        total_records = 0
        for class_name in CLASSES:
            for i in range(STUDENTS_PER_CLASS):
                level_tag, rate_min, rate_max = random.choice(LEVELS)
                student_name = f"{class_name[:-1]}S{str(i+1).zfill(2)}"

                for q_no, q_type, q_score, is_objective in PAPER:
                    if is_objective:
                        correct_prob = random.uniform(rate_min, rate_max)
                        score = q_score if random.random() < correct_prob else 0
                    else:
                        rate = random.uniform(rate_min, rate_max)
                        rate = max(0, min(1, rate + random.uniform(-0.1, 0.1)))
                        score = round(rate * q_score, 1)

                    db.add(ExamRecord(
                        exam_id=EXAM_ID,
                        student_name=student_name,
                        class_name=class_name,
                        question_id=q_no,
                        score=score,
                        full_score=q_score
                    ))
                    total_records += 1

                if total_records % 500 == 0:
                    db.flush()

        db.commit()

        total_students = len(CLASSES) * STUDENTS_PER_CLASS
        print(f"模拟数据生成成功")
        print(f"   考试: {EXAM_ID}")
        print(f"   班级: {len(CLASSES)} 个, 学生: {total_students} 人")
        print(f"   题目: {len(PAPER)} 道 (听力阅读=0/1计分, 写作翻译=连续分值)")
        print(f"   总分: 710 (写作106.5 + 听力248.5 + 阅读248.5 + 翻译106.5)")
    except Exception as e:
        db.rollback()
        print(f"生成失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    generate()
