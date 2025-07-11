import logging
from typing import List, Optional

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
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


class EnhancedEmbeddingModelManager:
    """
    Manages FastEmbed embedding models. Simplified to focus on FastEmbed only.
    """

    def __init__(self, default_settings: EmbeddingProviderSettings):
        self.default_settings = default_settings
        self._available_models: List[EmbeddingModelInfo] = []
        self._default_provider: EmbeddingProvider = create_embedding_provider(default_settings)

        self._populate_available_models()

    def _populate_available_models(self):
        """Populate the list of available FastEmbed models."""
        try:
            from fastembed import TextEmbedding
            supported_models = TextEmbedding.list_supported_models()
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

    def get_default_provider(self) -> EmbeddingProvider:
        """Returns the default FastEmbed provider."""
        return self._default_provider

    def get_model_info(self, model_name: str) -> Optional[EmbeddingModelInfo]:
        """Get information about a specific model."""
        for model in self._available_models:
            if model.model_name == model_name:
                return model
        return None

    def list_available_models(self) -> List[EmbeddingModelInfo]:
        """List all available embedding models."""
        return self._available_models.copy()

    def find_model_by_vector_size(self, vector_size: int) -> Optional[str]:
        """Find a suitable model based on vector size."""
        for model in self._available_models:
            if model.vector_size == vector_size:
                return model.model_name
        return None