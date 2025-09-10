import redis
import os
from dotenv import load_dotenv
from colorama import Fore, Style

load_dotenv()

def get_redis_conn():
    """获取Redis连接（单例模式）"""
    if not hasattr(get_redis_conn, "conn"):
        try:
            get_redis_conn.conn = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD", ""),
                decode_responses=True,  # 自动将Redis返回的bytes转成字符串（简化操作）
                db=int(os.getenv("REDIS_DB", 0))
            )
            get_redis_conn.conn.ping()
        except Exception as e:
            get_redis_conn.conn = None 
    return get_redis_conn.conn

# 全局Redis连接实例（后续直接导入使用）
redis_conn = get_redis_conn()