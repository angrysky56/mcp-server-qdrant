"""
Enhanced embedding model manager that persists collection-model associations.
Uses a dedicated collection to store model mappings.
"""

import logging
from typing import Dict, List, Optional

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.embeddings.types import EmbeddingProviderType
from mcp_server_qdrant.settings import EmbeddingProviderSettings
from qdrant_client import models

logger = logging.getLogger(__name__)

# Special collection for storing embedding model mappings
MODEL_MAPPING_COLLECTION = "_mcp_embedding_models"


class EmbeddingModelInfo:
    """Information about an available embedding model."""

    def __init__(self, model_name: str, provider_type: str, vector_size: int, description: str = ""):
        self.model_name = model_name
        self.provider_type = provider_type
        self.vector_size = vector_size
        self.description = description

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "provider_type": self.provider_type,
            "vector_size": self.vector_size,
            "description": self.description
        }


class EnhancedEmbeddingModelManager:
    """
    Enhanced manager that persists embedding model associations.
    Uses a dedicated collection to store collection-model mappings.
    """

    def __init__(self, default_settings: EmbeddingProviderSettings, qdrant_connector=None):
        self.default_settings = default_settings
        self._providers: Dict[str, EmbeddingProvider] = {}
        self._model_cache: Dict[str, str] = {}  # Local cache of collection -> model mappings
        self._available_models: List[EmbeddingModelInfo] = []
        self.qdrant_connector = qdrant_connector

        # Initialize with default provider
        self._default_provider = create_embedding_provider(default_settings)
        default_key = f"{default_settings.provider_type.value}:{default_settings.model_name}"
        self._providers[default_key] = self._default_provider

        # Populate available models list
        self._populate_available_models()

    def set_qdrant_connector(self, connector):
        """Set the Qdrant connector after initialization."""
        self.qdrant_connector = connector

    def _populate_available_models(self):
        """Populate the list of available embedding models."""
        try:
            from fastembed import TextEmbedding
            supported_models = TextEmbedding.list_supported_models()
            # supported_models is a list of dicts with keys: 'model', 'dim', 'description'
            for model in supported_models:
                self._available_models.append(
                    EmbeddingModelInfo(
                        model_name=model['model'],
                        provider_type="fastembed",
                        vector_size=model.get('dim', 0),
                        description=model.get('description', '')
                    )
                )
        except Exception as e:
            logger.error(f"Failed to populate available models: {e}")

    async def _ensure_mapping_collection_exists(self):
        """Ensure the model mapping collection exists."""
        if not self.qdrant_connector or not hasattr(self.qdrant_connector, '_client'):
            return

        try:
            exists = await self.qdrant_connector._client.collection_exists(MODEL_MAPPING_COLLECTION)
            if not exists:
                # Create a simple collection for storing mappings
                await self.qdrant_connector._client.create_collection(
                    collection_name=MODEL_MAPPING_COLLECTION,
                    vectors_config=models.VectorParams(
                        size=4,  # Tiny vectors, we only care about payload
                        distance=models.Distance.DOT,
                    ),
                )
                logger.info(f"Created model mapping collection: {MODEL_MAPPING_COLLECTION}")
        except Exception as e:
            logger.error(f"Error ensuring mapping collection: {e}")

    async def get_provider_for_collection(self, collection_name: str) -> EmbeddingProvider:
        """Get the embedding provider for a specific collection."""
        # Check cache first
        if collection_name in self._model_cache:
            model_name = self._model_cache[collection_name]
        else:
            # Try to get model from storage
            model_name = await self._get_collection_model_from_storage(collection_name)
            if model_name:
                self._model_cache[collection_name] = model_name

        if model_name:
            provider_key = f"fastembed:{model_name}"

            # Create provider if not cached
            if provider_key not in self._providers:
                try:
                    # Create new settings with the specific model
                    settings = EmbeddingProviderSettings(
                        provider_type=EmbeddingProviderType.FASTEMBED,
                        model_name=model_name
                    )
                    self._providers[provider_key] = create_embedding_provider(settings)
                    logger.info(f"Created embedding provider for model {model_name}")
                except Exception as e:
                    logger.error(f"Failed to create provider for model {model_name}: {e}")
                    return self._default_provider

            return self._providers[provider_key]

        # Return default provider
        return self._default_provider

    async def set_collection_model(self, collection_name: str, model_name: str, distance: str = "cosine") -> bool:
        """Set the embedding model and distance metric for a specific collection and persist it."""
        try:
            # Validate model exists
            model_info = self.get_model_info(model_name)
            if not model_info:
                logger.error(f"Model {model_name} not found in available models")
                return False

            # Create provider if not already cached
            provider_key = f"fastembed:{model_name}"
            if provider_key not in self._providers:
                settings = EmbeddingProviderSettings(
                    provider_type=EmbeddingProviderType.FASTEMBED,
                    model_name=model_name
                )
                self._providers[provider_key] = create_embedding_provider(settings)

            # Store in persistent storage with distance metric
            success = await self._store_collection_model_mapping(collection_name, model_name, model_info.vector_size, distance)

            if success:
                # Update cache
                self._model_cache[collection_name] = model_name
                logger.info(f"Successfully set model {model_name} with {distance} distance for collection {collection_name}")

            return success

        except Exception as e:
            logger.error(f"Error setting model {model_name} for collection {collection_name}: {e}")
            return False

    async def _get_collection_model_from_storage(self, collection_name: str) -> Optional[str]:
        """Retrieve the embedding model for a collection from storage."""
        if not self.qdrant_connector or not hasattr(self.qdrant_connector, '_client'):
            return None

        try:
            # Ensure mapping collection exists
            await self._ensure_mapping_collection_exists()

            # Search for the collection mapping
            results = await self.qdrant_connector._client.scroll(
                collection_name=MODEL_MAPPING_COLLECTION,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="collection_name",
                            match=models.MatchValue(value=collection_name)
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False
            )

            if results[0]:  # results is a tuple (points, next_offset)
                point = results[0][0]
                if point.payload:
                    return point.payload.get("model_name")

            return None

        except Exception as e:
            logger.error(f"Error getting model from storage: {e}")
            return None

    async def _store_collection_model_mapping(self, collection_name: str, model_name: str, vector_size: int, distance: str = "cosine") -> bool:
        """Store the embedding model mapping."""
        if not self.qdrant_connector or not hasattr(self.qdrant_connector, '_client'):
            logger.error("Qdrant connector not available")
            return False

        try:
            # Ensure mapping collection exists
            await self._ensure_mapping_collection_exists()

            # Create or update the mapping
            import uuid
            point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"mapping_{collection_name}"))
            await self.qdrant_connector._client.upsert(
                collection_name=MODEL_MAPPING_COLLECTION,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=[0.0, 0.0, 0.0, 0.0],  # Dummy vector
                        payload={
                            "collection_name": collection_name,
                            "model_name": model_name,
                            "vector_size": vector_size,
                            "distance": distance,
                            "provider": "fastembed"
                        }
                    )
                ]
            )
            return True

        except Exception as e:
            logger.error(f"Error storing model mapping: {e}")
            return False

    def get_model_info(self, model_name: str) -> Optional[EmbeddingModelInfo]:
        """Get information about a specific model."""
        for model in self._available_models:
            if model.model_name == model_name:
                return model
        return None

    def list_available_models(self) -> List[EmbeddingModelInfo]:
        """List all available embedding models."""
        return self._available_models.copy()

    async def get_collection_model(self, collection_name: str) -> Optional[str]:
        """Get the model name for a specific collection."""
        # Check cache first
        if collection_name in self._model_cache:
            return self._model_cache[collection_name]

        # Otherwise get from storage
        return await self._get_collection_model_from_storage(collection_name)

    async def remove_collection_model(self, collection_name: str):
        """Remove the model association for a collection."""
        # Remove from cache
        if collection_name in self._model_cache:
            del self._model_cache[collection_name]

        # Remove from storage
        if self.qdrant_connector and hasattr(self.qdrant_connector, '_client'):
            try:
                import uuid
                point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, f"mapping_{collection_name}"))
                await self.qdrant_connector._client.delete(
                    collection_name=MODEL_MAPPING_COLLECTION,
                    points_selector=models.PointIdsList(
                        points=[point_id]
                    )
                )
            except Exception as e:
                logger.error(f"Error removing model mapping: {e}")

    def find_model_by_vector_size(self, vector_size: int) -> Optional[str]:
        """Find a suitable model based on vector size."""
        for model in self._available_models:
            if model.vector_size == vector_size:
                return model.model_name
        return None

    async def get_collection_distance(self, collection_name: str) -> str:
        """Get the distance metric for a specific collection."""
        if not self.qdrant_connector or not hasattr(self.qdrant_connector, '_client'):
            return "cosine"  # Default fallback

        try:
            # Ensure mapping collection exists
            await self._ensure_mapping_collection_exists()

            # Search for the collection mapping
            results = await self.qdrant_connector._client.scroll(
                collection_name=MODEL_MAPPING_COLLECTION,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="collection_name",
                            match=models.MatchValue(value=collection_name)
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False
            )

            if results[0]:  # results is a tuple (points, next_offset)
                point = results[0][0]
                if point.payload:
                    return point.payload.get("distance", "cosine")

            return "cosine"  # Default fallback

        except Exception as e:
            logger.error(f"Error getting distance from storage: {e}")
            return "cosine"  # Default fallback
