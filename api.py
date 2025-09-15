from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import pika
import threading
import os
from dotenv import load_dotenv

load_dotenv()

from src.tools.QQMailTools import QQMailTools
from src.utils.rabbitmq import MQClient
from src.utils.database import MySQLManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=mq_client.consume_tasks, args=(consume_and_save_task,), daemon=True).start()
    yield
    # 关闭时
    if db:
        db.close_pool()
    if mq_client:
        mq_client.close()


app = FastAPI(
    title="邮件人工处理服务",
    version="1.0",
    lifespan=lifespan,
)

# 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # * 表示所有（不推荐生产用）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


try:
    db = MySQLManager(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        db_name=os.getenv("MYSQL_DB_NAME"),
        pool_size=10,
    )
    mq_client = MQClient(
        host=os.getenv("RABBITMQ_HOST"),
        queue_name=os.getenv("RABBITMQ_QUEUE_NAME"),
    )
    mail_tool = QQMailTools()
except Exception as e:
    print(f"初始化失败: {str(e)}")
    raise

def consume_and_save_task(ch, method, properties, body):
    try:
        task_data = json.loads(body)
        required_fields = ["email_id", "sender", "subject", "body", "created_at"]
        for field in required_fields:
            if field not in task_data:
                raise ValueError(f"缺少必要字段: {field}")
            
        db.execute_query("""
            INSERT INTO manual_email_tasks 
            (email_id, thread_id, sender, subject, body, category, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE status = 'pending'
        """, (
            task_data["email_id"],
            task_data.get("thread_id", ""),
            task_data["sender"],
            task_data["subject"],
            task_data["body"],
            task_data.get("category", ""),
            task_data["created_at"]
        ), commit=True)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"成功处理邮件任务: {task_data['email_id']}")
    except Exception as e:
        print(f"处理任务失败: {str(e)}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)       # 失败时重新入队


@app.get("/tasks", summary="get manual email tasks")
def get_tasks(status: str = "pending", page: int = 1, page_size: int = 20):
    try:
        if page < 1 or page_size < 1:
            raise HTTPException(status_code=400, detail="页码和页大小必须为正数")
        offset = (page - 1) * page_size
        tasks = db.execute_query("""
            SELECT * FROM manual_email_tasks 
            WHERE status = %s 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """, (status, page_size, offset), dictionary=True)
        
        # 查询总数（处理空结果情况）
        total_result = db.execute_query(
            "SELECT COUNT(*) as cnt FROM manual_email_tasks WHERE status = %s", 
            (status,), 
            dictionary=True
        )
        total = total_result[0]["cnt"] if total_result else 0
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "tasks": tasks or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务失败: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
