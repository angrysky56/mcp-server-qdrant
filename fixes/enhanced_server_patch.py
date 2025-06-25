"""
Patch for mcp_server_enhanced.py to fix dimension mismatch issues
and provide better error reporting.

This patch enhances the qdrant_store and qdrant_store_batch functions
to provide detailed error messages instead of generic failures.
"""

import json
import logging
from typing import Annotated

from mcp import Context
from pydantic import Field

from mcp_server_qdrant.qdrant import BatchEntry, DimensionMismatchError

logger = logging.getLogger(__name__)

class DimensionMismatchError(Exception):
    """Custom exception for dimension mismatches."""
    def __init__(self, expected: int, actual: int, collection: str, embedding_model: str):
        self.expected = expected
        self.actual = actual
        self.collection = collection
        self.embedding_model = embedding_model
        super().__init__(
            f"Vector dimension mismatch in collection '{collection}': "
            f"expected {expected}D vectors, but embedding model '{embedding_model}' produces {actual}D vectors. "
            f"Either use a {expected}D embedding model or recreate the collection with {actual}D configuration."
        )

async def enhanced_qdrant_store(
    self,
    ctx: Context,
    content: Annotated[str, Field(description="Text content to store")],
    collection_name: Annotated[str, Field(description="Collection to store the information in")],
    metadata: Annotated[str | None, Field(description="Optional metadata as JSON string")] = None,
    entry_id: Annotated[str | None, Field(description="Optional custom ID for the entry")] = None,
) -> str:
    """Enhanced store function with better error handling and diagnostics."""
    try:
        await ctx.debug(f"Storing content in collection '{collection_name}'")

        # Parse metadata from JSON string
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                return f"❌ Invalid metadata JSON: {metadata}"

        # Create entry
        batch_entry = BatchEntry(
            content=content,
            metadata=parsed_metadata,
            id=entry_id
        )

        # Get appropriate embedding provider for collection
        embedding_provider = await self.embedding_manager.get_provider_for_collection(collection_name)

        # Get embedding provider info for diagnostics
        model_name = embedding_provider.get_model_name()
        vector_size = embedding_provider.get_vector_size()
        
        await ctx.debug(f"Using embedding model: {model_name} ({vector_size}D)")

        # Check collection compatibility before storing
        try:
            # Get collection info if it exists
            collection_exists = await self.qdrant_connector._client.collection_exists(collection_name)
            if collection_exists:
                info = await self.qdrant_connector._client.get_collection(collection_name)
                
                # Extract expected vector size
                expected_size = None
                if hasattr(info, 'config') and info.config and hasattr(info.config, 'params'):
                    if hasattr(info.config.params, 'vectors'):
                        vectors_config = info.config.params.vectors
                        if isinstance(vectors_config, dict):
                            for vp in vectors_config.values():
                                if hasattr(vp, 'size'):
                                    expected_size = vp.size
                                    break
                        elif vectors_config is not None and hasattr(vectors_config, 'size'):
                            expected_size = vectors_config.size
                
                # Check for dimension mismatch
                if expected_size and expected_size != vector_size:
                    # Find compatible models
                    compatible_models = []
                    model_dimensions = {
                        "sentence-transformers/all-MiniLM-L6-v2": 384,
                        "sentence-transformers/all-mpnet-base-v2": 768,
                        "BAAI/bge-small-en-v1.5": 384,
                        "BAAI/bge-base-en-v1.5": 768,
                        "BAAI/bge-large-en-v1.5": 1024,
                        "thenlper/gte-base": 768,
                        "intfloat/e5-base-v2": 768,
                    }
                    
                    for model, dims in model_dimensions.items():
                        if dims == expected_size:
                            compatible_models.append(model)
                    
                    error_msg = (
                        f"❌ Vector dimension mismatch!\n"
                        f"   Collection '{collection_name}' expects: {expected_size}D vectors\n"
                        f"   Current model '{model_name}' produces: {vector_size}D vectors\n\n"
                        f"💡 Solutions:\n"
                        f"   1. Use a {expected_size}D embedding model"
                    )
                    
                    if compatible_models:
                        error_msg += f" (e.g., {compatible_models[0]})\n"
                        error_msg += f"   2. Available {expected_size}D models: {', '.join(compatible_models[:3])}\n"
                    
                    error_msg += (
                        f"   3. Or recreate collection '{collection_name}' with {vector_size}D configuration\n"
                        f"   4. Run diagnostic tool: python fixes/qdrant_diagnostic_fix.py diagnose {collection_name}"
                    )
                    
                    return error_msg

        except Exception as e:
            await ctx.debug(f"Error checking collection compatibility: {e}")

        # Update connector's embedding provider temporarily
        original_provider = self.qdrant_connector._embedding_provider
        self.qdrant_connector._embedding_provider = embedding_provider

        try:
            stored_count = await self.qdrant_connector.batch_store([batch_entry], collection_name)
            
            if stored_count > 0:
                return f"✅ Successfully stored entry in collection '{collection_name}' using {model_name}"
            else:
                # Provide detailed error information
                return (
                    f"❌ Failed to store entry in collection '{collection_name}'\n"
                    f"   This usually indicates a vector dimension mismatch.\n"
                    f"   Current embedding model: {model_name} ({vector_size}D)\n"
                    f"   Run diagnostic: python fixes/qdrant_diagnostic_fix.py diagnose {collection_name}"
                )
                
        finally:
            # Restore original provider
            self.qdrant_connector._embedding_provider = original_provider

    except DimensionMismatchError as e:
        await ctx.debug(f"Dimension mismatch error: {e}")
        return f"❌ {str(e)}"
    
    except Exception as e:
        await ctx.debug(f"Error storing content: {e}")
        return (
            f"❌ Error storing content: {str(e)}\n"
            f"   Collection: {collection_name}\n"
            f"   Model: {model_name} ({vector_size}D)\n"
            f"   Run diagnostic: python fixes/qdrant_diagnostic_fix.py diagnose {collection_name}"
        )

