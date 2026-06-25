from sqlalchemy import Column, Integer, String, Float
from db.database import Base

class ExamRecord(Base):
    __tablename__ = "exam_record"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(String(50), nullable=False, index=True)
    student_name = Column(String(50), nullable=False)
    class_name = Column(String(50), default="")
    question_id = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    full_score = Column(Float, nullable=False, default=1.0)
