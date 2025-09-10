from colorama import Fore, Style


from .tools.QQMailTools import QQMailTools
from .state import GraphState, Email
from .agents import Agents

class Nodes:
    def __init__(self, model_name: str, base_url: str, api_key: str):
        self.qq_mail_tools = QQMailTools()
        self.agents = Agents(model_name, base_url, api_key)

    # 定义节点
    def load_new_emails(self, state: GraphState) -> GraphState:
        """
        加载新的未处理过的邮件
        """
        print(Fore.BLUE + "正在加载新邮件...\n" + Style.RESET_ALL)
        recent_emails = self.qq_mail_tools.fetch_unanswered_emails()
        emails = [Email(**email) for email in recent_emails]
        return {"emails": emails}
        
    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        """
        Check if the email inbox is empty.
        """
        return state
    

    def categorize_email(self, state: GraphState) -> GraphState:
        """
        调用分类agent对邮件进行分类
        """
        print(Fore.BLUE + "正在分类邮件...\n" + Style.RESET_ALL)
        current_email = state["emails"][-1] 
        result = self.agents.categorize_email_chain().invoke({"email_content": current_email.body})
        print(Fore.MAGENTA + f"分类结果Email category: {result.category.value}" + Style.RESET_ALL)

        return {
            "email_category": result.category.value,
            "current_email": current_email
        }