from sqlalchemy import Column, Integer, String, Text, JSON, Float
from db.database import Base


class Question(Base):
    __tablename__ = "question"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, comment="题干")
    type = Column(String(20), comment="题型")
    difficulty = Column(String(10), comment="难度")
    answer = Column(Text, comment="答案")
    analysis = Column(Text, comment="解析")
    knowledge_id = Column(Integer)
    score = Column(Integer, default=1)
    source = Column(String(200), comment="来源试卷")
    audio_url = Column(String(255))
    options = Column(JSON, comment="选项列表")
    passage_text = Column(Text, comment="原文段落")
    question_number = Column(Integer, comment="题号")
    section = Column(String(100), comment="所属部分")
    image_url = Column(String(255))
    latex_formula = Column(Text)
    difficulty_detail = Column(JSON, comment="难度分析详情")
    difficulty_elo = Column(Float, comment="Elo动态难度分")


class KnowledgePoint(Base):
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    parent_id = Column(Integer, default=None)
