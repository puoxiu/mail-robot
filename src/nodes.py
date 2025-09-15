from colorama import Fore, Style
from typing import Dict, Any
from time import sleep
from langchain.schema import HumanMessage, AIMessage
from datetime import datetime

from .tools.QQMailTools import QQMailTools
from .state import GraphState, Email
from .chains import Chains
from src.rag import RAGEngine
from src.utils.rabbitmq import MQClient


class Nodes:
    def __init__(self, model_name: str, base_url: str, api_key: str, rag_engine: RAGEngine, mq_client: MQClient):
        self.qq_mail_tools = QQMailTools()
        self.chains = Chains(model_name, base_url, api_key)
        self.rag_engine = rag_engine
        self.mq_client = mq_client

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
    
    
    def check_more_emails(self, state: GraphState) -> Dict[str, Any]:
        """检查是否有更多邮件需要处理"""
        current_index = state["current_email_index"]
        total_emails = len(state["emails"])
        has_more = current_index < total_emails
        print(Fore.CYAN + f"🔍 check_more_emails：当前索引={current_index}，总邮件数={total_emails}，是否有更多={has_more}" + Style.RESET_ALL)
        return {**state, "has_more": has_more}
    


    def get_next_email(self, state: GraphState) -> GraphState:
        """进入此节点，必定有更多邮件需要处理，获取下一封邮件进行处理"""
        index = state["current_email_index"]
        next_index = index + 1

        return {
            **state,
            # 重置当前邮件相关的状态
            "current_email": state["emails"][index],
            "current_email_index": next_index,
            "email_category": "",
            "generated_email": "",
            "rag_queries": [],
            "retrieved_documents": "",
            "writer_messages": [],
            "sendable": False,
            "trials": 0
        }

    def categorize_email(self, state: GraphState) -> GraphState:
        """
        调用分类chain对邮件进行分类
        """
        print(Fore.BLUE + "正在分类邮件...\n" + Style.RESET_ALL)
        current_email = state["current_email"]
        result = self.chains.categorize_email_chain().invoke({"email_content": current_email.body})
        print(Fore.MAGENTA + f"nodes info: 分类结果Email category: {result.category.value}" + Style.RESET_ALL)

        return {
            **state,
            "email_category": result.category.value,
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
            **state,
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


        #  构造提示词（优化：从 Message 对象提取 content，避免字符串拼接错误）
        history_str_list = []
        for msg in history_messages:
            if isinstance(msg, HumanMessage):
                history_str_list.append(f"用户：{msg.content}")
            elif isinstance(msg, AIMessage):
                history_str_list.append(f"AI：{msg.content}")
        history_str = "\n".join(history_str_list) if history_str_list else "无历史沟通记录"

        email_information = (
            f"# 客户邮件内容：{current_email.body}\n"
            f"# 邮件分类：{email_category}\n"
            f"# RAG检索参考：{rag_queries if rag_queries else '无'}\n"
        )

        email_result = self.chains.email_writer_chain().invoke({
            "email_information": email_information,  
            "history": history_str 
        })
        email_content = email_result.content
        print(Fore.MAGENTA + f"nodes info: 编写邮件内容: {email_content}" + Style.RESET_ALL)
        
        # 4. 关键：追加 Message 对象（而非字符串），统一类型
        updated_history = history_messages + [
            HumanMessage(content=f"第{trials}次编写的输入信息：{email_information}"),
            AIMessage(content=f"第{trials}次编写结果：{email_content}")
        ]

        return {
            **state,
            "generated_email": email_content, 
            "trials": trials,
            "writer_messages": updated_history
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
            **state,
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
        return {
            **state,
            "retrieved_documents": "",  # 重置RAG检索结果（避免影响下一封邮件）
            "trials": 0  # 重置重试次数（避免下一封邮件继承重试计数）
        }
    
    def manual_pending(self, state: GraphState) -> GraphState:
        """
        手动处理邮件
        """
        print(Fore.BLUE + "正在手动处理邮件...\n" + Style.RESET_ALL)
        print(Fore.MAGENTA + f"{state}" + Style.RESET_ALL)
        
        current_email = state["current_email"]
        task_data = {
            "email_id": current_email.id,
            "thread_id": current_email.threadId,
            "sender": current_email.sender,
            "subject": current_email.subject,
            "body": current_email.body,
            "category": state["email_category"],
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        self.mq_client.publish_task(task_data)

        # todo : 更新redis状态
        
        return state
    
    def skip_unrelated_email(self, state: GraphState) -> GraphState:
        """
        跳过无关邮件(垃圾、广告邮件等)
        """
        print(Fore.BLUE + "正在跳过无关邮件...\n" + Style.RESET_ALL)
        print(Fore.MAGENTA + f"nodes info: 邮件内容: {state['current_email']}" + Style.RESET_ALL)
        current_email_idx = state["current_email_index"] - 1
        if 0 <= current_email_idx < len(state["emails"]):
            state["emails"].pop(current_email_idx)  # 删除当前处理的邮件
        else:
            print(Fore.YELLOW + f"警告：无效的邮件索引 {current_email_idx}，跳过删除" + Style.RESET_ALL)
        
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
        
        return {
            **state,
            "retrieved_documents": retrieved_str
        }


    def wait_for_next_check(self, state: GraphState) -> Dict[str, Any]:
        """等待一段时间后再检查新邮件"""
        # 从环境变量获取等待时间，默认为1小时
        wait_hours = 1
        print(f"所有邮件处理完毕，将在{wait_hours}小时后再次检查新邮件...")
        sleep(wait_hours * 3600) 
        return {
            **state,
            "emails": [],  # 清空旧邮件列表
            "current_email_index": 0,  # 重置索引为0
            "has_more": False,  # 重置为“无更多邮件”
            "current_email": None  # 清空当前邮件
        }