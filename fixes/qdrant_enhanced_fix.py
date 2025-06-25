"""
Enhanced Qdrant connector with improved error handling and dimension validation.
This fixes the vector dimension mismatch issues that cause silent failures.
"""

import logging
import uuid
from typing import Any

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.settings import METADATA_PATH

logger = logging.getLogger(__name__)

Metadata = dict[str, Any]
ArbitraryFilter = dict[str, Any]

class CollectionInfo(BaseModel):
    """Information about a Qdrant collection."""
    name: str
    vectors_count: int = 0
    indexed_vectors_count: int = 0
    points_count: int = 0
    segments_count: int = 0
    status: str = "unknown"
    optimizer_status: str = "unknown"
    vector_size: int | None = None
    distance_metric: str | None = None

class BatchEntry(BaseModel):
    """Entry for batch operations."""
    content: str
    metadata: Metadata | None = None
    id: str | None = None

class Entry(BaseModel):
    """A single entry in the Qdrant collection."""
    content: str
    metadata: Metadata | None = None

class DimensionMismatchError(Exception):
    """Raised when vector dimensions don't match collection configuration."""
    def __init__(self, expected: int, actual: int, collection: str):
        self.expected = expected
        self.actual = actual
        self.collection = collection
        super().__init__(
            f"Vector dimension mismatch in collection '{collection}': "
            f"expected {expected}D, got {actual}D. "
            f"Use a different embedding model or recreate the collection."
        )

