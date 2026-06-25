from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from db.database import Base


class AnswerSheet(Base):
    __tablename__ = "answer_sheet"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(300), comment="解析PDF文件名")
    pdf_path = Column(String(500), comment="文件存储路径")
    year_month = Column(String(10), comment="匹配键：年份月份 e.g. 2025.12")
    suite_number = Column(Integer, comment="匹配键：第几套")
    has_extracted_text = Column(Boolean, default=False, comment="是否成功提取到文字")
    full_text = Column(Text, comment="PDF全文（文字版）")
    answers_json = Column(JSON, comment="解析出的答案 [{question_number, answer, analysis, type}]")
    matched_exam_source = Column(String(300), comment="匹配到的真题source")
    match_count = Column(Integer, default=0, comment="成功匹配题目数量")
    created_at = Column(DateTime, server_default=func.now())
