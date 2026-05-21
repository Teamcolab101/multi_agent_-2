

"""
RAG engine — loads hr_policy.txt into FAISS and answers HR policy questions.
Uses HuggingFace embeddings (no OpenAI key required for retrieval).
"""

import os
from typing import Optional

from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings




BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")

FAISS_PATH = os.path.join(DATA_DIR, "faiss_index")

POLICY_PATH = os.path.join(BASE_DIR, "data", "hr_policy.txt")
print("POLICY PATH =", POLICY_PATH)
print("FILE EXISTS =", os.path.exists(POLICY_PATH))


print(os.listdir(r"C:\Users\vamsh\OneDrive\Desktop\multi_agent_ 2\data"))

# 🔁 Global cache
_vectorstore: Optional[FAISS] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None


# ✅ Load embeddings once
def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


#  Build or load FAISS
def build_vectorstore(force_rebuild: bool = False) -> FAISS:
    global _vectorstore

    # Use cache
    if _vectorstore is not None and not force_rebuild:
        return _vectorstore

    emb = _get_embeddings()

    #  Try loading existing FAISS
    if os.path.exists(FAISS_PATH) and not force_rebuild:
        try:
            print(" Loading FAISS index...")
            _vectorstore = FAISS.load_local(
                FAISS_PATH,
                emb,
                allow_dangerous_deserialization=True
            )
            return _vectorstore
        except Exception as e:
            print("⚠️ FAISS load failed, rebuilding:", e)

    # ❌ If file missing → error
    if not os.path.exists(POLICY_PATH):
        raise FileNotFoundError(f"❌ Policy file not found: {POLICY_PATH}")

    print("🔨 Building FAISS index...")

    # 📄 Load document
    if POLICY_PATH.endswith(".txt"):
        loader = TextLoader(POLICY_PATH, encoding="utf-8")
        docs = loader.load()

    # ✂️ Split text
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80
    )
    chunks = splitter.split_documents(docs)

    # 🧠 Create vector store
    _vectorstore = FAISS.from_documents(chunks, emb)

    # 💾 Save FAISS
    os.makedirs(FAISS_PATH, exist_ok=True)
    _vectorstore.save_local(FAISS_PATH)

    return _vectorstore


# ✅ Retrieve relevant chunks
def search_policy(query: str, k: int = 4) -> str:
    vs = build_vectorstore()

    # ✅ Modern retriever (LangChain updated API)
    retriever = vs.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(query)

    if not docs:
        return "No relevant policy found."

    parts = []
    for i, doc in enumerate(docs, 1):
        snippet = doc.page_content.strip()
        parts.append(f"[Source {i}]\n{snippet}")

    return "\n\n".join(parts)


# ✅ Final response (simple RAG)
def hr_rag_response(query: str) -> str:
    try:
        context = search_policy(query)

        return f"""
📄 **HR Policy Answer**

{context}

---
❓ Question: {query}
"""
    except Exception as e:
        return f"⚠️ RAG Error: {str(e)}"


# ✅ Optional intent check (semantic instead of keyword spam)
def is_policy_question(query: str) -> bool:
    try:
        vs = build_vectorstore()
        retriever = vs.as_retriever(search_kwargs={"k": 1})
        docs = retriever.invoke(query)
        return len(docs) > 0
    except:
        return False