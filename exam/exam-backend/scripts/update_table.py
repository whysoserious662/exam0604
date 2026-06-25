"""更新数据库表结构，添加options字段"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from db.database import engine

def add_options_column():
    try:
        with engine.connect() as conn:
            # 添加 options 字段（先检查是否存在）
            result = conn.execute(text("SHOW COLUMNS FROM question LIKE 'options'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE question ADD COLUMN options TEXT"))
                print("已添加 options 字段")
            else:
                print("options 字段已存在")
            
            # 添加 source 字段
            result = conn.execute(text("SHOW COLUMNS FROM question LIKE 'source'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE question ADD COLUMN source VARCHAR(50)"))
                print("已添加 source 字段")
            else:
                print("source 字段已存在")
            
            # 添加 audio_url 字段
            result = conn.execute(text("SHOW COLUMNS FROM question LIKE 'audio_url'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE question ADD COLUMN audio_url VARCHAR(200)"))
                print("已添加 audio_url 字段")
            else:
                print("audio_url 字段已存在")
            
            conn.commit()
        print("表结构更新成功！")
    except Exception as e:
        print(f"更新失败: {e}")

if __name__ == "__main__":
    add_options_column()
