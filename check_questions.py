import os
import pymysql

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'exam_system'),
    charset='utf8mb4'
)
cursor = conn.cursor()

# 检查段落匹配题目的 passage_text 分布
print("=== 段落匹配 passage 分布 ===")
cursor.execute("""
SELECT LEFT(passage_text, 100) as passage_head, COUNT(*) as count, GROUP_CONCAT(id) as ids
FROM question 
WHERE section = 'Reading Section B' AND answer IS NOT NULL AND answer != ''
GROUP BY passage_text
ORDER BY count DESC
LIMIT 10
""")

rows = cursor.fetchall()
print(f"共有 {len(rows)} 个不同的 passage")
for row in rows:
    print(f"\nPassage开头: {row[0]}...")
    print(f"题目数量: {row[1]}")

conn.close()