from .state import GraphState
from colorama import Fore, Style



class Edges:
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
