import os
import uuid
import docx
import sys

# Get the project root directory (parent of the current data_ingestion directory)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from banking_agents.rag.base_rag import BaseRAG

# Documents whose names match any of these prefixes go into loan_docs.
# All others go into policy_docs.
LOAN_DOC_KEYWORDS = [
    "loan_eligibility",
    "retail_credit",
    "corporate_lending",
    "msme_lending",
    "home_loan",
    "personal_loan",
    "loan_restructuring",
    "npa_management",
    "collateral_security",
    "credit_risk",
]

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

def is_loan_doc(filename: str) -> bool:
    """Returns True if the filename should go into the loan_docs collection."""
    name_lower = filename.lower()
    return any(keyword in name_lower for keyword in LOAN_DOC_KEYWORDS)

def main():
    docs_dir = os.path.join(os.path.dirname(__file__), "policy_documents")
    if not os.path.exists(docs_dir):
        print(f"Directory '{docs_dir}' not found.")
        return

    db_path = os.path.join(PROJECT_ROOT, "chroma_db")
    print(f"Initializing RAG database at '{db_path}'...")

    # Two separate collections
    policy_rag = BaseRAG(collection_name="policy_docs", db_path=db_path)
    loan_rag   = BaseRAG(collection_name="loan_docs",   db_path=db_path)

    policy_chunks, policy_metas, policy_ids = [], [], []
    loan_chunks,   loan_metas,   loan_ids   = [], [], []

    print(f"Reading documents from '{docs_dir}'...")
    for filename in sorted(os.listdir(docs_dir)):
        if not filename.endswith(".docx") or filename.startswith("~$"):
            continue

        file_path = os.path.join(docs_dir, filename)
        target = "loan_docs" if is_loan_doc(filename) else "policy_docs"
        print(f"  [{target}] Processing: {filename}")

        try:
            text   = extract_text_from_docx(file_path)
            chunks = chunk_text(text)

            for i, chunk in enumerate(chunks):
                meta = {"source": filename, "chunk_index": i}
                uid  = str(uuid.uuid4())
                if target == "loan_docs":
                    loan_chunks.append(chunk); loan_metas.append(meta); loan_ids.append(uid)
                else:
                    policy_chunks.append(chunk); policy_metas.append(meta); policy_ids.append(uid)

        except Exception as e:
            print(f"  ERROR processing {filename}: {e}")

    # Ingest into policy_docs
    if policy_chunks:
        print(f"\nIngesting {len(policy_chunks)} chunks -> policy_docs...")
        policy_rag.ingest(documents=policy_chunks, metadatas=policy_metas, ids=policy_ids)
        print("  policy_docs ingestion complete.")
    else:
        print("No policy documents found.")

    # Ingest into loan_docs
    if loan_chunks:
        print(f"\nIngesting {len(loan_chunks)} chunks -> loan_docs...")
        loan_rag.ingest(documents=loan_chunks, metadatas=loan_metas, ids=loan_ids)
        print("  loan_docs ingestion complete.")
    else:
        print("No loan documents found.")

    print("\nAll done!")

if __name__ == "__main__":
    main()
