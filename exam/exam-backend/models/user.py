from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from db.database import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="bcrypt密码哈希")
    role = Column(String(20), nullable=False, default="student", comment="角色: student/teacher")
    email = Column(String(100), unique=True, nullable=False, comment="邮箱")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
