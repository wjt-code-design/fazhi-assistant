import os
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 路径锚定到本文件所在目录，避免换个目录启动就找不到数据库
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Embeddings — BGE-base-zh 本地运行（比 large 更快更省，法律条文场景质量足够；数据量大时可升级回 large）
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-zh-v1.5",
    model_kwargs={"device": "cpu"},
)

# 2. Vector store — Chroma 持久化到本地目录
vectorstore = Chroma(
    persist_directory=os.path.join(BASE_DIR, "chroma_db"),
    embedding_function=embeddings,
    collection_name="legal_provisions",
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 3. LLM — GLM-4.7-Flash 走 OpenAI 兼容协议（可用环境变量 LLM_MODEL 切换模型）
llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "glm-4.7-flash"),
    api_key=os.getenv("ZHIPUAI_API_KEY"),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    streaming=True,
)

# 4. Prompt
prompt = ChatPromptTemplate.from_template("""你是一名专业的法律咨询助手。请根据以下法律条文回答用户问题。

相关法律条文：
{context}

用户问题：{question}

要求：
1. 只依据上述条文回答，不编造
2. 引用时标注来源（如"根据《劳动合同法》第十九条"）
3. 条文不足时说明"根据现有资料无法完整回答"
4. 回答控制在 300 字以内

回答：""")

# 5. RAG Chain (LCEL 管道)
def format_docs(docs):
    return "\n\n".join(f"[{d.metadata.get('source', '')} {d.metadata.get('article', '')}] {d.page_content}" for d in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
