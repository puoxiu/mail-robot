# create_index.py
import os
from dotenv import load_dotenv
load_dotenv()
from src.utils.database import MySQLManager
from src.rag import RAGEngine
from langchain_openai import ChatOpenAI
from src.llm import get_llm
from colorama import Fore, Style


print(Fore.BLUE +f"============================================================================")
print(f"===============================加载环境变量=================================")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
print(f"BASE_URL: {os.getenv('BASE_URL')}")
print(f"MODEL_NAME: {os.getenv('MODEL_NAME')}")
print(f"EMBEDDING_MODEL_NAME: {os.getenv('EMBEDDING_MODEL_NAME')}")
print(f"EMBEDDING_API_KEY: {os.getenv('EMBEDDING_API_KEY')}")
print(f"DASHSCOPE_API_KEY: {os.getenv('DASHSCOPE_API_KEY')}")
print(f"EMAIL_FROM: {os.getenv('EMAIL_FROM')}")
print(f"SMTP_HOST: {os.getenv('SMTP_HOST')}")
print(f"SMTP_PORT: {os.getenv('SMTP_PORT')}")
print(f"EMAIL_ACCOUNT: {os.getenv('EMAIL_ACCOUNT')}")
print(f"EMAIL_PASSWORD: {os.getenv('EMAIL_PASSWORD')}")
print(f"EMAIL_DELAY_HOURS: {os.getenv('EMAIL_DELAY_HOURS')}")
print(f"IMAP_HOST: {os.getenv('IMAP_HOST')}")
print(f"IMAP_PORT: {os.getenv('IMAP_PORT')}")

print(f"=============================================================================")
print(f"=============================================================================")

print(Fore.GREEN + "Starting workflow..." + Style.RESET_ALL)

def load_documents_from_dir(data_dir: str):
    """加载目录下的所有文本文件"""
    docs = []
    for file in os.listdir(data_dir):
        path = os.path.join(data_dir, file)
        if os.path.isfile(path) and file.endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                docs.append((file, f.read()))
    return docs


def main():
    # 1. 初始化 MySQL 管理器
    db = MySQLManager(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        port=int(os.getenv("MYSQL_PORT")),
        database=os.getenv("MYSQL_DATABASE")
    )

    # 2. 初始化 RAG 引擎
    rag_engine = RAGEngine(
        db_manager=db,
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

    # 3. 初始化 LLM（生成 HyDE 问题）
    llm = get_llm(
        model_name=os.getenv("MODEL_NAME"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("BASE_URL"),
    )

    # 4. 加载文档
    docs = load_documents_from_dir(os.getenv("DATA_DIR"))

    # 5. 处理并存储
    for file_name, content in docs:
        chunk_count, question_count = rag_engine.process_document(
            document_content=content,
            source=file_name,
            llm=llm
        )
        print(f"✅ {file_name} 已处理: {chunk_count} chunks, {question_count} hyde questions")


if __name__ == "__main__":
    main()
