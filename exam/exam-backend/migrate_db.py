"""数据库迁移：添加新字段 + 创建 answer_sheet 表"""
from db.database import engine, Base
from sqlalchemy import text


def migrate():
    """添加 question 表新字段 + 创建 answer_sheet 表"""
    columns = [
        ("difficulty_detail", "JSON DEFAULT NULL COMMENT '难度分析详情'"),
        ("options", "JSON DEFAULT NULL COMMENT '选项列表'"),
        ("question_number", "INT DEFAULT NULL COMMENT '题号'"),
        ("section", "VARCHAR(100) DEFAULT NULL COMMENT '所属大题'"),
        ("source", "VARCHAR(200) DEFAULT NULL COMMENT '来源试卷'"),
        ("passage_text", "TEXT DEFAULT NULL COMMENT '原文段落(阅读题)'"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in columns:
            try:
                conn.execute(text(f"ALTER TABLE question ADD COLUMN `{col_name}` {col_def}"))
                conn.commit()
                print(f"  [+] 添加列 {col_name}")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print(f"  [~] 列 {col_name} 已存在，跳过")
                else:
                    print(f"  [!] 添加 {col_name} 失败: {e}")

    # 创建 answer_sheet 表
    from models.answer_sheet import AnswerSheet
    Base.metadata.create_all(bind=engine, tables=[AnswerSheet.__table__])
    print("  [+] 创建 answer_sheet 表")


if __name__ == "__main__":
    print("开始数据库迁移...")
    migrate()
    print("迁移完成")
