"""
Enhanced embedding model manager that persists collection-model associations.
"""

import logging
from typing import Dict, List, Optional
import json

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.embeddings.types import EmbeddingProviderType
from mcp_server_qdrant.settings import EmbeddingProviderSettings

logger = logging.getLogger(__name__)

# Metadata key for storing embedding model info in collections
EMBEDDING_MODEL_META_KEY = "_mcp_embedding_model"


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
    Enhanced manager that persists embedding model associations in Qdrant collection metadata.
    """
    
    def __init__(self, default_settings: EmbeddingProviderSettings, qdrant_connector=None):
        self.default_settings = default_settings
        self._providers: Dict[str, EmbeddingProvider] = {}
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
        # FastEmbed models with their actual dimensions
        fastembed_models = [
            ("sentence-transformers/all-MiniLM-L6-v2", 384, "Lightweight, fast model good for general use"),
            ("sentence-transformers/all-mpnet-base-v2", 768, "High quality, balanced performance"),
            ("BAAI/bge-small-en-v1.5", 384, "Compact model optimized for English"),
            ("BAAI/bge-base-en-v1.5", 768, "Better quality English embeddings"),
            ("BAAI/bge-large-en-v1.5", 1024, "Highest quality English embeddings"),
            ("sentence-transformers/all-MiniLM-L12-v2", 384, "Slightly larger than L6, better quality"),
            ("thenlper/gte-small", 384, "General text embeddings, small variant"),
            ("thenlper/gte-base", 768, "General text embeddings, base variant"),
            ("thenlper/gte-large", 1024, "General text embeddings, large variant"),
            ("intfloat/e5-small-v2", 384, "E5 family, small and efficient"),
            ("intfloat/e5-base-v2", 768, "E5 family, balanced performance"),
            ("intfloat/e5-large-v2", 1024, "E5 family, highest quality"),
        ]
        
        for model_name, vector_size, description in fastembed_models:
            self._available_models.append(
                EmbeddingModelInfo(
                    model_name=model_name,
                    provider_type="fastembed",
                    vector_size=vector_size,
                    description=description
                )
            )
    
    async def get_provider_for_collection(self, collection_name: str) -> EmbeddingProvider:
        """Get the embedding provider for a specific collection."""
        # Try to get model from collection metadata
        model_name = await self._get_collection_model_from_metadata(collection_name)
        
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
    
    async def set_collection_model(self, collection_name: str, model_name: str) -> bool:
        """Set the embedding model for a specific collection and persist it."""
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
            
            # Store in collection metadata
            success = await self._store_collection_model_metadata(collection_name, model_name, model_info.vector_size)
            
            if success:
                logger.info(f"Successfully set model {model_name} for collection {collection_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting model {model_name} for collection {collection_name}: {e}")
            return False
    
    async def _get_collection_model_from_metadata(self, collection_name: str) -> Optional[str]:
        """Retrieve the embedding model for a collection from its metadata."""
        if not self.qdrant_connector or not hasattr(self.qdrant_connector, '_client'):
            return None
        
        try:
            # Check if collection exists
            exists = await self.qdrant_connector._client.collection_exists(collection_name)
            if not exists:
                return None
            
            # Get collection info
            info = await self.qdrant_connector._client.get_collection(collection_name)
            
            # Check for embedding model in metadata
            if hasattr(info, 'config') and hasattr(info.config, 'params') and hasattr(info.config.params, 'metadata'):
                metadata = info.config.params.metadata
                if metadata and EMBEDDING_MODEL_META_KEY in metadata:
                    model_data = metadata[EMBEDDING_MODEL_META_KEY]
                    if isinstance(model_data, str):
                        # Handle legacy string format
                        return model_data
                    elif isinstance(model_data, dict):
                        return model_data.get('model_name')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting model from collection metadata: {e}")
            return None
    
    async def _store_collection_model_metadata(self, collection_name: str, model_name: str, vector_size: int) -> bool:
        """Store the embedding model info in collection metadata."""
        if not self.qdrant_connector or not hasattr(self.qdrant_connector, '_client'):
            logger.error("Qdrant connector not available")
            return False
        
        try:
            # Update collection with metadata
            await self.qdrant_connector._client.update_collection(
                collection_name=collection_name,
                metadata={
                    EMBEDDING_MODEL_META_KEY: {
                        "model_name": model_name,
                        "vector_size": vector_size,
                        "provider": "fastembed"
                    }
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Error storing model metadata: {e}")
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
        return await self._get_collection_model_from_metadata(collection_name)
    
    async def remove_collection_model(self, collection_name: str):
        """Remove the model association for a collection."""
        # Since we store in metadata, this happens automatically when collection is deleted
        pass
    
    def find_model_by_vector_size(self, vector_size: int) -> Optional[str]:
        """Find a suitable model based on vector size."""
        for model in self._available_models:
            if model.vector_size == vector_size:
                return model.model_name
        return None
