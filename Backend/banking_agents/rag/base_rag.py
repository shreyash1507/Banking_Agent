import os
import chromadb
from sentence_transformers import SentenceTransformer

class BaseRAG:
    """
    Abstract base class for RAG implementations using local BERT embeddings
    and ChromaDB for vector storage.
    """
    
    def __init__(self, collection_name: str, db_path: str = "./chroma_db"):
        self.collection_name = collection_name
        self.db_path = db_path
        
        # Load the local BERT model
        # all-MiniLM-L6-v2 is fast and efficient for standard retrieval tasks
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"Error loading embedding model: {e}")
            raise e
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        
        # Get or create the collection
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)
        
    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings using the local BERT model."""
        embeddings = self.embedding_model.encode(texts)
        return embeddings.tolist()
        
    def ingest(self, documents: list[str], metadatas: list[dict], ids: list[str]):
        """Ingests documents into the vector database."""
        embeddings = self._get_embeddings(documents)
        
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Ingested {len(documents)} documents into {self.collection_name}")
        
    def retrieve(self, query: str, n_results: int = 3) -> list[dict]:
        """Retrieves top k documents matching the query."""
        query_embedding = self._get_embeddings([query])
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        
        # Format the results into a more readable structure
        formatted_results = []
        if results['documents'] and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if 'distances' in results else None
                })
                
        return formatted_results
