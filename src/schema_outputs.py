from pydantic import BaseModel, Field
from enum import Enum
from typing import List



class EmailCategory(str, Enum):
    product_enquiry = "product_enquiry"
    customer_complaint = "customer_complaint"
    customer_feedback = "customer_feedback"
    unrelated = "unrelated"

class CategorizeEmailOutput(BaseModel):
    category: EmailCategory = Field(
        ..., 
        description="The category assigned to the email, indicating its type based on predefined rules."
    )


class RAGQueriesOutput(BaseModel):
    queries: List[str] = Field(
        ..., 
        description="A list of up to three questions representing the customer's intent, based on their email."
    )

class EmailWriterOutput(BaseModel):
    content: str = Field(
        ..., 
        description="The final email content, formatted as a string, ready to be sent to the customer."
    )


class EmailProofreaderOutput(BaseModel):
    reason: str = Field(
        ..., 
        description="Detailed reason why the email is or is not sendable."
    )
    sendable: bool = Field(
        ..., 
        description="Indicates whether the email is sendable (true) or not (false)."
    )

