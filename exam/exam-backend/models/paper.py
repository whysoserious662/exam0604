from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy.dialects.mysql import LONGTEXT
from db.database import Base
from datetime import datetime


class Paper(Base):
    __tablename__ = 'paper'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), comment='试卷标题')
    content = Column(LONGTEXT, comment='试卷内容(JSON格式)')
    difficulty = Column(Integer, comment='难度等级')
    total_score = Column(Integer, comment='总分')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')


class ExamPaperMapping(Base):
    """试卷-题目映射表：持久化 exam_id → 题号 → 题库真实ID 的对应关系。
    解决服务重启后内存映射丢失导致在线考试和阅卷模块找不到原题的 Bug。
    """
    __tablename__ = 'exam_paper_mapping'

    id = Column(Integer, primary_key=True, autoincrement=True)
    exam_id = Column(String(50), nullable=False, index=True, comment='考试编号/试卷编号')
    question_id = Column(Integer, nullable=False, comment='试卷内部顺序题号(1-57)')
    question_db_id = Column(Integer, nullable=False, comment='题库中题目的真实ID(关联question表)')
    question_type = Column(String(50), comment='题型')
    section = Column(String(200), comment='所属部分/大题名')
    full_score = Column(Float, default=0, comment='该题满分')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')
