from dotenv import load_dotenv
load_dotenv()
from src.tools.QQMailTools import QQMailTools



if __name__ == "__main__":
    mail_tool = QQMailTools()
    # # 收件（最近 N 小时未读邮件）
    emails = mail_tool.fetch_unanswered_emails(max_results=10)
    print(emails)

    # if emails:
    #     # 回复第一封邮件
    #     result = mail_tool.send_reply(emails[0], "你好，这是自动回复测试。")
    #     print(result)
