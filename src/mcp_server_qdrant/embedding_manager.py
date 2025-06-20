"""
Embedding model manager for handling multiple embedding providers and models.
"""

import logging
from typing import Dict, List

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.embeddings.types import EmbeddingProviderType
from mcp_server_qdrant.settings import EmbeddingProviderSettings

logger = logging.getLogger(__name__)


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


class EmbeddingModelManager:
    """
    Manages multiple embedding models and providers.
    Allows dynamic switching between models for different collections.
    """
    
    def __init__(self, default_settings: EmbeddingProviderSettings):
        self.default_settings = default_settings
        self._providers: Dict[str, EmbeddingProvider] = {}
        self._collection_models: Dict[str, str] = {}  # collection_name -> model_name
        self._available_models: List[EmbeddingModelInfo] = []
        
        # Initialize with default provider
        default_key = f"{default_settings.provider_type.value}:{default_settings.model_name}"
        self._providers[default_key] = create_embedding_provider(default_settings)
        
        # Populate available models list
        self._populate_available_models()
    
    def _populate_available_models(self):
        """Populate the list of available embedding models."""
        # FastEmbed models - these are commonly available
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
    
    def get_provider_for_collection(self, collection_name: str) -> EmbeddingProvider:
        """Get the embedding provider for a specific collection."""
        model_name = self._collection_models.get(collection_name)
        if model_name:
            provider_key = f"fastembed:{model_name}"
            if provider_key in self._providers:
                return self._providers[provider_key]
        
        # Return default provider
        default_key = f"{self.default_settings.provider_type.value}:{self.default_settings.model_name}"
        return self._providers[default_key]
    
    def set_collection_model(self, collection_name: str, model_name: str) -> bool:
        """Set the embedding model for a specific collection."""
        try:
            # Check if model is available
            if not any(model.model_name == model_name for model in self._available_models):
                logger.error(f"Model {model_name} not found in available models")
                return False
            
            # Create provider if not already cached
            provider_key = f"fastembed:{model_name}"
            if provider_key not in self._providers:
                # Create settings using environment variable approach
                import os
                original_model = os.environ.get("EMBEDDING_MODEL")
                try:
                    # Temporarily set the model name
                    os.environ["EMBEDDING_MODEL"] = model_name
                    settings = EmbeddingProviderSettings()
                    self._providers[provider_key] = create_embedding_provider(settings)
                finally:
                    # Restore original model
                    if original_model:
                        os.environ["EMBEDDING_MODEL"] = original_model
                    else:
                        os.environ.pop("EMBEDDING_MODEL", None)
            
            # Associate collection with model
            self._collection_models[collection_name] = model_name
            return True
            
        except Exception as e:
            logger.error(f"Error setting model {model_name} for collection {collection_name}: {e}")
            return False
    
    def get_collection_model(self, collection_name: str) -> str | None:
        """Get the model name for a specific collection."""
        return self._collection_models.get(collection_name)
    
    def list_available_models(self) -> List[EmbeddingModelInfo]:
        """List all available embedding models."""
        return self._available_models.copy()
    
    def get_model_info(self, model_name: str) -> EmbeddingModelInfo | None:
        """Get information about a specific model."""
        for model in self._available_models:
            if model.model_name == model_name:
                return model
        return None
    
    def remove_collection_model(self, collection_name: str):
        """Remove the model association for a collection."""
        if collection_name in self._collection_models:
            del self._collection_models[collection_name]
    
    def get_collections_using_model(self, model_name: str) -> List[str]:
        """Get list of collections using a specific model."""
        return [
            collection_name for collection_name, assigned_model 
            in self._collection_models.items() 
            if assigned_model == model_name
        ]
