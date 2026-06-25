from sqlalchemy import Column, Integer, String, DateTime
from db.database import Base
from datetime import datetime

class KnowledgePoint(Base):
    __tablename__ = "knowledge_point"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), default="")
    subject = Column(String(50), default="英语四级")
    create_time = Column(DateTime, default=datetime.now)
