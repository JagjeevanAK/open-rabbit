from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain.schema import Document
from dotenv import load_dotenv
from client.client import app
import re

load_dotenv()

def split_code_by_function(snippet: str, language: str = "unknown", max_lines: int = 20, overlap: int = 5):
    """
    Splits code snippet into chunks based on lines.
    - snippet: code or config snippet
    - max_lines: max number of lines per chunk
    - overlap: lines of overlap between chunks
    """
    lines = snippet.splitlines()
    if len(lines) <= max_lines:
        return [Document(page_content=snippet, metadata={"language": language, "type": "raw_snippet"})]

    chunks = []
    for i in range(0, len(lines), max_lines - overlap):
        chunk_lines = lines[i:i + max_lines]
        chunk_text = "\n".join(chunk_lines).strip()
        if chunk_text:
            chunks.append(Document(page_content=chunk_text, metadata={"language": language, "type": "raw_snippet"}))
    return chunks

@app.task
def index_code():
    chunks = split_code_by_function('')
    embeddings = OpenAIEmbeddings(model='text-embedding-large')

    QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        url = 'http://localhost:6333/',
        collection_name='Rag-learning'
    )
    return "Created vector embeddings"