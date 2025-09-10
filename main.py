
from dotenv import load_dotenv
load_dotenv()

import os
import sys
from colorama import Fore, Style
from src.graph import GraphWorkFlow

from src.utils.redis_utils import redis_conn


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
    graph = GraphWorkFlow(
        model_name=os.getenv('MODEL_NAME'),
        base_url=os.getenv('BASE_URL'),
        api_key=os.getenv('OPENAI_API_KEY'),
    )
    graph.display(path="./graph_png/graph_load_emails.png")

    for output in graph.graph.stream(initial_state, config):
        for key, value in output.items():
            print(Fore.CYAN + f"Finished running: {key}:" + Style.RESET_ALL)


if __name__ == "__main__":
    main()
