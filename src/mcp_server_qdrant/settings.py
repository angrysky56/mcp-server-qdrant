"""
Enhanced configuration settings with removed limits and better defaults.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings

from mcp_server_qdrant.embeddings.types import EmbeddingProviderType

# Import enhanced descriptions
from mcp_server_qdrant.enhanced_tool_descriptions import (
    DEFAULT_TOOL_STORE_DESCRIPTION,
    DEFAULT_TOOL_FIND_DESCRIPTION,
    DEFAULT_TOOL_BATCH_STORE_DESCRIPTION,
    DEFAULT_TOOL_SCROLL_DESCRIPTION,
    DEFAULT_TOOL_LIST_COLLECTIONS_DESCRIPTION,
    DEFAULT_TOOL_CREATE_COLLECTION_DESCRIPTION,
    DEFAULT_TOOL_GET_COLLECTION_INFO_DESCRIPTION,
    DEFAULT_TOOL_DELETE_COLLECTION_DESCRIPTION,
    DEFAULT_TOOL_HYBRID_SEARCH_DESCRIPTION,
    DEFAULT_TOOL_SET_COLLECTION_EMBEDDING_MODEL_DESCRIPTION,
    DEFAULT_TOOL_LIST_EMBEDDING_MODELS_DESCRIPTION,
)

METADATA_PATH = "metadata"


class ToolSettings(BaseSettings):
    """
    Configuration for all the tools with enhanced descriptions.
    """

    tool_store_description: str = Field(
        default=DEFAULT_TOOL_STORE_DESCRIPTION,
        validation_alias="TOOL_STORE_DESCRIPTION",
    )
    tool_find_description: str = Field(
        default=DEFAULT_TOOL_FIND_DESCRIPTION,
        validation_alias="TOOL_FIND_DESCRIPTION",
    )
    tool_batch_store_description: str = Field(
        default=DEFAULT_TOOL_BATCH_STORE_DESCRIPTION,
        validation_alias="TOOL_BATCH_STORE_DESCRIPTION",
    )
    tool_scroll_description: str = Field(
        default=DEFAULT_TOOL_SCROLL_DESCRIPTION,
        validation_alias="TOOL_SCROLL_DESCRIPTION",
    )
    tool_list_collections_description: str = Field(
        default=DEFAULT_TOOL_LIST_COLLECTIONS_DESCRIPTION,
        validation_alias="TOOL_LIST_COLLECTIONS_DESCRIPTION",
    )
    tool_create_collection_description: str = Field(
        default=DEFAULT_TOOL_CREATE_COLLECTION_DESCRIPTION,
        validation_alias="TOOL_CREATE_COLLECTION_DESCRIPTION",
    )
    tool_get_collection_info_description: str = Field(
        default=DEFAULT_TOOL_GET_COLLECTION_INFO_DESCRIPTION,
        validation_alias="TOOL_GET_COLLECTION_INFO_DESCRIPTION",
    )
    tool_delete_collection_description: str = Field(
        default=DEFAULT_TOOL_DELETE_COLLECTION_DESCRIPTION,
        validation_alias="TOOL_DELETE_COLLECTION_DESCRIPTION",
    )
    tool_hybrid_search_description: str = Field(
        default=DEFAULT_TOOL_HYBRID_SEARCH_DESCRIPTION,
        validation_alias="TOOL_HYBRID_SEARCH_DESCRIPTION",
    )
    tool_set_collection_embedding_model_description: str = Field(
        default=DEFAULT_TOOL_SET_COLLECTION_EMBEDDING_MODEL_DESCRIPTION,
        validation_alias="TOOL_SET_COLLECTION_EMBEDDING_MODEL_DESCRIPTION",
    )
    tool_list_embedding_models_description: str = Field(
        default=DEFAULT_TOOL_LIST_EMBEDDING_MODELS_DESCRIPTION,
        validation_alias="TOOL_LIST_EMBEDDING_MODELS_DESCRIPTION",
    )


class EmbeddingProviderSettings(BaseSettings):
    """
    Configuration for the embedding provider.
    """

    provider_type: EmbeddingProviderType = Field(
        default=EmbeddingProviderType.FASTEMBED,
        validation_alias="EMBEDDING_PROVIDER",
    )
    model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias="EMBEDDING_MODEL",
    )


class FilterableField(BaseModel):
    name: str = Field(description="The name of the field payload field to filter on")
    description: str = Field(
        description="A description for the field used in the tool description"
    )
    field_type: Literal["keyword", "integer", "float", "boolean"] = Field(
        description="The type of the field"
    )
    condition: Literal["==", "!=", ">", ">=", "<", "<=", "any", "except"] | None = (
        Field(
            default=None,
            description=(
                "The condition to use for the filter. If not provided, the field will be indexed, but no "
                "filter argument will be exposed to MCP tool."
            ),
        )
    )
    required: bool = Field(
        default=False,
        description="Whether the field is required for the filter.",
    )


class QdrantSettings(BaseSettings):
    """
    Configuration for the Qdrant connector with sensible defaults and no artificial limits.
    """

    location: str | None = Field(default=None, validation_alias="QDRANT_URL")
    api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    collection_name: str | None = Field(
        default=None, validation_alias="COLLECTION_NAME"
    )
    local_path: str | None = Field(default=None, validation_alias="QDRANT_LOCAL_PATH")

    @model_validator(mode="before")
    @classmethod
    def clean_empty_strings(cls, values):
        """Convert empty strings to None for proper validation."""
        if isinstance(values, dict):
            for key, value in values.items():
                if value == "":
                    values[key] = None
        return values

    # Increased default search limit for better results
    search_limit: int = Field(default=50, validation_alias="QDRANT_SEARCH_LIMIT")
    read_only: bool = Field(default=False, validation_alias="QDRANT_READ_ONLY")

    filterable_fields: list[FilterableField] | None = Field(default=None)

    allow_arbitrary_filter: bool = Field(
        default=False, validation_alias="QDRANT_ALLOW_ARBITRARY_FILTER"
    )

    # Enhanced settings for multi-collection support
    enable_collection_management: bool = Field(
        default=True, validation_alias="QDRANT_ENABLE_COLLECTION_MANAGEMENT"
    )
    enable_dynamic_embedding_models: bool = Field(
        default=True, validation_alias="QDRANT_ENABLE_DYNAMIC_EMBEDDING_MODELS"
    )
    default_vector_size: int = Field(
        default=384, validation_alias="QDRANT_DEFAULT_VECTOR_SIZE"
    )
    default_distance_metric: str = Field(
        default="cosine", validation_alias="QDRANT_DEFAULT_DISTANCE_METRIC"
    )

    # Removed artificial batch size limit - now unlimited
    max_batch_size: int = Field(
        default=10000, validation_alias="QDRANT_MAX_BATCH_SIZE",
        description="Maximum batch size for operations. Default is 10000 (effectively unlimited for most use cases)"
    )

    enable_resources: bool = Field(
        default=True, validation_alias="QDRANT_ENABLE_RESOURCES"
    )

    def filterable_fields_dict(self) -> dict[str, FilterableField]:
        if self.filterable_fields is None:
            return {}
        return {field.name: field for field in self.filterable_fields}

    def filterable_fields_dict_with_conditions(self) -> dict[str, FilterableField]:
        if self.filterable_fields is None:
            return {}
        return {
            field.name: field
            for field in self.filterable_fields
            if field.condition is not None
        }

    @model_validator(mode="after")
    def check_local_path_conflict(self) -> "QdrantSettings":
        if self.local_path:
            if self.location is not None or self.api_key is not None:
                raise ValueError(
                    "If 'local_path' is set, 'location' and 'api_key' must be None."
                )
        return self
