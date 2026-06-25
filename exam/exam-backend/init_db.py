import pymysql
import os
from dotenv import load_dotenv
load_dotenv()

db = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'exam_system'),
)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS `paper` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(200) DEFAULT NULL COMMENT '试卷标题',
  `content` longtext COMMENT '试卷内容(JSON格式)',
  `difficulty` int DEFAULT NULL COMMENT '难度等级',
  `total_score` int DEFAULT NULL COMMENT '总分',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS `exam_paper_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `exam_id` varchar(50) NOT NULL COMMENT '考试编号/试卷编号',
  `question_id` int NOT NULL COMMENT '试卷内部顺序题号(1-57)',
  `question_db_id` int NOT NULL COMMENT '题库中题目的真实ID(关联question表)',
  `question_type` varchar(50) DEFAULT NULL COMMENT '题型',
  `section` varchar(200) DEFAULT NULL COMMENT '所属部分/大题名',
  `full_score` float DEFAULT 0 COMMENT '该题满分',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_exam_id` (`exam_id`),
  KEY `idx_question_id` (`question_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS `exam_record` (
  `id` int NOT NULL AUTO_INCREMENT,
  `paper_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `score` int DEFAULT NULL,
  `status` varchar(20) DEFAULT 'ongoing',
  PRIMARY KEY (`id`),
  KEY `paper_id` (`paper_id`),
  KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS `student_answer` (
  `id` int NOT NULL AUTO_INCREMENT,
  `exam_id` varchar(50) DEFAULT NULL COMMENT '考试编号',
  `student_name` varchar(50) DEFAULT NULL COMMENT '学生姓名',
  `question_id` int NOT NULL COMMENT '题目ID（试卷内部顺序号 1-57）',
  `answer_text` text COMMENT '学生提交的答案',
  `submitted_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
  PRIMARY KEY (`id`),
  KEY `idx_exam_id` (`exam_id`),
  KEY `idx_student` (`exam_id`, `student_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
""")

db.commit()
print("数据库表初始化完成！")

cursor.execute("SELECT COUNT(*) FROM paper")
paper_count = cursor.fetchone()[0]
print(f"当前试卷数量: {paper_count}")

cursor.execute("SELECT COUNT(*) FROM question")
q_count = cursor.fetchone()[0]
print(f"当前题库题目数量: {q_count}")

cursor.execute("SELECT COUNT(*) FROM exam_paper_mapping")
mapping_count = cursor.fetchone()[0]
print(f"当前试卷映射数量: {mapping_count}")

db.close()
