# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 【重要】请修改为你自己的 MySQL 连接信息
# 格式: mysql+pymysql://用户名:密码@主机地址:端口/数据库名?charset=utf8mb4
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/checkup_system?charset=utf8mb4"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,           # 设为 True 可以看到生成的 SQL 语句，方便调试
    pool_pre_ping=True,   # 自动检测并修复断开的连接
    pool_recycle=3600,    # 每小时回收一次连接，防止超时
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话的依赖项"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()