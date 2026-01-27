"""
Search functionality for the Regulatory Knowledge Base.

Combines full-text search with semantic vector search for natural language queries.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .config import config
from .database import db

logger = logging.getLogger(__name__)


class SearchEngine:
    """Search engine combining FTS and vector search for documents."""

    def __init__(self) -> None:
        """Initialize the search engine."""
        self._model: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of models and vector database."""
        if self._initialized:
            return

        try:
            # Initialize sentence transformer model
            model_name = config.get("search.embedding_model", "all-MiniLM-L6-v2")
            logger.info(f"Loading embedding model: {model_name}")
            self._model = SentenceTransformer(model_name)

            # Initialize ChromaDB
            chroma_path = config.base_dir / "db" / "chroma"
            chroma_path.mkdir(parents=True, exist_ok=True)

            self._chroma_client = chromadb.PersistentClient(
                path=str(chroma_path), settings=Settings(anonymized_telemetry=False)
            )

            self._collection = self._chroma_client.get_or_create_collection(
                name="documents", metadata={"hnsw:space": "cosine"}
            )

            self._initialized = True
            logger.info("Search engine initialized")

        except Exception as e:
            logger.error(f"Failed to initialize search engine: {e}")
            raise

    def index_document(self, doc_id: int, text: str, metadata: dict[str, Any]) -> bool:
        """
        Index a document for vector search.

        Args:
            doc_id: Document ID.
            text: Text content to index.
            metadata: Document metadata.

        Returns:
            True if successful, False otherwise.
        """
        self._ensure_initialized()

        try:
            # Generate embedding
            embedding = self._model.encode(text[:10000])  # Limit text length

            # Prepare metadata (ChromaDB only accepts str, int, float, bool)
            clean_metadata = {
                k: str(v) if v is not None else ""
                for k, v in metadata.items()
                if k in ["title", "document_type", "jurisdiction", "version"]
            }

            # Add to ChromaDB
            self._collection.upsert(
                ids=[str(doc_id)],
                embeddings=[embedding.tolist()],
                metadatas=[clean_metadata],
                documents=[text[:1000]],  # Store snippet for context
            )

            logger.debug(f"Indexed document {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index document {doc_id}: {e}")
            return False

    def search(
        self,
        query: str,
        limit: int = 10,
        document_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        latest_only: bool = True,
        include_excerpt: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search for documents using natural language query.

        Combines vector search with full-text search for best results.

        Args:
            query: Natural language search query.
            limit: Maximum number of results.
            document_type: Filter by document type.
            jurisdiction: Filter by jurisdiction.
            latest_only: Only return latest versions.
            include_excerpt: Include matching excerpts in results.

        Returns:
            List of search results with relevance scores.
        """
        self._ensure_initialized()

        results = []

        # Vector search
        try:
            vector_results = self._vector_search(query, limit * 2, document_type, jurisdiction)
            results.extend(vector_results)
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")

        # Full-text search
        try:
            fts_results = db.search_fts(query, limit * 2, latest_only)
            for doc in fts_results:
                # Avoid duplicates
                if not any(r["id"] == doc["id"] for r in results):
                    doc["search_type"] = "fts"
                    doc["relevance_score"] = abs(doc.get("relevance", 0))
                    results.append(doc)
        except Exception as e:
            logger.warning(f"FTS search failed: {e}")

        # Filter results
        if document_type:
            results = [r for r in results if r.get("document_type") == document_type]
        if jurisdiction:
            results = [r for r in results if r.get("jurisdiction") == jurisdiction]
        if latest_only:
            results = [r for r in results if r.get("is_latest", True)]

        # Sort by relevance and limit
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        results = results[:limit]

        # Add excerpts if requested
        if include_excerpt:
            for result in results:
                result["excerpt"] = self._get_excerpt(result.get("id"), query)

        return results

    def _vector_search(
        self,
        query: str,
        limit: int,
        document_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Perform vector similarity search.

        Args:
            query: Search query.
            limit: Maximum results.
            document_type: Filter by type.
            jurisdiction: Filter by jurisdiction.

        Returns:
            List of matching documents.
        """
        # Generate query embedding
        query_embedding = self._model.encode(query)

        # Build filter
        where_filter = {}
        if document_type:
            where_filter["document_type"] = document_type
        if jurisdiction:
            where_filter["jurisdiction"] = jurisdiction

        # Query ChromaDB
        chroma_results = self._collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=limit,
            where=where_filter if where_filter else None,
        )

        results = []
        if chroma_results and chroma_results["ids"]:
            for i, doc_id in enumerate(chroma_results["ids"][0]):
                # Get full document from SQLite
                doc = db.get_document(doc_id=int(doc_id))
                if doc:
                    doc["search_type"] = "vector"
                    # Convert distance to similarity score (ChromaDB uses L2 by default)
                    distance = (
                        chroma_results["distances"][0][i] if chroma_results["distances"] else 0
                    )
                    doc["relevance_score"] = 1.0 / (1.0 + distance)
                    results.append(doc)

        return results

    def _get_excerpt(self, doc_id: Optional[int], query: str, context_chars: int = 200) -> str:
        """
        Get a relevant excerpt from the document.

        Args:
            doc_id: Document ID.
            query: Search query for context.
            context_chars: Characters of context around match.

        Returns:
            Excerpt string.
        """
        if not doc_id:
            return ""

        # Try to get extracted text
        extracted_path = config.extracted_dir / f"{doc_id}.md"
        if not extracted_path.exists():
            return ""

        try:
            with open(extracted_path, encoding="utf-8") as f:
                text = f.read()

            # Find query terms in text
            query_terms = query.lower().split()
            text_lower = text.lower()

            best_pos = 0
            best_score = 0

            for i in range(0, len(text_lower) - 100, 50):
                chunk = text_lower[i : i + 200]
                score = sum(1 for term in query_terms if term in chunk)
                if score > best_score:
                    best_score = score
                    best_pos = i

            # Extract excerpt around best position
            start = max(0, best_pos - 50)
            end = min(len(text), best_pos + context_chars)
            excerpt = text[start:end].strip()

            # Clean up and add ellipsis
            if start > 0:
                excerpt = "..." + excerpt
            if end < len(text):
                excerpt = excerpt + "..."

            return excerpt

        except Exception as e:
            logger.debug(f"Failed to get excerpt for doc {doc_id}: {e}")
            return ""

    def reindex_all(self, progress_callback: Optional[callable] = None) -> int:
        """
        Reindex all documents in the database.

        Args:
            progress_callback: Optional callback for progress updates.

        Returns:
            Number of documents indexed.
        """
        self._ensure_initialized()

        documents = db.list_documents(latest_only=False, limit=10000)
        indexed = 0

        for doc in documents:
            try:
                # Get extracted text
                extracted_path = Path(doc.get("extracted_path", ""))
                if extracted_path.exists():
                    with open(extracted_path, encoding="utf-8") as f:
                        text = f.read()
                else:
                    text = doc.get("title", "") + " " + doc.get("description", "")

                if self.index_document(doc["id"], text, doc):
                    indexed += 1

                if progress_callback:
                    progress_callback(indexed, len(documents))

            except Exception as e:
                logger.error(f"Failed to reindex document {doc['id']}: {e}")

        return indexed


# Global search engine instance
search_engine = SearchEngine()