async def enhanced_qdrant_store_batch(
    self,
    ctx: Context,
    entries: Annotated[list, Field(description="List of entries to store, each with 'content' and optional 'metadata' and 'id'")],
    collection_name: Annotated[str, Field(description="Collection to store entries in")]
) -> str:
    """Enhanced batch store function with better error handling."""
    try:
        await ctx.debug(f"Batch storing {len(entries)} entries in collection '{collection_name}'")

        if not entries:
            return "❌ No entries provided"

        # Parse and validate entries
        batch_entries = []
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict) or 'content' not in entry:
                return f"❌ Invalid entry at index {i}: must be dict with 'content' field"
            
            parsed_metadata = None
            if 'metadata' in entry and entry['metadata']:
                try:
                    if isinstance(entry['metadata'], str):
                        parsed_metadata = json.loads(entry['metadata'])
                    else:
                        parsed_metadata = entry['metadata']
                except json.JSONDecodeError:
                    return f"❌ Invalid metadata JSON in entry {i}"

            batch_entries.append(BatchEntry(
                content=entry['content'],
                metadata=parsed_metadata,
                id=entry.get('id')
            ))

        # Get appropriate embedding provider for collection
        embedding_provider = await self.embedding_manager.get_provider_for_collection(collection_name)
        model_name = embedding_provider.get_model_name()
        vector_size = embedding_provider.get_vector_size()
        
        await ctx.debug(f"Using embedding model: {model_name} ({vector_size}D)")

        # Update connector's embedding provider temporarily
        original_provider = self.qdrant_connector._embedding_provider
        self.qdrant_connector._embedding_provider = embedding_provider

        try:
            stored_count = await self.qdrant_connector.batch_store(batch_entries, collection_name)
            
            if stored_count > 0:
                return f"✅ Successfully stored {stored_count}/{len(entries)} entries in collection '{collection_name}' using {model_name}"
            else:
                return (
                    f"❌ Failed to store entries in collection '{collection_name}'\n"
                    f"   Attempted: {len(entries)} entries\n"
                    f"   Stored: {stored_count}\n"
                    f"   Model: {model_name} ({vector_size}D)\n"
                    f"   This usually indicates a vector dimension mismatch.\n"
                    f"   Run diagnostic: python fixes/qdrant_diagnostic_fix.py diagnose {collection_name}"
                )
                
        finally:
            # Restore original provider
            self.qdrant_connector._embedding_provider = original_provider

    except DimensionMismatchError as e:
        await ctx.debug(f"Dimension mismatch error: {e}")
        return f"❌ {str(e)}"
        
    except Exception as e:
        await ctx.debug(f"Error in batch store: {e}")
        return (
            f"❌ Error in batch store: {str(e)}\n"
            f"   Collection: {collection_name}\n"
            f"   Entries: {len(entries)}\n"
            f"   Run diagnostic: python fixes/qdrant_diagnostic_fix.py diagnose {collection_name}"
        )

