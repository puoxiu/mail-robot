from langgraph.graph import StateGraph,END

from src.state import GraphState
from src.nodes import Nodes
from src.edges import Edges
from src.rag import RAGEngine

class GraphWorkFlow:
    def __init__(self, model_name: str, base_url: str, api_key: str, rag_engine: RAGEngine):
        workflow = StateGraph(GraphState)
        nodes = Nodes(model_name, base_url, api_key, rag_engine)
        edges = Edges()

        workflow.add_node("load_inbox_emails", nodes.load_new_emails)
        workflow.add_node("is_email_inbox_empty", nodes.is_email_inbox_empty)   # todo
        workflow.add_node("check_more_emails", nodes.check_more_emails)  # 检查是否有更多邮件

        workflow.add_node("get_next_email", nodes.get_next_email)  # 获取下一封邮件
        workflow.add_node("categorize_email", nodes.categorize_email)
        
        workflow.add_node("construct_rag_queries", nodes.construct_rag_queries)
        workflow.add_node("retrieve_from_rag", nodes.retrieve_from_rag)
        workflow.add_node("email_writer", nodes.write_email)
        workflow.add_node("email_proofreader", nodes.verify_generated_email)
        workflow.add_node("send_email", nodes.send_email)
        workflow.add_node("manual_pending", nodes.manual_pending)
        workflow.add_node("skip_unrelated_email", nodes.skip_unrelated_email)
        workflow.add_node("wait_for_next_check", nodes.wait_for_next_check)

        workflow.set_entry_point("load_inbox_emails")
        workflow.add_edge("load_inbox_emails", "is_email_inbox_empty")
        workflow.add_edge("is_email_inbox_empty", "check_more_emails")

        workflow.add_conditional_edges(
            "check_more_emails",
            edges.has_more_emails,
            {
                "True": "get_next_email",
                "False": "wait_for_next_check",
            },
        )

        workflow.add_edge("get_next_email", "categorize_email")

        workflow.add_conditional_edges(
            "categorize_email",
            edges.route_email_based_on_category,
            {
                "product related": "construct_rag_queries",
                "complaint_or_feedback": "email_writer",
                "unrelated": "skip_unrelated_email",
            },
        )
        workflow.add_edge("construct_rag_queries", "retrieve_from_rag")
        workflow.add_edge("retrieve_from_rag", "email_writer")
        workflow.add_edge("email_writer", "email_proofreader")
        workflow.add_conditional_edges(
            "email_proofreader",
            edges.is_email_sendable,
            {
                "send": "send_email",
                "rewrite": "email_writer",
                "stop": "manual_pending"
            },
        )
        # 各种处理结束后检查是否有更多邮件
        workflow.add_edge("send_email", "check_more_emails")
        workflow.add_edge("manual_pending", "check_more_emails")
        workflow.add_edge("skip_unrelated_email", "check_more_emails")
    

        # 等待一段时间后重新检查邮箱
        workflow.add_edge("wait_for_next_check", "load_inbox_emails")
        # workflow.add_edge("email_writer", END)

        self.graph = workflow.compile()

    
    def display(self, path: str):
        try:
            image_data = self.graph.get_graph().draw_mermaid_png()

            with open(path, "wb") as f:
                f.write(image_data)
            print(f"流程图已成功保存为 {path}")
        except Exception as e:
            print(f"保存流程图时出错: {e}")
