"""彻底清空数据库"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import engine
from sqlalchemy import text

def clear_db():
    try:
        with engine.connect() as conn:
            # 先禁用外键检查
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            
            # 清空表
            conn.execute(text("TRUNCATE TABLE question"))
            
            # 启用外键检查
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            
            conn.commit()
        print("数据库已彻底清空！")
    except Exception as e:
        print(f"清空失败: {e}")

if __name__ == "__main__":
    clear_db()
