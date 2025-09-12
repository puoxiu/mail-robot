# database.py
import mysql.connector
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
    ):
        """初始化MySQL连接管理器"""
        self.host = host
        self.user = user
        self.port = port
        self.password = password
        self.db_name = db_name
        self.conn: Optional[MySQLConnection] = None
        self._init_connection()
        self._init_tables()  # 确保表结构存在

    def _init_connection(self) -> None:
        """初始化数据库连接"""
        try:
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                port=self.port,
                password=self.password,
                database=self.db_name,
            )
            if self.conn.is_connected():
                print(f"成功连接到MySQL数据库: {self.db_name}")
        except Exception as e:
            print(f"MySQL连接失败: {str(e)}")
            raise

    def _init_tables(self) -> None:
        """初始化数据库表结构（如果不存在）"""
        if not self.conn or not self.conn.is_connected():
            self._init_connection()

        cursor = self.conn.cursor()
        
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
        
        self.conn.commit()
        cursor.close()

    def get_cursor(self, dictionary: bool = False) -> MySQLCursor:
        """获取数据库游标"""
        if not self.conn or not self.conn.is_connected():
            self._init_connection()
        return self.conn.cursor(dictionary=dictionary)

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        commit: bool = False,
        dictionary: bool = False
    ) -> List[Dict] | None:
        """
        执行SQL查询
        
        Args:
            query: SQL语句
            params: 查询参数
            commit: 是否需要提交事务（用于INSERT/UPDATE/DELETE）
            dictionary: 是否返回字典格式的结果
            
        Returns:
            查询结果（SELECT语句）或None（其他语句）
        """
        cursor = self.get_cursor(dictionary=dictionary)
        try:
            cursor.execute(query, params or ())
            if commit:
                self.conn.commit()
                return None
            # 对于SELECT语句，返回结果
            return cursor.fetchall()
        except Exception as e:
            print(f"SQL执行失败: {str(e)} | Query: {query}")
            if commit:
                self.conn.rollback()
            raise
        finally:
            cursor.close()

    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn and self.conn.is_connected():
            self.conn.close()
            print("MySQL连接已关闭")

    def __del__(self):
        """对象销毁时自动关闭连接"""
        self.close()
