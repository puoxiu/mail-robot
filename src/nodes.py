from colorama import Fore, Style


from .tools.QQMailTools import QQMailTools
from .state import GraphState, Email
from .chains import Chains
from src.rag import RAGEngine


class Nodes:
    def __init__(self, model_name: str, base_url: str, api_key: str, rag_engine: RAGEngine):
        self.qq_mail_tools = QQMailTools()
        self.chains = Chains(model_name, base_url, api_key)
        self.rag_engine = rag_engine

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
        调用分类chain对邮件进行分类
        """
        print(Fore.BLUE + "正在分类邮件...\n" + Style.RESET_ALL)
        current_email = state["emails"][-1] 
        result = self.chains.categorize_email_chain().invoke({"email_content": current_email.body})
        print(Fore.MAGENTA + f"nodes info: 分类结果Email category: {result.category.value}" + Style.RESET_ALL)

        return {
            "email_category": result.category.value,
            "current_email": current_email
        }
    

    def construct_rag_queries(self, state: GraphState) -> GraphState:
        """
        调用RAG agent构造RAG查询
        """
        print(Fore.BLUE + "正在构造RAG查询...\n" + Style.RESET_ALL)
        email_content = state["current_email"].body
        query_result = self.chains.design_rag_queries_chain().invoke({"email_content": email_content})

        for query in query_result.queries:
            print(Fore.MAGENTA + f"nodes info: 构造RAG查询: {query}" + Style.RESET_ALL)
        
        return {
            "rag_queries": query_result.queries
        }
        
    
    def write_email(self, state: GraphState) -> GraphState:
        """
        调用邮件chain编写邮件
        """
        print(Fore.BLUE + "正在编写邮件...\n" + Style.RESET_ALL)

        # 1. 从state中获取所需信息（确保前置节点已存入这些数据）
        current_email = state.get("current_email")  # 当前处理的客户邮件
        email_category = state.get("email_category")  # 邮件分类结果
        rag_queries = state.get("rag_queries", [])  # RAG查询结果（可选，为空不影响）
        history_messages = state.get("writer_messages", [])  # 历史编写记录
        trials = state.get("trials", 0) + 1  # 重试次数

        email_information = (
            f"# 客户邮件内容：{current_email.body}\n"
            f"# 邮件分类：{email_category}\n"
            f"# RAG检索参考：{rag_queries if rag_queries else '无'}\n"
        )
        history_str = "\n".join(history_messages) if history_messages else "无历史沟通记录"

        email_result = self.chains.email_writer_chain().invoke({
            "email_information": email_information,  
            "history": history_str 
        })
        email_content = email_result.content
        print(Fore.MAGENTA + f"nodes info: 编写邮件内容: {email_content}" + Style.RESET_ALL)
        
        history_messages.append(f"# 第{trials}次编写结果：\n{email_content}")

        return {
            "generated_email": email_content, 
            "trials": trials,
            "writer_messages": history_messages
        }
    

    def verify_generated_email(self, state: GraphState) -> GraphState:
        """
        调用邮件chain校对邮件
        """
        print(Fore.BLUE + "正在校对邮件...\n" + Style.RESET_ALL)
        review = self.chains.email_proofreader_chain().invoke({
            "initial_email": state["current_email"].body,
            "generated_email": state["generated_email"],
        })
        writer_messages = state.get('writer_messages', [])
        writer_messages.append(f"# 校对结果：\n{review.reason}")

        return {
            "sendable": review.sendable,
            "writer_messages": writer_messages
        }
    

    def send_email(self, state: GraphState) -> GraphState:
        """
        发送邮件
        """
        print(Fore.BLUE + "正在发送邮件...\n" + Style.RESET_ALL)
        print(Fore.MAGENTA + f"nodes info: 原始邮件内容: {state['current_email']}" + Style.RESET_ALL)
        print(Fore.MAGENTA + f"nodes info: 发送邮件内容: {state['generated_email']}" + Style.RESET_ALL)
        self.qq_mail_tools.send_reply(
            state["current_email"],
            state["generated_email"]
        )
        return {"retrieved_documents": "", "trials": 0}
    
    def manual_pending(self, state: GraphState) -> GraphState:
        """
        手动处理邮件
        """
        print(Fore.BLUE + "正在手动处理邮件...\n" + Style.RESET_ALL)
        print(Fore.MAGENTA + f"{state}" + Style.RESET_ALL)
        return state
    
    def skip_unrelated_email(self, state: GraphState) -> GraphState:
        """
        跳过无关邮件(垃圾、广告邮件等)
        """
        print(Fore.BLUE + "正在跳过无关邮件...\n" + Style.RESET_ALL)
        print(Fore.MAGENTA + f"nodes info: 邮件内容: {state['current_email']}" + Style.RESET_ALL)
        state["emails"].pop()
        return state    
    
    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """
        从RAG中检索文档
        """
        print(Fore.BLUE + "正在从RAG中检索文档...\n" + Style.RESET_ALL)
        
        rag_queries = state.get("rag_queries", [])
        if not rag_queries:
            print(Fore.YELLOW + "警告：未获取到 RAG 查询，检索跳过" + Style.RESET_ALL)
            return {"retrieved_documents": "未提供有效查询，无检索结果", "retrieval_details": []}
        
        # 检索
        # 1. 直接检索
        direct_results = self.rag_engine.retrieve_direct(
            queries=rag_queries
        )
        # 2. HyDE检索
        hyde_results = self.rag_engine.retrieve_hyde(
            queries=rag_queries
        )
        # 3. 合并检索结果
        merged_results = self.rag_engine.merge_and_rerank(
            direct_results=direct_results,
            hyde_results=hyde_results,
        )
        
        # 4. 生成最终答案
        retrieved_str = ""
        retrieval_details = []  # 存储详细信息（用于调试）
        if merged_results:
            retrieved_str += f"找到 {len(merged_results)} 个相关参考信息：\n\n"
            for idx, doc in enumerate(merged_results, 1):
                # 只保留来源和内容（HyDE检索时补充匹配的问题）
                source = doc.get("source", "未知来源")
                content = doc.get("content", "无内容")
                matching_question = doc.get("matching_question", "")  # 仅HyDE有
                
                # 简化格式
                retrieved_str += f"{idx}. 来源：{source}\n"
                if matching_question:  # 若有匹配问题，简要说明
                    retrieved_str += f"（相关问题：{matching_question}）\n"
                retrieved_str += f"内容：{content}\n\n"
        else:
            retrieved_str = "未找到相关参考信息"

        print(Fore.MAGENTA + f"\n\nnodes info: RAG 检索结果：\n{retrieved_str}\n\n" + Style.RESET_ALL)
        
        return {"retrieved_documents": retrieved_str}
