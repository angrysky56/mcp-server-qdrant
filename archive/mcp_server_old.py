import json
import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field
from qdrant_client import models

from mcp_server_qdrant.common.filters import make_indexes
from mcp_server_qdrant.common.func_tools import make_partial_function
from mcp_server_qdrant.common.wrap_filters import wrap_filters
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.embedding_manager import EmbeddingModelManager
from mcp_server_qdrant.qdrant import ArbitraryFilter, Entry, QdrantConnector, BatchEntry
from mcp_server_qdrant.settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

logger = logging.getLogger(__name__)


class QdrantMCPServer(FastMCP):
    """
    A MCP server for Qdrant with enhanced collection management and dynamic embedding models.
    """

    def __init__(
        self,
        tool_settings: ToolSettings,
        qdrant_settings: QdrantSettings,
        embedding_provider_settings: EmbeddingProviderSettings,
        name: str = "mcp-server-qdrant",
        instructions: str | None = None,
        **settings: Any,
    ):
        self.tool_settings = tool_settings
        self.qdrant_settings = qdrant_settings
        self.embedding_provider_settings = embedding_provider_settings

        # Initialize embedding model manager for dynamic model support
        self.embedding_manager = EmbeddingModelManager(embedding_provider_settings)

        # Use default embedding provider for initial setup
        self.embedding_provider = create_embedding_provider(embedding_provider_settings)
        self.qdrant_connector = QdrantConnector(
            qdrant_settings.location,
            qdrant_settings.api_key,
            qdrant_settings.collection_name,
            self.embedding_provider,
            qdrant_settings.local_path,
            make_indexes(qdrant_settings.filterable_fields_dict()),
        )

        super().__init__(name=name, instructions=instructions, **settings)

        self.setup_tools()
        if self.qdrant_settings.enable_resources:
            self.setup_resources()

    def format_entry(self, entry: Entry) -> str:
        """
        Feel free to override this method in your subclass to customize the format of the entry.
        """
        entry_metadata = json.dumps(entry.metadata) if entry.metadata else ""
        return f"<entry><content>{entry.content}</content><metadata>{entry_metadata}</metadata></entry>"

    def setup_tools(self) -> None:
        """
        Register the tools in the server, including find and store tools, and enhanced tools if enabled.
        Applies filter conditions and collection defaults as needed.
        """

        # Core find tool
        async def find(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            collection_name: Annotated[
                str, Field(description="The collection to search in")
            ],
            query_filter: ArbitraryFilter | None = None,
        ) -> list[str]:
            """
            Find memories in Qdrant.
            Args:
                ctx (Context): The request context.
                query (str): The query string to search for.
                collection_name (str): The collection to search in.
                query_filter (ArbitraryFilter | None): Optional filter for the query.
            Returns:
                list[str]: List of formatted search results or a message if not found.
            """
            await ctx.debug(f"Query filter: {query_filter}")

            # Convert dict to Filter object only when passing to search method
            filter_obj = models.Filter(**query_filter) if query_filter else None

            await ctx.debug(f"Finding results for query {query}")
            entries = await self.qdrant_connector.search(
                query,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                query_filter=filter_obj,
            )

            if not entries:
                return [f"No information found for the query '{query}'"]
            content = [
                f"Results for the query '{query}'",
            ]
            for entry in entries:
                content.append(self.format_entry(entry))
            return content

        # Core store tool - fixed version that actually works
        async def qdrant_store(
            ctx: Context,
            content: Annotated[str, Field(description="Text content to store")],
            collection_name: Annotated[str, Field(description="Collection to store the information in")],
            metadata: Annotated[str | None, Field(description="Optional metadata as JSON string")] = None,
            entry_id: Annotated[str | None, Field(description="Optional custom ID for the entry")] = None,
        ) -> str:
            """
            Store information in Qdrant with optional metadata.
            Args:
                ctx (Context): The request context.
                content (str): The text content to store.
                collection_name (str): The collection to store the information in.
                metadata (str | None): Optional metadata as JSON string (MCP limitation).
                entry_id (str | None): Optional custom ID for the entry.
            Returns:
                str: Success or error message.
            """
            try:
                await ctx.debug(f"Storing content in collection '{collection_name}'")

                # Parse metadata from JSON string (MCP sends dicts as strings)
                parsed_metadata = None
                if metadata:
                    try:
                        parsed_metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        return f"Invalid metadata JSON: {metadata}"

                # Create entry using BatchEntry which works correctly
                batch_entry = BatchEntry(
                    content=content,
                    metadata=parsed_metadata,
                    id=entry_id
                )

                # Get appropriate embedding provider for collection
                embedding_provider = self.embedding_manager.get_provider_for_collection(collection_name)

                # Update connector's embedding provider temporarily
                original_provider = self.qdrant_connector._embedding_provider
                self.qdrant_connector._embedding_provider = embedding_provider

                try:
                    stored_count = await self.qdrant_connector.batch_store([batch_entry], collection_name)
                finally:
                    # Restore original provider
                    self.qdrant_connector._embedding_provider = original_provider

                if stored_count > 0:
                    return f"Successfully stored entry in collection '{collection_name}'"
                else:
                    return f"Failed to store entry in collection '{collection_name}'"

            except Exception as e:
                await ctx.debug(f"Error storing content: {e}")
                return f"Error storing content: {str(e)}"

        # Register find tool with filters applied
        filterable_conditions = (
            self.qdrant_settings.filterable_fields_dict_with_conditions()
        )

        find_tool = find
        if len(filterable_conditions) > 0:
            find_tool = wrap_filters(find_tool, filterable_conditions)
        elif not self.qdrant_settings.allow_arbitrary_filter:
            find_tool = make_partial_function(find_tool, {"query_filter": None})

        if self.qdrant_settings.collection_name:
            find_tool = make_partial_function(
                find_tool, {"collection_name": self.qdrant_settings.collection_name}
            )

        # Register the find tool
        find_tool.__name__ = "qdrant_find"
        self.tool(name="qdrant_find", description=self.tool_settings.tool_find_description)(find_tool)

        # Register store tool if not read-only
        if not self.qdrant_settings.read_only:
            store_tool = qdrant_store
            if self.qdrant_settings.collection_name:
                store_tool = make_partial_function(
                    store_tool, {"collection_name": self.qdrant_settings.collection_name}
                )

            store_tool.__name__ = "qdrant_store"
            self.tool(name="qdrant_store", description=self.tool_settings.tool_store_description)(store_tool)

        # Add enhanced tools if enabled
        if self.qdrant_settings.enable_collection_management:
            self.setup_collection_management_tools()

        if self.qdrant_settings.enable_dynamic_embedding_models:
            self.setup_embedding_model_tools()

        # Always add advanced search tools
        self.setup_advanced_search_tools()

    def setup_collection_management_tools(self):
        """Setup tools for collection management."""

        @self.tool(description=self.tool_settings.tool_list_collections_description)
        async def list_collections(ctx: Context) -> list[str]:
            """List all available Qdrant collections."""
            try:
                collections = await self.qdrant_connector.get_collection_names()
                if not collections:
                    return ["No collections found"]
                return [f"Available collections: {', '.join(collections)}"]
            except Exception as e:
                await ctx.debug(f"Error listing collections: {e}")
                return [f"Error listing collections: {str(e)}"]

        @self.tool(description=self.tool_settings.tool_get_collection_info_description)
        async def get_collection_info(
            ctx: Context,
            collection_name: Annotated[str, Field(description="Name of the collection to get info about")]
        ) -> list[str]:
            """Get detailed information about a specific collection."""
            try:
                info = await self.qdrant_connector.get_detailed_collection_info(collection_name)
                if not info:
                    return [f"Collection '{collection_name}' not found"]

                return [
                    f"Collection Information for '{collection_name}':",
                    f"Points: {info.points_count:,}",
                    f"Vectors: {info.vectors_count:,}",
                    f"Indexed Vectors: {info.indexed_vectors_count:,}",
                    f"Segments: {info.segments_count}",
                    f"Status: {info.status}",
                    f"Optimizer Status: {info.optimizer_status}",
                    f"Vector Size: {info.vector_size or 'Unknown'}",
                    f"Distance Metric: {info.distance_metric or 'Unknown'}"
                ]
            except Exception as e:
                await ctx.debug(f"Error getting collection info: {e}")
                return [f"Error getting collection info: {str(e)}"]

        if not self.qdrant_settings.read_only:
            @self.tool(description=self.tool_settings.tool_create_collection_description)
            async def create_collection(
                ctx: Context,
                collection_name: Annotated[str, Field(description="Name of the collection to create")],
                vector_size: Annotated[int, Field(description="Size of the vectors (e.g., 384, 768, 1024)")],
                distance: Annotated[str, Field(description="Distance metric: cosine, dot, euclidean, manhattan")] = "cosine",
                embedding_model: Annotated[str, Field(description="Embedding model to use for this collection")] = ""
            ) -> str:
                """Create a new collection with specified parameters."""
                try:
                    # Set embedding model for collection if specified
                    embedding_provider = None
                    if embedding_model:
                        if self.embedding_manager.set_collection_model(collection_name, embedding_model):
                            embedding_provider = self.embedding_manager.get_provider_for_collection(collection_name)
                            # Update vector size based on model
                            model_info = self.embedding_manager.get_model_info(embedding_model)
                            if model_info:
                                vector_size = model_info.vector_size
                        else:
                            return f"Failed to set embedding model '{embedding_model}' for collection '{collection_name}'"

                    success = await self.qdrant_connector.create_collection_with_config(
                        collection_name, vector_size, distance, embedding_provider
                    )
                    if success:
                        result = f"Successfully created collection '{collection_name}' with vector size {vector_size} and {distance} distance"
                        if embedding_model:
                            result += f" using embedding model '{embedding_model}'"
                        return result
                    else:
                        return f"Failed to create collection '{collection_name}'"
                except Exception as e:
                    await ctx.debug(f"Error creating collection: {e}")
                    return f"Error creating collection: {str(e)}"

            @self.tool(description=self.tool_settings.tool_delete_collection_description)
            async def delete_collection(
                ctx: Context,
                collection_name: Annotated[str, Field(description="Name of the collection to delete")],
                confirm: Annotated[bool, Field(description="Confirmation that you want to delete this collection")] = False
            ) -> str:
                """Delete a collection permanently. Requires confirmation."""
                if not confirm:
                    return f"Please set confirm=True to delete collection '{collection_name}'. This action cannot be undone."

                try:
                    # Remove from embedding manager
                    self.embedding_manager.remove_collection_model(collection_name)

                    success = await self.qdrant_connector.delete_collection(collection_name)
                    if success:
                        return f"Successfully deleted collection '{collection_name}'"
                    else:
                        return f"Failed to delete collection '{collection_name}'"
                except Exception as e:
                    await ctx.debug(f"Error deleting collection: {e}")
                    return f"Error deleting collection: {str(e)}"

    def setup_embedding_model_tools(self):
        """Setup tools for embedding model management."""

        @self.tool(description=self.tool_settings.tool_list_embedding_models_description)
        async def list_embedding_models(ctx: Context) -> list[str]:
            """List all available embedding models."""
            try:
                models = self.embedding_manager.list_available_models()
                if not models:
                    return ["No embedding models available"]

                result = ["Available Embedding Models:"]
                for model in models:
                    result.append(f"• {model.model_name} ({model.provider_type}) - {model.vector_size}D - {model.description}")
                return result
            except Exception as e:
                await ctx.debug(f"Error listing models: {e}")
                return [f"Error listing models: {str(e)}"]

        if not self.qdrant_settings.read_only:
            @self.tool(description=self.tool_settings.tool_set_collection_embedding_model_description)
            async def set_collection_embedding_model(
                ctx: Context,
                collection_name: Annotated[str, Field(description="Name of the collection")],
                model_name: Annotated[str, Field(description="Name of the embedding model to use")]
            ) -> str:
                """Set the embedding model for a specific collection."""
                try:
                    success = self.embedding_manager.set_collection_model(collection_name, model_name)
                    if success:
                        return f"Successfully set embedding model '{model_name}' for collection '{collection_name}'"
                    else:
                        return f"Failed to set embedding model '{model_name}' for collection '{collection_name}'"
                except Exception as e:
                    await ctx.debug(f"Error setting model: {e}")
                    return f"Error setting model: {str(e)}"

    def setup_advanced_search_tools(self):
        """Setup advanced search and storage tools."""

        @self.tool(description=self.tool_settings.tool_hybrid_search_description)
        async def hybrid_search(
            ctx: Context,
            query: Annotated[str, Field(description="Search query")],
            collection_name: Annotated[str, Field(description="Collection to search in")],
            limit: Annotated[int, Field(description="Maximum number of results")] = 10,
            min_score: Annotated[float, Field(description="Minimum similarity score threshold")] = 0.0,
            include_scores: Annotated[bool, Field(description="Include similarity scores in results")] = True
        ) -> list[str]:
            """Perform advanced search with similarity scores and filtering."""
            try:
                # Get appropriate embedding provider for collection
                embedding_provider = self.embedding_manager.get_provider_for_collection(collection_name)

                # Update connector's embedding provider temporarily
                original_provider = self.qdrant_connector._embedding_provider
                self.qdrant_connector._embedding_provider = embedding_provider

                try:
                    results = await self.qdrant_connector.hybrid_search(
                        query=query,
                        collection_name=collection_name,
                        limit=limit,
                        min_score=min_score if min_score > 0 else None
                    )
                finally:
                    # Restore original provider
                    self.qdrant_connector._embedding_provider = original_provider

                if not results:
                    return [f"No results found for query '{query}' in collection '{collection_name}'"]

                content = [f"Hybrid search results for '{query}' in '{collection_name}':"]
                for entry, score in results:
                    if include_scores:
                        content.append(f"[Score: {score:.4f}] {self.format_entry(entry)}")
                    else:
                        content.append(self.format_entry(entry))

                return content
            except Exception as e:
                await ctx.debug(f"Error in hybrid search: {e}")
                return [f"Error in hybrid search: {str(e)}"]

        @self.tool(description=self.tool_settings.tool_scroll_description)
        async def scroll_collection(
            ctx: Context,
            collection_name: Annotated[str, Field(description="Collection to browse")],
            limit: Annotated[int, Field(description="Maximum number of entries to return")] = 20,
            offset: Annotated[str, Field(description="Pagination offset (point ID to start from)")] = ""
        ) -> list[str]:
            """Browse through collection contents with pagination."""
            try:
                entries, next_offset = await self.qdrant_connector.scroll_collection(
                    collection_name=collection_name,
                    limit=min(limit, self.qdrant_settings.max_batch_size),
                    offset=offset if offset else None
                )

                if not entries:
                    return [f"No entries found in collection '{collection_name}'"]

                content = [f"Browsing collection '{collection_name}' (showing {len(entries)} entries):"]
                for entry in entries:
                    content.append(self.format_entry(entry))

                if next_offset:
                    content.append(f"Next page offset: {next_offset}")
                else:
                    content.append("End of collection reached")

                return content
            except Exception as e:
                await ctx.debug(f"Error scrolling collection: {e}")
                return [f"Error scrolling collection: {str(e)}"]

        if not self.qdrant_settings.read_only:
            @self.tool(description=self.tool_settings.tool_batch_store_description)
            async def qdrant_store_batch(
                ctx: Context,
                entries: Annotated[list[dict], Field(description="List of entries to store, each with 'content' and optional 'metadata' and 'id'")],
                collection_name: Annotated[str, Field(description="Collection to store entries in")]
            ) -> str:
                """Store multiple entries efficiently in a single batch operation."""
                try:
                    # Validate and convert entries
                    batch_entries = []
                    for i, entry_dict in enumerate(entries):
                        if "content" not in entry_dict:
                            return f"Entry {i} missing required 'content' field"

                        batch_entries.append(BatchEntry(
                            content=entry_dict["content"],
                            metadata=entry_dict.get("metadata"),
                            id=entry_dict.get("id")
                        ))

                    if len(batch_entries) > self.qdrant_settings.max_batch_size:
                        return f"Batch size {len(batch_entries)} exceeds maximum {self.qdrant_settings.max_batch_size}"

                    # Get appropriate embedding provider for collection
                    embedding_provider = self.embedding_manager.get_provider_for_collection(collection_name)

                    # Update connector's embedding provider temporarily
                    original_provider = self.qdrant_connector._embedding_provider
                    self.qdrant_connector._embedding_provider = embedding_provider

                    try:
                        stored_count = await self.qdrant_connector.batch_store(batch_entries, collection_name)
                    finally:
                        # Restore original provider
                        self.qdrant_connector._embedding_provider = original_provider

                    return f"Successfully stored {stored_count} entries in collection '{collection_name}'"
                except Exception as e:
                    await ctx.debug(f"Error in batch store: {e}")
                    return f"Error in batch store: {str(e)}"

    def setup_resources(self):
        """Setup MCP resources for collection information."""

        @self.resource("qdrant://collections")
        async def collections_overview() -> str:
            """Overview of all collections and their statistics."""
            try:
                collections = await self.qdrant_connector.get_collection_names()
                if not collections:
                    return "No collections found in Qdrant database."

                overview = ["# Qdrant Collections Overview\n"]

                for collection_name in collections:
                    info = await self.qdrant_connector.get_detailed_collection_info(collection_name)
                    if info:
                        overview.append(f"## Collection: {collection_name}")
                        overview.append(f"- **Points**: {info.points_count:,}")
                        overview.append(f"- **Vectors**: {info.vectors_count:,}")
                        overview.append(f"- **Status**: {info.status}")
                        overview.append(f"- **Vector Size**: {info.vector_size or 'Unknown'}")
                        overview.append(f"- **Distance Metric**: {info.distance_metric or 'Unknown'}")

                        # Check if collection has associated embedding model
                        model = self.embedding_manager.get_collection_model(collection_name)
                        if model:
                            overview.append(f"- **Embedding Model**: {model}")
                        overview.append("")

                return "\n".join(overview)
            except Exception as e:
                return f"Error getting collections overview: {str(e)}"

        @self.resource("qdrant://collection/{collection_name}/schema")
        async def collection_schema(collection_name: str) -> str:
            """Detailed schema and configuration for a specific collection."""
            try:
                info = await self.qdrant_connector.get_detailed_collection_info(collection_name)
                if not info:
                    return f"Collection '{collection_name}' not found."

                schema = [f"# Collection Schema: {collection_name}\n"]

                schema.append("## Configuration")
                schema.append(f"- **Vector Size**: {info.vector_size or 'Unknown'}")
                schema.append(f"- **Distance Metric**: {info.distance_metric or 'Unknown'}")
                schema.append(f"- **Status**: {info.status}")
                schema.append(f"- **Optimizer Status**: {info.optimizer_status}")
                schema.append("")

                schema.append("## Statistics")
                schema.append(f"- **Total Points**: {info.points_count:,}")
                schema.append(f"- **Total Vectors**: {info.vectors_count:,}")
                schema.append(f"- **Indexed Vectors**: {info.indexed_vectors_count:,}")
                schema.append(f"- **Segments**: {info.segments_count}")
                schema.append("")

                # Show embedding model if assigned
                model = self.embedding_manager.get_collection_model(collection_name)
                if model:
                    model_info = self.embedding_manager.get_model_info(model)
                    schema.append("## Embedding Model")
                    schema.append(f"- **Model**: {model}")
                    if model_info:
                        schema.append(f"- **Provider**: {model_info.provider_type}")
                        schema.append(f"- **Vector Size**: {model_info.vector_size}")
                        schema.append(f"- **Description**: {model_info.description}")
                    schema.append("")

                return "\n".join(schema)
            except Exception as e:
                return f"Error getting collection schema: {str(e)}"
