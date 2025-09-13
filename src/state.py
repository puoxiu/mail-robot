from typing import List, TypedDict, Annotated
from langgraph.graph import add_messages
from typing import Optional

from src.tools.schema_mail import Email

class GraphState(TypedDict):
    # 1. 多邮件处理必需字段
    emails: List[Email]  # 存储加载的所有邮件（Email 类型列表）
    current_email_index: int  # 跟踪当前处理的邮件索引（新增，解决循环问题）
    has_more: bool  # 标记是否有更多邮件待处理（新增，与 initial_state 对齐）
    
    # 2. 当前邮件信息（Email 类型，与 schema 一致）
    current_email: Optional[Email]  # 用 Optional 允许初始为 None，后续赋值
    
    # 3. 邮件分类与处理字段
    email_category: str  # 邮件分类结果（product/complaint/unrelated）
    generated_email: str  # 生成的回复邮件内容
    rag_queries: List[str]  # RAG 检索用的查询语句列表
    retrieved_documents: str  # RAG 检索到的文档内容
    
    # 4. LLM 对话与重试字段
    writer_messages: Annotated[list, add_messages]  # 邮件生成的对话历史
    sendable: bool  # 邮件是否可发送（校验结果）
    trials: int  # 重试次数（避免无限循环）