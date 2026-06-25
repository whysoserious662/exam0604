from db.database import SessionLocal
from models.question import Question

db = SessionLocal()
total = db.query(Question).count()
print(f"数据库里总共有 {total} 道题！")
db.close()