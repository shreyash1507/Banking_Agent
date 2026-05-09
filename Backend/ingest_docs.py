import os
import uuid
import docx
import sys

# Ensure banking_agents is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from banking_agents.rag.base_rag import BaseRAG

def extract_text_from_docx(file_path):
    """Extracts text from a .docx file."""
    doc = docx.Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    return "\n".join(full_text)

def chunk_text(text, chunk_size=1000, overlap=200):
    """Simple text chunking by characters with overlap."""
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= text_length:
            break
        start += (chunk_size - overlap)
        
    return chunks

def main():
    docs_dir = os.path.join(os.path.dirname(__file__), "Policy docs for RAG")
    if not os.path.exists(docs_dir):
        print(f"Directory '{docs_dir}' not found.")
        return

    # Initialize RAG for policies
    print("Initializing RAG database...")
    rag = BaseRAG(collection_name="policy_docs")
    
    all_chunks = []
    all_metadatas = []
    all_ids = []

    print(f"Reading documents from '{docs_dir}'...")
    
    for filename in os.listdir(docs_dir):
        if filename.endswith(".docx"):
            file_path = os.path.join(docs_dir, filename)
            print(f"Processing: {filename}")
            
            try:
                # 1. Extract text
                text = extract_text_from_docx(file_path)
                
                # 2. Chunk text
                chunks = chunk_text(text)
                
                # 3. Prepare data for ingestion
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_metadatas.append({
                        "source": filename,
                        "chunk_index": i
                    })
                    # Create a unique ID for each chunk
                    all_ids.append(str(uuid.uuid4()))
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")

    # Ingest all chunks into ChromaDB
    if all_chunks:
        print(f"Ingesting {len(all_chunks)} total chunks into ChromaDB...")
        rag.ingest(documents=all_chunks, metadatas=all_metadatas, ids=all_ids)
        print("Ingestion complete! The agent can now access these policies.")
    else:
        print("No content found to ingest.")

if __name__ == "__main__":
    main()