# Additional diagnostic tool function
async def enhanced_diagnose_collection(
    self,
    ctx: Context,
    collection_name: Annotated[str, Field(description="Name of the collection to diagnose")]
) -> str:
    """Diagnose collection for common issues."""
    try:
        await ctx.debug(f"Diagnosing collection '{collection_name}'")
        
        # Check if collection exists
        exists = await self.qdrant_connector._client.collection_exists(collection_name)
        if not exists:
            return f"ℹ️  Collection '{collection_name}' does not exist (will be created on first use)"
        
        # Get collection info
        info = await self.qdrant_connector._client.get_collection(collection_name)
        
        # Get current embedding provider info
        embedding_provider = await self.embedding_manager.get_provider_for_collection(collection_name)
        current_model = embedding_provider.get_model_name()
        current_size = embedding_provider.get_vector_size()
        current_vector_name = embedding_provider.get_vector_name()
        
        # Extract collection vector config
        collection_vectors = {}
        if hasattr(info, 'config') and info.config and hasattr(info.config, 'params'):
            if hasattr(info.config.params, 'vectors'):
                vectors_config = info.config.params.vectors
                if isinstance(vectors_config, dict):
                    for vector_name, vp in vectors_config.items():
                        collection_vectors[vector_name] = {
                            "size": getattr(vp, 'size', None),
                            "distance": str(getattr(vp, 'distance', None))
                        }
                elif vectors_config is not None:
                    collection_vectors["default"] = {
                        "size": getattr(vectors_config, 'size', None),
                        "distance": str(getattr(vectors_config, 'distance', None))
                    }
        
        # Build diagnosis report
        report = [
            f"🔍 Collection Diagnosis: {collection_name}",
            f"",
            f"📊 Collection Stats:",
            f"   Points: {getattr(info, 'points_count', 0):,}",
            f"   Vectors: {getattr(info, 'vectors_count', 0):,}",
            f"   Status: {getattr(info, 'status', 'unknown')}",
            f"",
            f"🎯 Current Embedding Provider:",
            f"   Model: {current_model}",
            f"   Vector Size: {current_size}D",
            f"   Vector Name: {current_vector_name}",
            f"",
            f"⚙️  Collection Vector Configuration:",
        ]
        
        issues = []
        recommendations = []
        
        for vector_name, vector_config in collection_vectors.items():
            size = vector_config.get("size", "unknown")
            distance = vector_config.get("distance", "unknown")
            report.append(f"   {vector_name}: {size}D, {distance}")
            
            # Check for dimension mismatch
            if isinstance(size, int) and size != current_size:
                issues.append(
                    f"Dimension mismatch: collection expects {size}D, model produces {current_size}D"
                )
                
                # Suggest compatible models
                compatible_models = {
                    384: ["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5"],
                    768: ["sentence-transformers/all-mpnet-base-v2", "BAAI/bge-base-en-v1.5", "thenlper/gte-base"],
                    1024: ["BAAI/bge-large-en-v1.5", "thenlper/gte-large"]
                }
                
                if size in compatible_models:
                    recommendations.append(f"Use a {size}D model like: {compatible_models[size][0]}")
                
                recommendations.append(f"Or recreate collection with {current_size}D: python fixes/qdrant_diagnostic_fix.py recreate {collection_name}")
            
            # Check vector name mismatch
            if vector_name != current_vector_name:
                issues.append(f"Vector name mismatch: collection uses '{vector_name}', provider uses '{current_vector_name}'")
        
        if issues:
            report.extend([
                f"",
                f"❌ Issues Found:",
            ])
            for issue in issues:
                report.append(f"   • {issue}")
        
        if recommendations:
            report.extend([
                f"",
                f"💡 Recommendations:",
            ])
            for rec in recommendations:
                report.append(f"   • {rec}")
        
        if not issues:
            report.extend([
                f"",
                f"✅ No issues found - collection is compatible with current embedding provider"
            ])
        
        return "\n".join(report)
        
    except Exception as e:
        await ctx.debug(f"Error diagnosing collection: {e}")
        return f"❌ Error diagnosing collection '{collection_name}': {str(e)}"

# Instructions for applying the patch:
PATCH_INSTRUCTIONS = """
To apply this patch to your MCP server:

1. Backup your current mcp_server_enhanced.py:
   cp src/mcp_server_qdrant/mcp_server_enhanced.py src/mcp_server_qdrant/mcp_server_enhanced.py.backup

2. Replace the qdrant_store function (around line 148) with enhanced_qdrant_store
3. Replace the qdrant_store_batch function (around line 477) with enhanced_qdrant_store_batch  
4. Add the enhanced_diagnose_collection function as a new tool

5. Or use the diagnostic script directly:
   python fixes/qdrant_diagnostic_fix.py diagnose [collection_name]
"""

print(PATCH_INSTRUCTIONS)