class EnhancedQdrantConnector:
    """
    Enhanced Qdrant connector with improved error handling and validation.
    """

    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        collection_name: str | None,
        embedding_provider: EmbeddingProvider,
        qdrant_local_path: str | None = None,
        field_indexes: dict[str, models.PayloadSchemaType] | None = None,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._default_collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )
        self._field_indexes = field_indexes

    async def validate_vector_dimensions(self, collection_name: str, vector_size: int) -> bool:
        """
        Validate that the vector size matches the collection configuration.
        
        :param collection_name: Name of the collection to validate against
        :param vector_size: Size of the vectors to validate
        :return: True if dimensions match, False otherwise
        :raises DimensionMismatchError: If dimensions don't match
        """
        try:
            collection_exists = await self._client.collection_exists(collection_name)
            if not collection_exists:
                return True  # New collection, dimensions will be set correctly
            
            info = await self._client.get_collection(collection_name)
            
            # Extract expected vector size from collection config
            expected_size = None
            if hasattr(info, 'config') and info.config and hasattr(info.config, 'params'):
                if hasattr(info.config.params, 'vectors'):
                    vectors_config = info.config.params.vectors
                    if isinstance(vectors_config, dict):
                        for vp in vectors_config.values():
                            if hasattr(vp, 'size'):
                                expected_size = vp.size
                                break
                    elif vectors_config is not None and hasattr(vectors_config, 'size'):
                        expected_size = vectors_config.size
            
            if expected_size and expected_size != vector_size:
                raise DimensionMismatchError(expected_size, vector_size, collection_name)
            
            return True
            
        except DimensionMismatchError:
            raise
        except Exception as e:
            logger.error(f"Error validating dimensions for {collection_name}: {e}")
            return False

    async def store(self, entry: Entry, *, collection_name: str | None = None):
        """
        Store information in Qdrant with improved error handling.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        try:
            await self._ensure_collection_exists(collection_name)

            # Embed the document
            embeddings = await self._embedding_provider.embed_documents([entry.content])
            vector_size = len(embeddings[0])
            
            # Validate dimensions before attempting to store
            await self.validate_vector_dimensions(collection_name, vector_size)

            # Add to Qdrant
            vector_name = self._embedding_provider.get_vector_name()
            payload = {"document": entry.content, METADATA_PATH: entry.metadata}
            
            result = await self._client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=uuid.uuid4().hex,
                        vector={vector_name: embeddings[0]},
                        payload=payload,
                    )
                ],
            )
            
            # Check if upsert was successful
            if hasattr(result, 'status') and result.status == models.UpdateStatus.COMPLETED:
                logger.info(f"Successfully stored entry in collection '{collection_name}'")
            else:
                logger.warning(f"Upsert may have failed for collection '{collection_name}': {result}")
                
        except DimensionMismatchError as e:
            logger.error(f"Dimension mismatch error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error storing entry in collection '{collection_name}': {e}")
            raise

    async def batch_store(self, entries: list[BatchEntry], collection_name: str | None = None) -> int:
        """
        Store multiple entries in batch with improved error handling.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        try:
            await self._ensure_collection_exists(collection_name)

            # Prepare all documents for embedding
            documents = [entry.content for entry in entries]
            embeddings = await self._embedding_provider.embed_documents(documents)
            
            if not embeddings:
                logger.warning("No embeddings generated")
                return 0
            
            vector_size = len(embeddings[0])
            
            # Validate dimensions before attempting to store
            await self.validate_vector_dimensions(collection_name, vector_size)

            # Prepare points for batch upload
            points = []
            vector_name = self._embedding_provider.get_vector_name()

            for i, (entry, embedding) in enumerate(zip(entries, embeddings)):
                point_id = entry.id or uuid.uuid4().hex
                payload = {"document": entry.content, METADATA_PATH: entry.metadata}

                points.append(models.PointStruct(
                    id=point_id,
                    vector={vector_name: embedding},
                    payload=payload,
                ))

            # Upload in batch
            result = await self._client.upsert(
                collection_name=collection_name,
                points=points,
            )
            
            # Check result and return actual count
            if hasattr(result, 'status') and result.status == models.UpdateStatus.COMPLETED:
                logger.info(f"Successfully stored {len(points)} entries in collection '{collection_name}'")
                return len(points)
            else:
                logger.warning(f"Batch upsert may have failed for collection '{collection_name}': {result}")
                return 0

        except DimensionMismatchError as e:
            logger.error(f"Dimension mismatch in batch store: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in batch store for collection '{collection_name}': {e}")
            raise

    async def diagnose_collection(self, collection_name: str) -> dict[str, Any]:
        """
        Diagnose a collection for common issues.
        """
        diagnosis = {
            "collection_name": collection_name,
            "exists": False,
            "vector_config": None,
            "embedding_provider": {
                "model": self._embedding_provider.get_model_name(),
                "vector_size": self._embedding_provider.get_vector_size(),
                "vector_name": self._embedding_provider.get_vector_name()
            },
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Check if collection exists
            exists = await self._client.collection_exists(collection_name)
            diagnosis["exists"] = exists
            
            if not exists:
                diagnosis["issues"].append("Collection does not exist")
                diagnosis["recommendations"].append("Create collection with appropriate vector size")
                return diagnosis
            
            # Get collection info
            info = await self._client.get_collection(collection_name)
            
            # Extract vector configuration
            if hasattr(info, 'config') and info.config and hasattr(info.config, 'params'):
                if hasattr(info.config.params, 'vectors'):
                    vectors_config = info.config.params.vectors
                    if isinstance(vectors_config, dict):
                        for vector_name, vp in vectors_config.items():
                            diagnosis["vector_config"] = {
                                "name": vector_name,
                                "size": getattr(vp, 'size', None),
                                "distance": getattr(vp, 'distance', None)
                            }
                            break
                    elif vectors_config is not None:
                        diagnosis["vector_config"] = {
                            "size": getattr(vectors_config, 'size', None),
                            "distance": getattr(vectors_config, 'distance', None)
                        }
            
            # Check for dimension mismatch
            if diagnosis["vector_config"] and diagnosis["vector_config"]["size"]:
                expected_size = diagnosis["vector_config"]["size"]
                actual_size = diagnosis["embedding_provider"]["vector_size"]
                
                if expected_size != actual_size:
                    diagnosis["issues"].append(
                        f"Vector dimension mismatch: collection expects {expected_size}D, "
                        f"embedding provider produces {actual_size}D"
                    )
                    diagnosis["recommendations"].append(
                        f"Use an embedding model that produces {expected_size}D vectors, "
                        f"or recreate the collection with {actual_size}D configuration"
                    )
            
            # Check vector names
            if diagnosis["vector_config"] and diagnosis["vector_config"].get("name"):
                expected_name = diagnosis["vector_config"]["name"]
                actual_name = diagnosis["embedding_provider"]["vector_name"]
                
                if expected_name != actual_name:
                    diagnosis["issues"].append(
                        f"Vector name mismatch: collection uses '{expected_name}', "
                        f"embedding provider uses '{actual_name}'"
                    )
                    diagnosis["recommendations"].append(
                        "Ensure embedding provider vector name matches collection configuration"
                    )
            
            return diagnosis
            
        except Exception as e:
            diagnosis["issues"].append(f"Error during diagnosis: {str(e)}")
            return diagnosis

    async def get_collection_names(self) -> list[str]:
        """Get the names of all collections in the Qdrant server."""
        response = await self._client.get_collections()
        return [collection.name for collection in response.collections]

    async def _ensure_collection_exists(self, collection_name: str):
        """Ensure that the collection exists, creating it if necessary."""
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            # Create the collection with the appropriate vector size
            vector_size = self._embedding_provider.get_vector_size()
            vector_name = self._embedding_provider.get_vector_name()
            
            logger.info(f"Creating collection '{collection_name}' with vector size {vector_size}")
            
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    vector_name: models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
            )

            # Create payload indexes if configured
            if self._field_indexes:
                for field_name, field_type in self._field_indexes.items():
                    await self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )

    # Add the rest of the methods from the original QdrantConnector class...
    # (search, get_detailed_collection_info, create_collection_with_config, etc.)
    
    async def search(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """Find points in the Qdrant collection."""
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        try:
            query_vector = await self._embedding_provider.embed_query(query)
            vector_name = self._embedding_provider.get_vector_name()

            # Validate dimensions before searching
            await self.validate_vector_dimensions(collection_name, len(query_vector))

            search_results = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                using=vector_name,
                limit=limit,
                query_filter=query_filter,
            )

            return [
                Entry(
                    content=(result.payload["document"] if result.payload and "document" in result.payload else ""),
                    metadata=(result.payload.get("metadata") if result.payload else None),
                )
                for result in search_results.points
            ]
            
        except DimensionMismatchError as e:
            logger.error(f"Dimension mismatch during search: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during search in collection '{collection_name}': {e}")
            return []
