from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Embed a list of documents into vectors."""
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Embed a query into a vector."""
        pass

    @abstractmethod
    def get_vector_name(self) -> str:
        """Get the name of the vector for the Qdrant collection."""
        pass

    @abstractmethod
    def get_vector_size(self) -> int:
        """Get the size of the vector for the Qdrant collection."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the name of the embedding model."""
        pass
