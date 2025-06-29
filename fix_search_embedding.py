#!/usr/bin/env python3
"""
Fix for the embedding vector name mismatch issue.
This script patches the search method to use client-side embedding.
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, '/home/ty/Repositories/mcp-server-qdrant/src')

def create_fixed_search_method():
    """Create a fixed search method that uses client-side embedding."""
    
    search_method_code = '''
    async def search(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """
        Find points in the Qdrant collection using CLIENT-SIDE embedding to avoid vector name mismatch.
        :param query: The query to use for the search.
        :param collection_name: The name of the collection to search in.
        :param limit: The maximum number of entries to return.
        :param query_filter: The filter to apply to the query, if any.
        :return: A list of entries found.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # CRITICAL FIX: Use CLIENT-SIDE embedding to avoid vector name mismatch
        # Get the vector name from the current embedding provider
        vector_name = self._embedding_provider.get_vector_name()
        
        # Embed the query using the current embedding provider
        query_vector = await self._embedding_provider.embed_query(query)
        
        # Use the specific vector name when searching
        search_results_raw = await self._client.search(
            collection_name=collection_name,
            query_vector=models.NamedVector(
                name=vector_name,
                vector=query_vector
            ),
            limit=limit,
            query_filter=query_filter,
        )
        search_results = cast(list[models.ScoredPoint], search_results_raw)

        return [
            Entry(
                content=(point.payload["document"] if point.payload and "document" in point.payload else ""),
                metadata=(point.payload.get(METADATA_PATH) if point.payload else None),
            )
            for point in search_results
        ]
    '''
    
    return search_method_code

def create_fixed_hybrid_search_method():
    """Create a fixed hybrid search method that uses client-side embedding."""
    
    hybrid_search_method_code = '''
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
        Perform hybrid search with scoring using CLIENT-SIDE embedding.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        try:
            # CRITICAL FIX: Use CLIENT-SIDE embedding
            vector_name = self._embedding_provider.get_vector_name()
            query_vector = await self._embedding_provider.embed_query(query)

            search_results_raw = await self._client.search(
                collection_name=collection_name,
                query_vector=models.NamedVector(
                    name=vector_name,
                    vector=query_vector
                ),
                limit=limit,
                query_filter=query_filter,
                score_threshold=min_score,
            )
            search_results = cast(list[models.ScoredPoint], search_results_raw)

            results = []
            for scored_point in search_results:
                entry = Entry(
                    content=(scored_point.payload["document"] if scored_point.payload and "document" in scored_point.payload else ""),
                    metadata=(scored_point.payload.get(METADATA_PATH) if scored_point.payload else None),
                )
                score = scored_point.score
                results.append((entry, score))
            return results
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    '''
    
    return hybrid_search_method_code

if __name__ == "__main__":
    print("🔧 Fixed search methods created!")
    print("\nFixed search method:")
    print(create_fixed_search_method())
    print("\nFixed hybrid search method:")
    print(create_fixed_hybrid_search_method())
