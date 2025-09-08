
from dotenv import load_dotenv
import os
from colorama import Fore, Style
from src.graph import GraphWorkFlow

load_dotenv()


print(Fore.BLUE +f"===============================加载环境变量=================================")
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

print(Fore.GREEN + "Starting workflow..." + Style.RESET_ALL)


graph = GraphWorkFlow()
graph.display(path="./graph_png/graph_load_emails.png")



