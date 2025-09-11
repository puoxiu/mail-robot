import os
import uuid
from typing import List, Dict, Tuple, Optional

from openai import OpenAI
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.docstore.document import Document
from langchain_dashscope import DashScopeEmbeddings

from src.schema_outputs import RAGQueriesOutput
from src.utils.database import MySQLManager


class RAGEngine:
    def __init__(
        self,
        db_manager: MySQLManager,
        embedding_model_name: str,
        api_key: str,
        base_url: str,
        chunk_vector_db_path: str,
        question_vector_db_path: str,
        dimensions: int = 1024,
        top_k: int = 3,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """
        初始化 RAG 引擎
        params:
            embedding_model_name: 嵌入模型名称
            api_key: embedding model API 密钥
            base_url: OpenAI API 基础 URL
            dimensions: 嵌入维度, 默认为 1024
            top_k: 检索文档数量, 默认为 3
            chunk_size: 文档块大小, 默认为 500
            chunk_overlap: 文档块重叠大小, 默认为 50
        """
        self.embedding_model_name = embedding_model_name
        self.dimensions = dimensions
        self.top_k = top_k
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.db_manager = db_manager

        # 初始化 Embedding 客户端 
        self.embedding_client = OpenAI(api_key=api_key, base_url=base_url)

        # 初始化 LangChain 的 Embeddings 封装，用于 Chroma
        self.embedding_model = DashScopeEmbeddings(
            model=embedding_model_name,
            api_key=api_key
        )

        # 初始化 Chroma
        self.chunk_vector_db = Chroma(
            persist_directory=chunk_vector_db_path,
            embedding_function=self.embedding_model,
            collection_name="document_chunks"
        )
        self.question_vector_db = Chroma(
            persist_directory=question_vector_db_path,
            embedding_function=self.embedding_model,
            collection_name="hyde_questions"
        )

        # 初始化文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """调用 embedding 模型生成向量 (直接 API 调用，用于自定义逻辑)"""
        try:
            response = self.embedding_client.embeddings.create(
                model=self.embedding_model_name,
                input=texts,
                encoding_format="float",
                dimensions=self.dimensions,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"Embedding 嵌入生成失败: {e}")
            raise

    def _generate_hyde_questions(self, chunk_content: str, llm: ChatOpenAI) -> List[str]:
        """基于文档块生成反向 HyDE 问题"""
        prompt = """
        你是一个问题生成专家。
        请基于以下文档内容，生成一组可能的用户问题。这些问题必须：
        1. 与文档内容高度相关，可以通过该文档得到回答；
        2. 覆盖不同角度（例如：定义、关键细节、应用场景、原因结果、优缺点等）；
        3. 数量不固定，根据内容信息量而定（一般 3-5 个即可，但是不强制要求，且不要冗余）；
        4. 每个问题应简洁、清晰。

        文档内容:
        {chunk_content}

        请必须返回 JSON 格式：
        {{
            "queries": ["问题1", "问题2", "问题3"]
        }}
        """
        try:
            generate_query_prompt = PromptTemplate(
                template=prompt,
                input_variables=["chunk_content"],
            )
            chain = generate_query_prompt | llm.with_structured_output(RAGQueriesOutput)
            result = chain.invoke({"chunk_content": chunk_content})
            return result.queries
        except Exception as e:
            print(f"Prompt 模板生成失败: {e}")
            return []

    def process_document(
        self,
        document_content: str,
        document_id: Optional[str] = None,
        source: str = "unknown",
        llm: ChatOpenAI = None
    ) -> Tuple[int, int]:
        """分割并存储文档，生成 HyDE 问题"""
        if not document_id:
            document_id = str(uuid.uuid4())

        # 1. 分割文档块
        chunks = self.text_splitter.split_text(document_content)
        chunk_count = len(chunks)
        question_count = 0

        # 2. 处理每个文档块
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())

            # 3. 存储到向量库
            doc = Document(
                page_content=chunk,
                metadata={
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "source": source,
                    "chunk_index": i
                }
            )
            self.chunk_vector_db.add_documents([doc])

            # 4. 存储文档块元数据到 MySQL
            self.db_manager.execute_query("""
                INSERT INTO chunk_metadata 
                (chunk_id, source, document_id, chunk_index)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                source = VALUES(source), 
                document_id = VALUES(document_id),
                chunk_index = VALUES(chunk_index)
                """, (chunk_id, source, document_id, i), commit=True)

            # 5. 为文档块生成 HyDE 问题
            questions = self._generate_hyde_questions(chunk, llm)
            question_count += len(questions)

            if questions:
                # 6. 存储问题及其向量
                question_ids = [str(uuid.uuid4()) for _ in questions]
                question_docs = [
                    Document(
                        page_content=question,
                        metadata={"question_id": qid, "chunk_id": chunk_id}
                    )
                    for qid, question in zip(question_ids, questions)
                ]
                self.question_vector_db.add_documents(question_docs)

                # 存储问题与文档块的映射关系
                for qid, question in zip(question_ids, questions):
                    self.db_manager.execute_query("""
                    INSERT INTO question_chunk_mapping 
                    (question_id, chunk_id, question_content)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    question_content = VALUES(question_content)
                    """, (qid, chunk_id, question), commit=True)

        return chunk_count, question_count

    def retrieve_direct(self, queries: List[str], top_k: int = 3) -> List[Dict]:
        """直接根据用户 query 检索文档块"""
        all_results = []
        for query in queries:
            query_embedding = self._embed_texts([query])[0]
            results = self.chunk_vector_db.similarity_search_by_vector(
                embedding=query_embedding,
                k=top_k
            )

            for doc in results:
                all_results.append({
                    "chunk_id": doc.metadata.get("chunk_id"),
                    "content": doc.page_content,
                    "source": doc.metadata.get("source"),
                    "document_id": doc.metadata.get("document_id"),
                    "retrieval_path": "direct",
                    "score": 0.0
                })
        return all_results

    def retrieve_hyde(self, queries: List[str], top_k: int = 3) -> List[Dict]:
        """根据 HyDE 问题检索文档块"""
        all_results = []
        for query in queries:
            query_embedding = self._embed_texts([query])[0]
            similar_questions = self.question_vector_db.similarity_search_by_vector(
                embedding=query_embedding,
                k=top_k
            )

            question_ids = [q.metadata.get("question_id") for q in similar_questions if q.metadata.get("question_id")]
            if not question_ids:
                continue

            placeholders = ", ".join(["%s"] * len(question_ids))
            mappings = self.db_manager.execute_query(f"""
            SELECT qcm.chunk_id, qcm.question_content, cm.source, cm.document_id
            FROM question_chunk_mapping qcm
            JOIN chunk_metadata cm ON qcm.chunk_id = cm.chunk_id
            WHERE qcm.question_id IN ({placeholders})
            """, tuple(question_ids), dictionary=True)

            if not mappings:
                continue

            for mapping in mappings:
                chunk_id = mapping["chunk_id"]
                chunks = self.chunk_vector_db.get(
                    where={"chunk_id": chunk_id},
                    limit=1
                )
                if chunks and chunks["documents"]:
                    all_results.append({
                        "chunk_id": chunk_id,
                        "content": chunks["documents"][0],
                        "source": mapping["source"],
                        "document_id": mapping["document_id"],
                        "matching_question": mapping["question_content"],
                        "retrieval_path": "hyde",
                        "score": 0.0
                    })
        return all_results

    def merge_and_rerank(
        self, 
        direct_results: List[Dict], 
        hyde_results: List[Dict], 
        query: str,
        top_n: int = 8,
        score_threshold: float = 0.5
    ) -> List[Dict]:
        """合并 direct + HyDE 检索结果，并去重 + 排序"""
        chunk_map = {}
        for result in direct_results + hyde_results:
            chunk_id = result["chunk_id"]
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = result
            else:
                if result.get("score", 0) > chunk_map[chunk_id].get("score", 0):
                    chunk_map[chunk_id] = result

        results = list(chunk_map.values())
        return results
