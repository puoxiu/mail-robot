from .state import GraphState
from colorama import Fore, Style



class Edges:
    def is_email_inbox_empty(self, state: GraphState) -> str:
        """
        路由函数，根据收件箱是否为空路由到不同的节点
        """
        print(Fore.YELLOW + "Checking if email inbox is empty...\n" + Style.RESET_ALL)
        if len(state["emails"]) == 0:
            print(Fore.GREEN + "收件箱为空，没有邮件需要处理" + Style.RESET_ALL)
            return "True"
        else:
            return "False"

    def route_email_based_on_category(self, state: GraphState) -> str:
        """
        路由函数，根据邮件分类路由到不同的节点
        """
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)
        category = state["email_category"]
        if category == "product_enquiry":
            return "product related"
        elif category == "customer_complaint" or category == "customer_feedback":
            return "complaint_or_feedback"
        else:
            return "unrelated"

    def is_email_sendable(self, state: GraphState) -> str:
        """
        路由函数，根据邮件是否可发送路由到不同的节点
        """
        email_sendable = state["sendable"]
        if email_sendable:
            print(Fore.GREEN + "不需要重写，直接发送" + Style.RESET_ALL)
            state["emails"].pop()
            state["writer_messages"] = []
            return "send"
        elif state["trials"] >= 3:
            print(Fore.RED + "超过最大重试次数，必须停止" + Style.RESET_ALL)
            state["emails"].pop()
            state["writer_messages"] = []
            return "stop"
        else:
            print(Fore.RED + "需要重写" + Style.RESET_ALL)
            return "rewrite"