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
    """
    A single entry in the Qdrant collection.
    """

    content: str
    metadata: Metadata | None = None


class QdrantConnector:
    """
    Encapsulates the connection to a Qdrant server and all the methods to interact with it.
    :param qdrant_url: The URL of the Qdrant server.
    :param qdrant_api_key: The API key to use for the Qdrant server.
    :param collection_name: The name of the default collection to use. If not provided, each tool will require
                            the collection name to be provided.
    :param embedding_provider: The embedding provider to use.
    :param qdrant_local_path: The path to the storage directory for the Qdrant client, if local mode is used.
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

    async def get_collection_names(self) -> list[str]:
        """
        Get the names of all collections in the Qdrant server.
        :return: A list of collection names.
        """
        response = await self._client.get_collections()
        return [collection.name for collection in response.collections]

    async def store(self, entry: Entry, *, collection_name: str | None = None):
        """
        Store some information in the Qdrant collection, along with the specified metadata.
        :param entry: The entry to store in the Qdrant collection.
        :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                the default collection is used.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        await self._ensure_collection_exists(collection_name)

        # Embed the document
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.
        embeddings = await self._embedding_provider.embed_documents([entry.content])

        # Get collection info to determine the correct vector name
        collection_info = await self._client.get_collection(collection_name)

        # Find the first vector configuration name (there should be only one for our collections)
        vector_name = None
        if hasattr(collection_info, 'config') and collection_info.config and hasattr(collection_info.config, 'params'):
            if hasattr(collection_info.config.params, 'vectors'):
                vectors_config = collection_info.config.params.vectors
                if isinstance(vectors_config, dict) and vectors_config:
                    vector_name = list(vectors_config.keys())[0]  # Get the first vector name

        # Fallback to provider's vector name if we can't determine from collection
        if not vector_name:
            vector_name = self._embedding_provider.get_vector_name()

        # Add to Qdrant
        payload = {"document": entry.content, METADATA_PATH: entry.metadata}
        await self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=uuid.uuid4().hex,
                    vector={vector_name: embeddings[0]},
                    payload=payload,
                )
            ],
        )

    async def search(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.
        :param query: The query to use for the search.
        :param collection_name: The name of the collection to search in, optional. If not provided,
                                the default collection is used.
        :param limit: The maximum number of entries to return.
        :param query_filter: The filter to apply to the query, if any.

        :return: A list of entries found.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Embed the query
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.

        query_vector = await self._embedding_provider.embed_query(query)

        # Get collection info to determine the correct vector name
        collection_info = await self._client.get_collection(collection_name)

        # Find the first vector configuration name (there should be only one for our collections)
        vector_name = None
        if hasattr(collection_info, 'config') and collection_info.config and hasattr(collection_info.config, 'params'):
            if hasattr(collection_info.config.params, 'vectors'):
                vectors_config = collection_info.config.params.vectors
                if isinstance(vectors_config, dict) and vectors_config:
                    vector_name = list(vectors_config.keys())[0]  # Get the first vector name

        # Fallback to provider's vector name if we can't determine from collection
        if not vector_name:
            vector_name = self._embedding_provider.get_vector_name()

        # Search in Qdrant
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

    async def _ensure_collection_exists(self, collection_name: str):
        """
        Ensure that the collection exists, creating it if necessary.
        Uses the CURRENT embedding provider to ensure vector name consistency.
        :param collection_name: The name of the collection to ensure exists.
        """
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            # CRITICAL: Use the CURRENT embedding provider (which may have been swapped)
            # This ensures the collection is created with the same vector name that will be used for storage
            vector_size = self._embedding_provider.get_vector_size()
            vector_name = self._embedding_provider.get_vector_name()
            
            logger.info(f"Creating collection '{collection_name}' with vector name '{vector_name}' and size {vector_size}")
            
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

    async def get_detailed_collection_info(self, collection_name: str) -> CollectionInfo | None:
        """
        Get detailed information about a collection.
        :param collection_name: The name of the collection.
        :return: CollectionInfo object with detailed information, or None if collection doesn't exist.
        """
        try:
            collection_exists = await self._client.collection_exists(collection_name)
            if not collection_exists:
                return None

            info = await self._client.get_collection(collection_name)

            # Extract vector configuration
            vector_size = None
            distance_metric = None
            if hasattr(info, 'config') and info.config and hasattr(info.config, 'params'):
                if hasattr(info.config.params, 'vectors'):
                    vectors_config = info.config.params.vectors
                    # vectors_config is usually a dict of vector_name -> VectorParams
                    if isinstance(vectors_config, dict):
                        # Take the first vector config if available
                        for vp in vectors_config.values():
                            if hasattr(vp, 'size'):
                                vector_size = vp.size
                            if hasattr(vp, 'distance'):
                                distance_metric = vp.distance.name if hasattr(vp.distance, 'name') else str(vp.distance)
                            break  # Only use the first vector config
                    # If it's a single VectorParams (older qdrant), handle that as well
                    elif vectors_config is not None and hasattr(vectors_config, 'size'):
                        vector_size = vectors_config.size
                        if hasattr(vectors_config, 'distance'):
                            distance_metric = vectors_config.distance.name if hasattr(vectors_config.distance, 'name') else str(vectors_config.distance)

            # For small collections, Qdrant doesn't report vectors_count but points_count indicates stored vectors
            points_count = getattr(info, 'points_count', 0) or 0
            indexed_vectors_count = getattr(info, 'indexed_vectors_count', 0) or 0

            # If indexed_vectors_count is 0 but we have points, assume vectors are stored but not indexed
            # This happens for collections below the indexing threshold
            vectors_count = getattr(info, 'vectors_count', None)
            if vectors_count is None:
                vectors_count = points_count  # Assume each point has a vector for collections below indexing threshold

            return CollectionInfo(
                name=collection_name,
                vectors_count=vectors_count,
                indexed_vectors_count=indexed_vectors_count,
                points_count=points_count,
                segments_count=getattr(info, 'segments_count', 0) or 0,
                status=getattr(info, 'status', 'unknown') or 'unknown',
                optimizer_status=getattr(info, 'optimizer_status', 'unknown') or 'unknown',
                vector_size=vector_size,
                distance_metric=distance_metric
            )
        except Exception as e:
            logger.error(f"Error getting collection info for {collection_name}: {e}")
            return None

    async def create_collection_with_config(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "cosine",
        embedding_provider: EmbeddingProvider | None = None
    ) -> bool:
        """
        Create a new collection with specified configuration.
        :param collection_name: Name of the collection to create.
        :param vector_size: Size of the vectors.
        :param distance: Distance metric (cosine, dot, euclidean).
        :param embedding_provider: Optional embedding provider for this collection.
        :return: True if successful, False otherwise.
        """
        try:
            # Convert distance string to Qdrant Distance enum
            distance_map = {
                "cosine": models.Distance.COSINE,
                "dot": models.Distance.DOT,
                "euclidean": models.Distance.EUCLID,
                "manhattan": models.Distance.MANHATTAN
            }

            distance_metric = distance_map.get(distance.lower(), models.Distance.COSINE)

            # Use embedding provider vector name if provided, otherwise use the default embedding provider's name
            vector_name = embedding_provider.get_vector_name() if embedding_provider else self._embedding_provider.get_vector_name()

            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    vector_name: models.VectorParams(
                        size=vector_size,
                        distance=distance_metric,
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

            return True
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")
            return False

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.
        :param collection_name: Name of the collection to delete.
        :return: True if successful, False otherwise.
        """
        try:
            await self._client.delete_collection(collection_name)
            return True
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False

    async def batch_store(self, entries: list[BatchEntry], collection_name: str | None = None) -> int:
        """
        Store multiple entries in batch with improved vector name handling.
        :param entries: List of entries to store.
        :param collection_name: Name of the collection to store in.
        :return: Number of entries successfully stored.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        # Ensure collection exists with the CURRENT embedding provider
        await self._ensure_collection_exists(collection_name)

        try:
            # Prepare all documents for embedding
            documents = [entry.content for entry in entries]
            embeddings = await self._embedding_provider.embed_documents(documents)

            # Get the vector name from the CURRENT embedding provider (not from collection config)
            # This should match the collection because _ensure_collection_exists uses the same provider
            vector_name = self._embedding_provider.get_vector_name()
            
            logger.info(f"Storing {len(entries)} entries in collection '{collection_name}' with vector name '{vector_name}'")

            # Prepare points for batch upload
            points = []

            for i, (entry, embedding) in enumerate(zip(entries, embeddings)):
                # Ensure point_id is a valid UUID
                if entry.id:
                    try:
                        # Try to parse as UUID and convert to hex
                        point_id = str(uuid.UUID(entry.id)).replace('-', '')
                    except ValueError:
                        # If not a valid UUID, generate a new one based on the entry ID
                        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, entry.id).hex
                else:
                    point_id = uuid.uuid4().hex
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
            
            # Verify the upsert actually worked by checking the result
            if hasattr(result, 'status') and hasattr(result.status, 'error') and result.status.error:
                logger.error(f"Qdrant upsert error: {result.status.error}")
                return 0
                
            # Double-check by getting collection info
            info = await self.get_detailed_collection_info(collection_name)
            if info and info.points_count > 0:
                logger.info(f"Successfully stored {len(points)} entries. Collection now has {info.points_count} total points.")
                return len(points)
            else:
                logger.error(f"Upsert appeared successful but collection has 0 points - likely vector name mismatch")
                return 0

        except Exception as e:
            logger.error(f"Error in batch store: {e}")
            return 0

    async def scroll_collection(
        self,
        collection_name: str | None = None,
        limit: int = 100,
        offset: str | None = None,
        query_filter: models.Filter | None = None,
        with_payload: bool = True,
        with_vectors: bool = False
    ) -> tuple[list[Entry], str | None]:
        """
        Scroll through collection contents with pagination.
        :param collection_name: Name of the collection to scroll.
        :param limit: Maximum number of entries to return.
        :param offset: Pagination offset (point ID to start from).
        :param query_filter: Optional filter to apply.
        :param with_payload: Include payload in results.
        :param with_vectors: Include vectors in results.
        :return: Tuple of (entries, next_offset).
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None

        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return [], None

        try:
            result = await self._client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                scroll_filter=query_filter,
                with_payload=with_payload,
                with_vectors=with_vectors
            )

            entries = []
            for point in result[0]:  # result is tuple (points, next_offset)
                if with_payload and point.payload:
                    content = point.payload.get("document", "")
                    metadata = point.payload.get(METADATA_PATH)
                    entries.append(Entry(content=content, metadata=metadata))
                else:
                    # If no payload, create entry with point ID as content
                    entries.append(Entry(content=f"Point ID: {point.id}", metadata={"point_id": point.id}))

            next_offset = str(result[1]) if result[1] is not None else None
            return entries, next_offset  # entries, next_offset
        except Exception as e:
            logger.error(f"Error scrolling collection {collection_name}: {e}")
            return [], None

    async def hybrid_search(
        self,
        query: str,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
        min_score: float | None = None,
        search_params: dict | None = None
    ) -> list[tuple[Entry, float]]:
        """
        Perform hybrid search with scoring.
        :param query: The search query.
        :param collection_name: Name of the collection to search.
        :param limit: Maximum number of results.
        :param query_filter: Optional filter to apply.
        :param min_score: Minimum similarity score threshold.
        :param search_params: Additional search parameters.
        :return: List of (entry, score) tuples.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        try:
            query_vector = await self._embedding_provider.embed_query(query)
            vector_name = self._embedding_provider.get_vector_name()

            # Prepare search parameters
            params = search_params or {}

            search_results = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                using=vector_name,
                limit=limit,
                query_filter=query_filter,
                score_threshold=min_score,
                **params
            )

            results = []
            for result in search_results.points:
                entry = Entry(
                    content=(result.payload["document"] if result.payload and "document" in result.payload else ""),
                    metadata=(result.payload.get(METADATA_PATH) if result.payload else None),
                )
                score = result.score if hasattr(result, 'score') else 0.0
                results.append((entry, score))

            return results
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
