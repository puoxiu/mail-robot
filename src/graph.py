from langgraph.graph import StateGraph,END

from src.state import GraphState
from src.nodes import Nodes

class GraphWorkFlow:
    def __init__(self, model_name: str, base_url: str, api_key: str):
        workflow = StateGraph(GraphState)
        nodes = Nodes(model_name, base_url, api_key)

        workflow.add_node("load_inbox_emails", nodes.load_new_emails)
        workflow.add_node("is_email_inbox_empty", nodes.is_email_inbox_empty)   # todo
        workflow.add_node("categorize_email", nodes.categorize_email)
        

        workflow.set_entry_point("load_inbox_emails")
        
        workflow.add_edge("load_inbox_emails", "is_email_inbox_empty")
        workflow.add_edge("is_email_inbox_empty", "categorize_email")
        workflow.add_edge("categorize_email", END)


        self.graph = workflow.compile()

    
    def display(self, path: str):
        try:
            image_data = self.graph.get_graph().draw_mermaid_png()

            with open(path, "wb") as f:
                f.write(image_data)
            print(f"流程图已成功保存为 {path}")
        except Exception as e:
            print(f"保存流程图时出错: {e}")
