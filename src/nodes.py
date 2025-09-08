from colorama import Fore, Style


from .tools.QQMailTools import QQMailTools
from .state import GraphState, Email

class Nodes:
    def __init__(self):
        self.qq_mail_tools = QQMailTools()

    # 定义节点
    def load_new_emails(self, state: GraphState) -> GraphState:
        """
        加载新的未处理过的邮件
        """
        print(Fore.BLUE + "正在加载新邮件...\n" + Style.RESET_ALL)
        recent_emails = self.qq_mail_tools.fetch_unanswered_emails()
        emails = [Email(**email) for email in recent_emails]

        return {"emails": emails}
        
