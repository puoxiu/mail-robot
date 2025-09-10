from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .prompts_zh import (
    CATEGORIZE_EMAIL_PROMPT,
    GENERATE_RAG_QUERIES_PROMPT,
    EMAIL_WRITER_PROMPT,
    EMAIL_PROOFREADER_PROMPT,
)
from .schema_outputs import CategorizeEmailOutput, RAGQueriesOutput, EmailWriterOutput, EmailProofreaderOutput

class Agents:
    def __init__(self, model_name: str, base_url: str, api_key: str):
        self.model1 = ChatOpenAI(
             model=model_name,
             base_url=base_url,
             api_key=api_key,
             temperature=0,
        )
        self.model2 = ChatOpenAI(
             model=model_name,
             base_url=base_url,
             api_key=api_key,
             temperature=0.7,
        )

    def categorize_email_chain(self) -> RunnablePassthrough:
        email_category_prompt = PromptTemplate(
            template=CATEGORIZE_EMAIL_PROMPT,
            input_variables=["email_content"],
        )
        # 输出会是一个 Pydantic 对象：CategorizeEmailOutput 而不是普通字符串
        return email_category_prompt | self.model1.with_structured_output(CategorizeEmailOutput)


    def design_rag_queries_chain(self) -> RunnablePassthrough:
        generate_query_prompt = PromptTemplate(
            template=GENERATE_RAG_QUERIES_PROMPT,
            input_variables=["email_content"],
        )
        return generate_query_prompt | self.model1.with_structured_output(RAGQueriesOutput)


    def email_writer_chain(self) -> RunnablePassthrough:
        writer_prompt = PromptTemplate(
            template=EMAIL_WRITER_PROMPT,
            input_variables=["email_information", "history"], 
        )
        return writer_prompt | self.model2.with_structured_output(EmailWriterOutput)

    def email_proofreader_chain(self) -> RunnablePassthrough:
        proofreader_prompt = PromptTemplate(
            template=EMAIL_PROOFREADER_PROMPT,
            input_variables=["initial_email", "generated_email"],
        )
        return proofreader_prompt | self.model2.with_structured_output(EmailProofreaderOutput)