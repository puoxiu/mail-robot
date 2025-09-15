import mysql.connector
from mysql.connector import pooling
from mysql.connector.connection import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from typing import Optional, Dict, List, Tuple


class MySQLManager:
    def __init__(
        self,
        host: str,
        user: str,
        port: int,
        password: str = "",
        db_name: str = "rag_hyde",
        pool_name: str = "mysql_pool",
        pool_size: int = 5,
        pool_reset_session: bool = True
    ):
        self.host = host
        self.user = user
        self.port = port
        self.password = password
        self.db_name = db_name
        self.pool_name = pool_name
        self.pool_size = pool_size
        self.pool_reset_session = pool_reset_session
        self.pool: Optional[pooling.MySQLConnectionPool] = None
        self._init_pool()  # 初始化连接池
        self._init_tables()  # 确保表结构存在

    def _init_pool(self) -> None:
        """初始化数据库连接池"""
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name=self.pool_name,
                pool_size=self.pool_size,
                pool_reset_session=self.pool_reset_session,
                host=self.host,
                user=self.user,
                port=self.port,
                password=self.password,
                database=self.db_name,
            )
            print(f"成功创建MySQL连接池: {self.pool_name} (大小: {self.pool_size})")
        except Exception as e:
            print(f"MySQL连接池创建失败: {str(e)}")
            raise

    def get_connection(self) -> MySQLConnection:
        """从连接池获取连接"""
        if not self.pool:
            self._init_pool()
        return self.pool.get_connection()

    def _init_tables(self) -> None:
        """初始化数据库表结构（使用连接池中的连接）"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # 创建问题-文档块映射表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_chunk_mapping (
                id INT AUTO_INCREMENT PRIMARY KEY,
                question_id VARCHAR(36) NOT NULL,
                chunk_id VARCHAR(36) NOT NULL,
                question_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_question_chunk (question_id, chunk_id)
            )
            """)
            
            # 创建文档块元数据表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunk_metadata (
                chunk_id VARCHAR(36) PRIMARY KEY,
                source VARCHAR(255) NOT NULL,
                document_id VARCHAR(36) NOT NULL,
                chunk_index INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 添加manual_email_tasks表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_email_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email_id VARCHAR(100) UNIQUE NOT NULL,
                thread_id VARCHAR(100),
                sender VARCHAR(255) NOT NULL,
                subject VARCHAR(255) NOT NULL,
                body TEXT NOT NULL,
                category VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                created_at DATETIME NOT NULL,
                processed_at DATETIME,
                operator VARCHAR(100),
                reply_content TEXT,
                reply_id VARCHAR(100),
                remark TEXT
            )
            """)
            
            conn.commit()
            cursor.close()
        except Exception as e:
            conn.rollback()
            print(f"表结构初始化失败: {str(e)}")
            raise
        finally:
            conn.close()  # 归还连接到池

    def get_cursor(self, conn: MySQLConnection, dictionary: bool = False) -> MySQLCursor:
        """基于指定连接获取游标"""
        return conn.cursor(dictionary=dictionary)

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        commit: bool = False,
        dictionary: bool = False
    ) -> List[Dict] | None:
        """
        执行SQL查询（使用连接池管理连接）
        
        Args:
            query: SQL语句
            params: 查询参数
            commit: 是否需要提交事务
            dictionary: 是否返回字典格式的结果
            
        Returns:
            查询结果（SELECT语句）或None（其他语句）
        """
        conn = self.get_connection()  # 从池获取连接
        cursor = self.get_cursor(conn, dictionary=dictionary)
        try:
            cursor.execute(query, params or ())
            if commit:
                conn.commit()
                return None
            return cursor.fetchall()
        except Exception as e:
            print(f"SQL执行失败: {str(e)} | Query: {query}")
            if commit:
                conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()  # 归还连接到池（关键！）

    def close_pool(self) -> None:
        """关闭连接池"""
        if self.pool:
            # 注意：mysql-connector-python的连接池没有显式关闭方法
            # 这里仅做标记，实际连接会在闲置超时后自动关闭
            print(f"MySQL连接池 {self.pool_name} 已关闭")
            self.pool = None

    def __del__(self):
        """对象销毁时关闭连接池"""
        self.close_pool()