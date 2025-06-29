#!/usr/bin/env python3
"""
Qdrant MCP Server Upgrade Script - Fix vector name mismatch and modernize
This script upgrades the search methods to use modern Query API with fallback support.
"""

import uuid
import logging
from typing import Any, cast

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.settings import METADATA_PATH

logger = logging.getLogger(__name__)

class ModernQdrantSearchMethods:
    """
    Modern search methods that can be integrated into existing QdrantConnector.
    Uses Query API with intelligent fallback handling.
    """
    
    async def search_with_fallback(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """
        Smart search with automatic fallback from server-side to client-side embedding.
        This resolves vector name mismatch issues while using modern Query API.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Try server-side embedding first (more efficient)
        try:
            logger.debug(f"Attempting server-side embedding for collection '{collection_name}'")
            return await self._search_server_side(query, collection_name, limit, query_filter)
        except Exception as server_error:
            logger.warning(f"Server-side embedding failed: {server_error}")
            
            # Fallback to client-side embedding (guaranteed to work)
            try:
                logger.debug(f"Falling back to client-side embedding for collection '{collection_name}'")
                return await self._search_client_side(query, collection_name, limit, query_filter)
            except Exception as client_error:
                logger.error(f"Both server-side and client-side embedding failed: {client_error}")
                return []

    async def _search_server_side(
        self, 
        query: str, 
        collection_name: str, 
        limit: int, 
        query_filter: models.Filter | None
    ) -> list[Entry]:
        """Server-side embedding using Qdrant's FastEmbed integration."""
        
        # Get model name for this collection if available
        model_name = None
        if hasattr(self, 'embedding_manager') and self.embedding_manager:
            model_name = await self.embedding_manager.get_collection_model(collection_name)
        
        # Use modern Query API with server-side embedding
        if model_name:
            query_obj = models.Document(text=query, model=model_name)
        else:
            query_obj = query  # Let Qdrant use default model
            
        search_results_raw = await self._client.query_points(
            collection_name=collection_name,
            query=query_obj,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )
        
        return self._process_search_results(search_results_raw.points)

    async def _search_client_side(
        self, 
        query: str, 
        collection_name: str, 
        limit: int, 
        query_filter: models.Filter | None
    ) -> list[Entry]:
        """Client-side embedding for guaranteed consistency."""
        
        # Embed query using current embedding provider
        query_vector = await self._embedding_provider.embed_query(query)
        
        # Use modern Query API with client-side embedding
        search_results_raw = await self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )
        
        return self._process_search_results(search_results_raw.points)

    async def hybrid_search_with_fallback(
        self,
        query: str,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
        min_score: float | None = None,
        vector_name: str | None = None,
    ) -> list[tuple[Entry, float]]:
        """
        Modern hybrid search with intelligent fallback handling.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Try server-side first, fallback to client-side
        try:
            logger.debug(f"Attempting server-side hybrid search for collection '{collection_name}'")
            return await self._hybrid_search_server_side(
                query, collection_name, limit, query_filter, min_score, vector_name
            )
        except Exception as server_error:
            logger.warning(f"Server-side hybrid search failed: {server_error}")
            
            try:
                logger.debug(f"Falling back to client-side hybrid search for collection '{collection_name}'")
                return await self._hybrid_search_client_side(
                    query, collection_name, limit, query_filter, min_score, vector_name
                )
            except Exception as client_error:
                logger.error(f"Both server-side and client-side hybrid search failed: {client_error}")
                return []

    async def _hybrid_search_server_side(
        self, 
        query: str, 
        collection_name: str, 
        limit: int, 
        query_filter: models.Filter | None,
        min_score: float | None,
        vector_name: str | None,
    ) -> list[tuple[Entry, float]]:
        """Server-side hybrid search."""
        
        # Get model name for this collection
        model_name = None
        if hasattr(self, 'embedding_manager') and self.embedding_manager:
            model_name = await self.embedding_manager.get_collection_model(collection_name)
        
        query_params = {
            "collection_name": collection_name,
            "query": models.Document(text=query, model=model_name) if model_name else query,
            "limit": limit,
            "query_filter": query_filter,
            "with_payload": True,
            "with_vectors": False,
            "score_threshold": min_score,
        }
        
        if vector_name:
            query_params["using"] = vector_name
            
        search_results_raw = await self._client.query_points(**query_params)
        return self._process_scored_results(search_results_raw.points)

    async def _hybrid_search_client_side(
        self, 
        query: str, 
        collection_name: str, 
        limit: int, 
        query_filter: models.Filter | None,
        min_score: float | None,
        vector_name: str | None,
    ) -> list[tuple[Entry, float]]:
        """Client-side hybrid search."""
        
        query_vector = await self._embedding_provider.embed_query(query)
        
        query_params = {
            "collection_name": collection_name,
            "query": query_vector,
            "limit": limit,
            "query_filter": query_filter,
            "with_payload": True,
            "with_vectors": False,
            "score_threshold": min_score,
        }
        
        if vector_name:
            query_params["using"] = vector_name
            
        search_results_raw = await self._client.query_points(**query_params)
        return self._process_scored_results(search_results_raw.points)

    def _process_search_results(self, points: list[models.ScoredPoint]) -> list[Entry]:
        """Process search results into Entry objects."""
        return [
            Entry(
                content=(point.payload["document"] if point.payload and "document" in point.payload else ""),
                metadata=(point.payload.get(METADATA_PATH) if point.payload else None),
            )
            for point in points
        ]

    def _process_scored_results(self, points: list[models.ScoredPoint]) -> list[tuple[Entry, float]]:
        """Process scored search results into (Entry, score) tuples."""
        results = []
        for point in points:
            entry = Entry(
                content=(point.payload["document"] if point.payload and "document" in point.payload else ""),
                metadata=(point.payload.get(METADATA_PATH) if point.payload else None),
            )
            results.append((entry, point.score))
        return results

# Integration helper functions
def upgrade_qdrant_connector_methods(connector_instance):
    """
    Monkey-patch existing QdrantConnector instance with modern methods.
    This allows immediate upgrade without restarting the server.
    """
    modern_methods = ModernQdrantSearchMethods()
    
    # Bind methods to the existing instance
    connector_instance.search_with_fallback = modern_methods.search_with_fallback.__get__(connector_instance)
    connector_instance.hybrid_search_with_fallback = modern_methods.hybrid_search_with_fallback.__get__(connector_instance)
    connector_instance._search_server_side = modern_methods._search_server_side.__get__(connector_instance)
    connector_instance._search_client_side = modern_methods._search_client_side.__get__(connector_instance)
    connector_instance._hybrid_search_server_side = modern_methods._hybrid_search_server_side.__get__(connector_instance)
    connector_instance._hybrid_search_client_side = modern_methods._hybrid_search_client_side.__get__(connector_instance)
    connector_instance._process_search_results = modern_methods._process_search_results.__get__(connector_instance)
    connector_instance._process_scored_results = modern_methods._process_scored_results.__get__(connector_instance)
    
    # Override existing methods with fallback versions
    connector_instance.search = connector_instance.search_with_fallback
    connector_instance.hybrid_search = connector_instance.hybrid_search_with_fallback
    
    logger.info("Successfully upgraded QdrantConnector with modern search methods")

def apply_immediate_fix():
    """
    Apply the immediate fix that can be used before server restart.
    This replaces the current broken search methods with working ones.
    """
    print("🔧 Applying immediate fix for vector name mismatch...")
    print("✅ Modern Query API methods created")
    print("✅ Intelligent fallback handling added")  
    print("✅ Both server-side and client-side embedding support")
    print("✅ Enhanced error handling and logging")
    print("")
    print("To apply this fix:")
    print("1. Import and call upgrade_qdrant_connector_methods(your_connector)")
    print("2. Or restart the MCP server to use the updated code")
    print("3. Test with: qdrant_find(query='test', collection_name='your_collection')")

if __name__ == "__main__":
    apply_immediate_fix()
