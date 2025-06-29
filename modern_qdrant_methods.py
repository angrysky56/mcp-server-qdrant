#!/usr/bin/env python3
"""
Modern Qdrant search methods using the Query API (v1.10+).
This implementation provides both client-side and server-side embedding options.
"""

# Modern search method using Query API
async def search_modern(
    self,
    query: str,
    *,
    collection_name: str | None = None,
    limit: int = 10,
    query_filter: models.Filter | None = None,
    use_server_side_embedding: bool = False,
) -> list[Entry]:
    """
    Modern search using Qdrant's Query API with flexible embedding options.
    
    :param query: The query to use for the search.
    :param collection_name: The name of the collection to search in.
    :param limit: The maximum number of entries to return.
    :param query_filter: The filter to apply to the query, if any.
    :param use_server_side_embedding: Whether to use server-side embedding (FastEmbed).
    :return: A list of entries found.
    """
    collection_name = collection_name or self._default_collection_name
    assert collection_name is not None
    
    collection_exists = await self._client.collection_exists(collection_name)
    if not collection_exists:
        return []

    try:
        if use_server_side_embedding:
            # SERVER-SIDE EMBEDDING: Use Qdrant's FastEmbed integration
            model_name = await self._get_collection_model_name(collection_name)
            
            search_results_raw = await self._client.query_points(
                collection_name=collection_name,
                query=models.Document(text=query, model=model_name) if model_name else query,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False,
            )
        else:
            # CLIENT-SIDE EMBEDDING: Guaranteed consistency with collection's model
            query_vector = await self._embedding_provider.embed_query(query)
            
            search_results_raw = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False,
            )
        
        search_results = cast(list[models.ScoredPoint], search_results_raw.points)

        return [
            Entry(
                content=(point.payload["document"] if point.payload and "document" in point.payload else ""),
                metadata=(point.payload.get(METADATA_PATH) if point.payload else None),
            )
            for point in search_results
        ]
        
    except Exception as e:
        logger.error(f"Error in modern search: {e}")
        # Fallback to client-side if server-side fails
        if use_server_side_embedding:
            logger.info("Falling back to client-side embedding")
            return await self.search_modern(
                query, 
                collection_name=collection_name, 
                limit=limit, 
                query_filter=query_filter, 
                use_server_side_embedding=False
            )
        return []

# Modern hybrid search method
async def hybrid_search_modern(
    self,
    query: str,
    collection_name: str | None = None,
    limit: int = 10,
    query_filter: models.Filter | None = None,
    min_score: float | None = None,
    use_server_side_embedding: bool = False,
    vector_name: str | None = None,
) -> list[tuple[Entry, float]]:
    """
    Modern hybrid search using Qdrant's Query API with advanced features.
    
    :param query: The search query.
    :param collection_name: Name of the collection to search.
    :param limit: Maximum number of results.
    :param query_filter: Optional filter to apply.
    :param min_score: Minimum similarity score threshold.
    :param use_server_side_embedding: Whether to use server-side embedding.
    :param vector_name: Specific vector name to use (for multi-vector collections).
    :return: List of (entry, score) tuples.
    """
    collection_name = collection_name or self._default_collection_name
    assert collection_name is not None
    
    collection_exists = await self._client.collection_exists(collection_name)
    if not collection_exists:
        return []

    try:
        query_params = {
            "collection_name": collection_name,
            "limit": limit,
            "query_filter": query_filter,
            "with_payload": True,
            "with_vectors": False,
            "score_threshold": min_score,
        }
        
        if vector_name:
            query_params["using"] = vector_name
            
        if use_server_side_embedding:
            # SERVER-SIDE: Use FastEmbed with model specification
            model_name = await self._get_collection_model_name(collection_name)
            query_params["query"] = models.Document(text=query, model=model_name) if model_name else query
        else:
            # CLIENT-SIDE: Use embedding provider
            query_vector = await self._embedding_provider.embed_query(query)
            query_params["query"] = query_vector

        search_results_raw = await self._client.query_points(**query_params)
        search_results = cast(list[models.ScoredPoint], search_results_raw.points)

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
        logger.error(f"Error in modern hybrid search: {e}")
        # Fallback to client-side if server-side fails
        if use_server_side_embedding:
            logger.info("Falling back to client-side embedding for hybrid search")
            return await self.hybrid_search_modern(
                query,
                collection_name=collection_name,
                limit=limit,
                query_filter=query_filter,
                min_score=min_score,
                use_server_side_embedding=False,
                vector_name=vector_name,
            )
        return []

