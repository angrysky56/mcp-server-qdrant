from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings

from mcp_server_qdrant.embeddings.types import EmbeddingProviderType

DEFAULT_TOOL_STORE_DESCRIPTION = (
    "Store information in Qdrant with optional metadata. Use this tool when you need to remember something. "
    "Metadata is optional and can contain any key-value pairs for additional context."
)
DEFAULT_TOOL_FIND_DESCRIPTION = (
    "Look up memories in Qdrant. Use this tool when you need to: \n"
    " - Find memories by their content \n"
    " - Access memories for further analysis \n"
    " - Get some personal information about the user"
)

# Enhanced tool descriptions
DEFAULT_TOOL_BATCH_STORE_DESCRIPTION = (
    "Store multiple entries efficiently in a single batch operation. Each entry can have content, metadata, and optional ID."
)
DEFAULT_TOOL_SCROLL_DESCRIPTION = (
    "Browse through collection contents with pagination and optional filtering."
)
DEFAULT_TOOL_LIST_COLLECTIONS_DESCRIPTION = (
    "List all available Qdrant collections with their basic information."
)
DEFAULT_TOOL_CREATE_COLLECTION_DESCRIPTION = (
    "Create a new Qdrant collection with specified parameters including vector size and distance metric."
)
DEFAULT_TOOL_GET_COLLECTION_INFO_DESCRIPTION = (
    "Get detailed information about a specific collection including configuration and statistics."
)
DEFAULT_TOOL_DELETE_COLLECTION_DESCRIPTION = (
    "Delete a collection permanently. Use with caution as this cannot be undone."
)
DEFAULT_TOOL_HYBRID_SEARCH_DESCRIPTION = (
    "Perform advanced search with multiple search strategies and complex filtering."
)
DEFAULT_TOOL_SET_COLLECTION_EMBEDDING_MODEL_DESCRIPTION = (
    "Set or change the embedding model for a specific collection."
)
DEFAULT_TOOL_LIST_EMBEDDING_MODELS_DESCRIPTION = (
    "List all available embedding models and their specifications."
)

METADATA_PATH = "metadata"


class ToolSettings(BaseSettings):
    """
    Configuration for all the tools.
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
    Configuration for the Qdrant connector.
    """

    location: str | None = Field(default=None, validation_alias="QDRANT_URL")
    api_key: str | None = Field(default=None, validation_alias="QDRANT_API_KEY")
    collection_name: str | None = Field(
        default=None, validation_alias="COLLECTION_NAME"
    )
    local_path: str | None = Field(default=None, validation_alias="QDRANT_LOCAL_PATH")
    search_limit: int = Field(default=10, validation_alias="QDRANT_SEARCH_LIMIT")
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
    max_batch_size: int = Field(
        default=100, validation_alias="QDRANT_MAX_BATCH_SIZE"
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
