from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .prompts_zh import CATEGORIZE_EMAIL_PROMPT
from .schema_outputs import CategorizeEmailOutput

class Agents:
    def __init__(self, model_name: str, base_url: str, api_key: str):
        self.model = ChatOpenAI(
             model=model_name,
             base_url=base_url,
             api_key=api_key,
             temperature=0,
        )

    def categorize_email_chain(self) -> RunnablePassthrough:
        email_category_prompt = PromptTemplate(
            template=CATEGORIZE_EMAIL_PROMPT,
            input_variables=["email_content"],
        )
        # 输出会是一个 Pydantic 对象：CategorizeEmailOutput 而不是普通字符串
        return email_category_prompt | self.model.with_structured_output(CategorizeEmailOutput)
