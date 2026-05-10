import os
import logging
import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class BaseRAG:
    """
    Base class for RAG implementations using local BERT embeddings
    and ChromaDB for vector storage.
    """

    def __init__(self, collection_name: str, db_path: str = "./chroma_db"):
        self.collection_name = collection_name
        self.db_path = db_path
        logger.info("[BaseRAG] Initializing BaseRAG | Collection: '%s' | DB path: '%s'", collection_name, db_path)

        # Load the local BERT model
        # all-MiniLM-L6-v2 is fast and efficient for standard retrieval tasks
        try:
            logger.debug("[BaseRAG] Loading local embedding model: 'all-MiniLM-L6-v2'...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("[BaseRAG] Embedding model 'all-MiniLM-L6-v2' loaded successfully.")
        except Exception as e:
            logger.error("[BaseRAG] Error loading embedding model: %s", e, exc_info=True)
            raise e

        # Initialize ChromaDB client
        logger.debug("[BaseRAG] Connecting to ChromaDB at path: '%s'", db_path)
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)

        # Get or create the collection
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)
        logger.info("[BaseRAG] ChromaDB collection '%s' ready. Document count: %d",
                    self.collection_name, self.collection.count())

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings using the local BERT model."""
        logger.debug("[BaseRAG._get_embeddings] Encoding %d text(s) into embeddings.", len(texts))
        embeddings = self.embedding_model.encode(texts)
        return embeddings.tolist()

    def ingest(self, documents: list[str], metadatas: list[dict], ids: list[str]):
        """Ingests documents into the vector database."""
        logger.info("[BaseRAG.ingest] >>> Ingesting %d document(s) into collection '%s'.",
                    len(documents), self.collection_name)
        embeddings = self._get_embeddings(documents)

        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info("[BaseRAG.ingest] <<< Successfully ingested %d document(s) into '%s'.",
                    len(documents), self.collection_name)

    def retrieve(self, query: str, n_results: int = 3) -> list[dict]:
        """Retrieves top k documents matching the query."""
        logger.info("[BaseRAG.retrieve] >>> Retrieving top %d doc(s) for query: '%s'", n_results, query)
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

        logger.info("[BaseRAG.retrieve] <<< Returned %d result(s) for query: '%s'", len(formatted_results), query)
        return formatted_results

