from typing import List, TypedDict, Annotated
from langgraph.graph import add_messages

from src.tools.schema_mail import Email

class GraphState(TypedDict):
    emails: List[Email]
    current_email: Email
    email_category: str
    generated_email: str
    rag_queries: List[str]
    retrieved_documents: str
    writer_messages: Annotated[list, add_messages]
    sendable: bool
    trials: int