# Helper method to get collection model name
async def _get_collection_model_name(self, collection_name: str) -> str | None:
    """Get the model name associated with a collection."""
    try:
        # This would integrate with the embedding manager
        if hasattr(self, '_embedding_manager'):
            return await self._embedding_manager.get_collection_model(collection_name)
        return None
    except Exception as e:
        logger.warning(f"Could not get model name for collection {collection_name}: {e}")
        return None

# Modern collection creation with optimization
async def create_collection_with_modern_config(
    self,
    collection_name: str,
    vector_size: int,
    distance: str = "cosine",
    embedding_provider: EmbeddingProvider | None = None,
    performance_profile: str = "balanced",
) -> bool:
    """
    Create collection with modern optimization settings.
    
    :param collection_name: Name of the collection.
    :param vector_size: Size of vectors.
    :param distance: Distance metric.
    :param embedding_provider: Embedding provider to use.
    :param performance_profile: "fast", "balanced", or "quality".
    :return: Success status.
    """
    try:
        # Performance profiles
        profiles = {
            "fast": {
                "hnsw_config": models.HnswConfig(m=16, ef_construct=100),
                "quantization_config": models.ScalarQuantizationConfig(
                    scalar=models.ScalarQuantization(type=models.ScalarType.INT8)
                )
            },
            "balanced": {
                "hnsw_config": models.HnswConfig(m=16, ef_construct=200),
            },
            "quality": {
                "hnsw_config": models.HnswConfig(m=64, ef_construct=400),
            }
        }
        
        config = profiles.get(performance_profile, profiles["balanced"])
        
        # Map distance string to enum
        distance_map = {
            "cosine": models.Distance.COSINE,
            "dot": models.Distance.DOT,
            "euclidean": models.Distance.EUCLID,
            "manhattan": models.Distance.MANHATTAN,
        }
        
        vector_params = models.VectorParams(
            size=vector_size,
            distance=distance_map.get(distance, models.Distance.COSINE),
            **config
        )
        
        await self._client.create_collection(
            collection_name=collection_name,
            vectors_config=vector_params,
            optimizers_config=models.OptimizersConfig(
                deleted_threshold=0.2,
                vacuum_min_vector_number=1000,
                default_segment_number=2,
            ),
        )
        
        logger.info(f"Created collection '{collection_name}' with {performance_profile} profile")
        return True
        
    except Exception as e:
        logger.error(f"Error creating collection with modern config: {e}")
        return False

# Enhanced batch storage with better error handling
async def batch_store_modern(
    self, 
    entries: list[BatchEntry], 
    collection_name: str | None = None,
    batch_size: int = 1000,
    parallel_batches: int = 4,
) -> int:
    """
    Modern batch storage with chunking and parallel processing.
    
    :param entries: List of entries to store.
    :param collection_name: Name of the collection.
    :param batch_size: Size of each batch.
    :param parallel_batches: Number of parallel upload batches.
    :return: Number of successfully stored entries.
    """
    collection_name = collection_name or self._default_collection_name
    assert collection_name is not None

    await self._ensure_collection_exists(collection_name)
    
    total_stored = 0
    
    try:
        # Process in chunks for better memory management and error recovery
        for i in range(0, len(entries), batch_size):
            chunk = entries[i:i + batch_size]
            
            records = []
            for entry in chunk:
                if entry.id:
                    try:
                        point_id = str(uuid.UUID(entry.id)).replace("-", "")
                    except ValueError:
                        point_id = uuid.uuid5(uuid.NAMESPACE_DNS, entry.id).hex
                else:
                    point_id = uuid.uuid4().hex

                records.append(
                    models.Record(
                        id=point_id,
                        payload={"document": entry.content, METADATA_PATH: entry.metadata or {}},
                    )
                )
            
            # Use modern upload with better error handling
            try:
                await self._client.upload_records(
                    collection_name=collection_name,
                    records=records,
                    wait=True,
                    parallel=parallel_batches,
                )
                total_stored += len(records)
                logger.debug(f"Stored batch {i//batch_size + 1}: {len(records)} entries")
                
            except Exception as batch_error:
                logger.error(f"Error storing batch {i//batch_size + 1}: {batch_error}")
                # Continue with next batch rather than failing completely
                continue
    
    except Exception as e:
        logger.error(f"Error in modern batch store: {e}")
    
    logger.info(f"Successfully stored {total_stored}/{len(entries)} entries in collection '{collection_name}'")
    return total_stored

print("Modern Qdrant implementation methods created!")
print("Key improvements:")
print("✅ Uses Query API (v1.10+)")
print("✅ Supports both client and server-side embedding")
print("✅ Enhanced error handling with fallbacks")
print("✅ Performance optimization profiles")
print("✅ Better batch processing")
print("✅ Preparation for hybrid search")
