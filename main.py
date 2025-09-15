
from dotenv import load_dotenv
load_dotenv()

import os
import sys
from colorama import Fore, Style
from src.graph import GraphWorkFlow

from src.utils.redis_utils import redis_conn
from src.utils.database import MySQLManager
from src.rag import RAGEngine
from src.utils.rabbitmq import MQClient


print(Fore.BLUE +f"============================================================================")
print(f"===============================加载环境变量=================================")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
print(f"BASE_URL: {os.getenv('BASE_URL')}")
print(f"MODEL_NAME: {os.getenv('MODEL_NAME')}")
print(f"EMBEDDING_MODEL_NAME: {os.getenv('EMBEDDING_MODEL_NAME')}")
print(f"EMBEDDING_API_KEY: {os.getenv('EMBEDDING_API_KEY')}")
print(f"EMAIL_FROM: {os.getenv('EMAIL_FROM')}")
print(f"SMTP_HOST: {os.getenv('SMTP_HOST')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT')}")
print(f"EMAIL_ACCOUNT: {os.getenv('EMAIL_ACCOUNT')}")
print(f"EMAIL_PASSWORD: {os.getenv('EMAIL_PASSWORD')}")
print(f"EMAIL_DELAY_HOURS: {os.getenv('EMAIL_DELAY_HOURS')}")
print(f"IMAP_HOST: {os.getenv('IMAP_HOST')}")
print(f"IMAP_PORT: {os.getenv('IMAP_PORT')}")
print(f"REDIS_HOST: {os.getenv('REDIS_HOST')}")
print(f"REDIS_PORT: {os.getenv('REDIS_PORT')}")
print(f"REDIS_DB: {os.getenv('REDIS_DB')}")
print(f"REDIS_PASSWORD: {os.getenv('REDIS_PASSWORD')}")
print(f"MYSQL_HOST: {os.getenv('MYSQL_HOST')}")
print(f"MYSQL_PORT: {os.getenv('MYSQL_PORT')}")
print(f"MYSQL_USER: {os.getenv('MYSQL_USER')}")
print(f"MYSQL_PASSWORD: {os.getenv('MYSQL_PASSWORD')}")
print(f"MYSQL_DB_NAME: {os.getenv('MYSQL_DB_NAME')}")

print(f"=============================================================================")
print(f"=============================================================================")

print(Fore.GREEN + "Starting workflow..." + Style.RESET_ALL)



# 检查 Redis
if not redis_conn:
    print(f"{Fore.RED}❌ Redis 初始化失败，程序终止{Style.RESET_ALL}")
    sys.exit(1)
else:
    print(f"{Fore.GREEN}✅ Redis 连接成功{Style.RESET_ALL}")



config = {'recursion_limit': 100}
initial_state = {
    "emails": [],
    "current_email_index": 0,
    "has_more": True,
    "current_email": {
      "id": "",
      "threadId": "",
      "messageId": "",
      "references": "",
      "sender": "",
      "subject": "",
      "body": ""
    },
    "email_category": "",
    "generated_email": "",
    "rag_queries": [],
    "retrieved_documents": "",
    "writer_messages": [],
    "sendable": False,
    "trials": 0
}


def main():
    db_manager = MySQLManager(
            host=os.getenv("MYSQL_HOST", ),
            port=int(os.getenv("MYSQL_PORT")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            db_name=os.getenv("MYSQL_DB_NAME")
        )
    
    mq_client = MQClient(
        host=os.getenv("RABBITMQ_HOST"),
        queue_name=os.getenv("RABBITMQ_QUEUE_NAME"),
    )
    
    rag_engine = RAGEngine(
        db_manager=db_manager,
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=os.getenv("BASE_URL"),
        chunk_vector_db_path=os.getenv("CHUNK_VECTOR_DB_PATH"),
        question_vector_db_path=os.getenv("QUESTION_VECTOR_DB_PATH"),
        dimensions=int(os.getenv("DIMENSIONS")),
        top_k=int(os.getenv("TOP_K")),
        chunk_size=int(os.getenv("CHUNK_SIZE")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP")),
    )

    graph = GraphWorkFlow(
        model_name=os.getenv('MODEL_NAME'),
        base_url=os.getenv('BASE_URL'),
        api_key=os.getenv('OPENAI_API_KEY'),
        rag_engine=rag_engine,
        mq_client=mq_client,
    )
    graph.display(path="./graph_png/graph_load_emails.png")

    for output in graph.graph.stream(initial_state, config):
        for key, value in output.items():
            print(Fore.CYAN + f"Finished running: {key}:" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
