from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from db.database import Base


class StudentAnswer(Base):
    __tablename__ = "student_answer"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(String(50), nullable=True, index=True, comment="考试编号")
    student_name = Column(String(50), nullable=True, comment="学生姓名")
    question_id = Column(Integer, nullable=False, comment="题目ID（试卷内部顺序号 1-57）")
    answer_text = Column(Text, default="", comment="学生提交的答案")
    submitted_at = Column(DateTime, server_default=func.now(), comment="提交时间")
