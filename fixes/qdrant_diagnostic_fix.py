#!/usr/bin/env python3
"""
Qdrant MCP Server Diagnostic and Fix Tool

This script helps diagnose and fix common issues with the Qdrant MCP server,
particularly vector dimension mismatches that cause silent store failures.

Usage:
    python qdrant_diagnostic_fix.py [command] [options]

Commands:
    diagnose [collection_name]  - Diagnose issues with a specific collection or all collections
    fix [collection_name]       - Fix dimension mismatches by updating embedding models
    recreate [collection_name]  - Recreate collection with correct dimensions
    list-models                 - List available embedding models and their dimensions
    
Examples:
    python qdrant_diagnostic_fix.py diagnose research_papers_attention
    python qdrant_diagnostic_fix.py fix research_papers_attention
    python qdrant_diagnostic_fix.py list-models
"""

import asyncio
import json
import sys
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from qdrant_client import AsyncQdrantClient, models
    from mcp_server_qdrant.settings import QdrantSettings, EmbeddingProviderSettings
    from mcp_server_qdrant.embeddings.factory import create_embedding_provider
    from mcp_server_qdrant.embeddings.types import EmbeddingProviderType
except ImportError as e:
    logger.error(f"Required modules not found: {e}")
    logger.error("Make sure you're running this from the MCP server directory and dependencies are installed")
    sys.exit(1)

class QdrantDiagnostic:
    """Diagnostic tool for Qdrant MCP server issues."""
    
    def __init__(self):
        self.qdrant_settings = QdrantSettings()
        self.embedding_settings = EmbeddingProviderSettings()
        self.client = AsyncQdrantClient(
            location=self.qdrant_settings.url,
            api_key=self.qdrant_settings.api_key,
            path=self.qdrant_settings.local_path
        )
        self.default_embedding_provider = create_embedding_provider(self.embedding_settings)
        
        # Available embedding models with their dimensions
        self.available_models = {
            "sentence-transformers/all-MiniLM-L6-v2": {"dimensions": 384, "provider": "fastembed"},
            "sentence-transformers/all-mpnet-base-v2": {"dimensions": 768, "provider": "fastembed"},
            "BAAI/bge-small-en-v1.5": {"dimensions": 384, "provider": "fastembed"},
            "BAAI/bge-base-en-v1.5": {"dimensions": 768, "provider": "fastembed"},
            "BAAI/bge-large-en-v1.5": {"dimensions": 1024, "provider": "fastembed"},
            "sentence-transformers/all-MiniLM-L12-v2": {"dimensions": 384, "provider": "fastembed"},
            "thenlper/gte-small": {"dimensions": 384, "provider": "fastembed"},
            "thenlper/gte-base": {"dimensions": 768, "provider": "fastembed"},
            "thenlper/gte-large": {"dimensions": 1024, "provider": "fastembed"},
            "intfloat/e5-small-v2": {"dimensions": 384, "provider": "fastembed"},
            "intfloat/e5-base-v2": {"dimensions": 768, "provider": "fastembed"},
            "intfloat/e5-large-v2": {"dimensions": 1024, "provider": "fastembed"},
        }

    async def get_collection_vector_config(self, collection_name: str) -> Dict[str, Any]:
        """Get vector configuration for a collection."""
        try:
            exists = await self.client.collection_exists(collection_name)
            if not exists:
                return {"exists": False}
            
            info = await self.client.get_collection(collection_name)
            config = {"exists": True, "vectors": {}}
            
            if hasattr(info, 'config') and info.config and hasattr(info.config, 'params'):
                if hasattr(info.config.params, 'vectors'):
                    vectors_config = info.config.params.vectors
                    if isinstance(vectors_config, dict):
                        for vector_name, vp in vectors_config.items():
                            config["vectors"][vector_name] = {
                                "size": getattr(vp, 'size', None),
                                "distance": str(getattr(vp, 'distance', None))
                            }
                    elif vectors_config is not None:
                        config["vectors"]["default"] = {
                            "size": getattr(vectors_config, 'size', None),
                            "distance": str(getattr(vectors_config, 'distance', None))
                        }
            
            # Get collection stats
            config.update({
                "points_count": getattr(info, 'points_count', 0),
                "vectors_count": getattr(info, 'vectors_count', 0),
                "status": getattr(info, 'status', 'unknown')
            })
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting collection config for {collection_name}: {e}")
            return {"exists": False, "error": str(e)}

    async def diagnose_collection(self, collection_name: str) -> Dict[str, Any]:
        """Diagnose a specific collection for common issues."""
        logger.info(f"🔍 Diagnosing collection: {collection_name}")
        
        diagnosis = {
            "collection_name": collection_name,
            "status": "unknown",
            "issues": [],
            "recommendations": [],
            "collection_config": {},
            "embedding_provider": {
                "model": self.default_embedding_provider.get_model_name(),
                "vector_size": self.default_embedding_provider.get_vector_size(),
                "vector_name": self.default_embedding_provider.get_vector_name()
            }
        }
        
        # Get collection configuration
        config = await self.get_collection_vector_config(collection_name)
        diagnosis["collection_config"] = config
        
        if not config.get("exists", False):
            diagnosis["status"] = "missing"
            diagnosis["issues"].append("Collection does not exist")
            diagnosis["recommendations"].append("Collection will be created automatically on first use")
            return diagnosis
        
        if "error" in config:
            diagnosis["status"] = "error"
            diagnosis["issues"].append(f"Error accessing collection: {config['error']}")
            return diagnosis
        
        # Check for dimension mismatches
        embedding_size = diagnosis["embedding_provider"]["vector_size"]
        embedding_name = diagnosis["embedding_provider"]["vector_name"]
        
        vector_configs = config.get("vectors", {})
        
        if not vector_configs:
            diagnosis["issues"].append("No vector configuration found")
            diagnosis["status"] = "error"
            return diagnosis
        
        # Check each vector configuration
        dimension_mismatch = False
        name_mismatch = False
        
        for vector_name, vector_config in vector_configs.items():
            collection_size = vector_config.get("size")
            
            if collection_size and collection_size != embedding_size:
                dimension_mismatch = True
                diagnosis["issues"].append(
                    f"Vector dimension mismatch: collection '{vector_name}' expects {collection_size}D, "
                    f"but embedding provider produces {embedding_size}D"
                )
                
                # Find compatible models
                compatible_models = [
                    model for model, info in self.available_models.items()
                    if info["dimensions"] == collection_size
                ]
                
                if compatible_models:
                    diagnosis["recommendations"].append(
                        f"Use one of these {collection_size}D models: {', '.join(compatible_models[:3])}"
                    )
                else:
                    diagnosis["recommendations"].append(
                        f"No available models match {collection_size}D. Consider recreating collection with {embedding_size}D"
                    )
            
            if vector_name != embedding_name:
                name_mismatch = True
                diagnosis["issues"].append(
                    f"Vector name mismatch: collection uses '{vector_name}', "
                    f"embedding provider uses '{embedding_name}'"
                )
        
        # Determine overall status
        if dimension_mismatch:
            diagnosis["status"] = "dimension_mismatch"
            diagnosis["recommendations"].append(
                "This is likely causing store operations to fail silently"
            )
        elif name_mismatch:
            diagnosis["status"] = "name_mismatch"
        else:
            diagnosis["status"] = "healthy"
        
        return diagnosis

    async def diagnose_all_collections(self) -> List[Dict[str, Any]]:
        """Diagnose all collections."""
        logger.info("🔍 Diagnosing all collections...")
        
        try:
            response = await self.client.get_collections()
            collection_names = [collection.name for collection in response.collections]
            
            if not collection_names:
                logger.info("No collections found")
                return []
            
            results = []
            for collection_name in collection_names:
                diagnosis = await self.diagnose_collection(collection_name)
                results.append(diagnosis)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting collections: {e}")
            return []

    def find_model_for_dimensions(self, dimensions: int) -> List[str]:
        """Find embedding models that match the given dimensions."""
        return [
            model for model, info in self.available_models.items()
            if info["dimensions"] == dimensions
        ]

    async def recreate_collection_with_correct_dimensions(
        self, 
        collection_name: str, 
        target_dimensions: int = None
    ) -> bool:
        """Recreate a collection with correct dimensions."""
        logger.warning(f"⚠️  Recreating collection '{collection_name}' - ALL DATA WILL BE LOST!")
        
        # Get current collection info for backup
        config = await self.get_collection_vector_config(collection_name)
        
        if config.get("exists") and config.get("points_count", 0) > 0:
            response = input(
                f"Collection '{collection_name}' contains {config['points_count']} points. "
                f"Are you sure you want to delete it? (type 'yes' to confirm): "
            )
            if response.lower() != 'yes':
                logger.info("Operation cancelled")
                return False
        
        try:
            # Delete existing collection
            if config.get("exists"):
                await self.client.delete_collection(collection_name)
                logger.info(f"Deleted existing collection '{collection_name}'")
            
            # Use target dimensions or default embedding provider dimensions
            vector_size = target_dimensions or self.default_embedding_provider.get_vector_size()
            vector_name = self.default_embedding_provider.get_vector_name()
            
            # Create new collection
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    vector_name: models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
            )
            
            logger.info(f"✅ Created new collection '{collection_name}' with {vector_size}D vectors")
            return True
            
        except Exception as e:
            logger.error(f"Error recreating collection '{collection_name}': {e}")
            return False

    def print_diagnosis_report(self, diagnoses: List[Dict[str, Any]]):
        """Print a formatted diagnosis report."""
        print("\n" + "="*80)
        print("QDRANT MCP SERVER DIAGNOSTIC REPORT")
        print("="*80)
        
        healthy_count = 0
        issues_count = 0
        
        for diagnosis in diagnoses:
            collection_name = diagnosis["collection_name"]
            status = diagnosis["status"]
            issues = diagnosis["issues"]
            recommendations = diagnosis["recommendations"]
            
            print(f"\n📁 Collection: {collection_name}")
            print(f"   Status: {status.upper()}")
            
            if status == "healthy":
                print("   ✅ No issues found")
                healthy_count += 1
            else:
                issues_count += 1
                if issues:
                    print("   ❌ Issues:")
                    for issue in issues:
                        print(f"      • {issue}")
                
                if recommendations:
                    print("   💡 Recommendations:")
                    for rec in recommendations:
                        print(f"      • {rec}")
            
            # Show collection details
            config = diagnosis.get("collection_config", {})
            if config.get("vectors"):
                print("   📊 Vector Configuration:")
                for vector_name, vector_config in config["vectors"].items():
                    size = vector_config.get("size", "unknown")
                    distance = vector_config.get("distance", "unknown")
                    print(f"      • {vector_name}: {size}D, {distance}")
            
            if config.get("points_count") is not None:
                print(f"   📈 Points: {config['points_count']:,}")
        
        print(f"\n📋 SUMMARY:")
        print(f"   Collections scanned: {len(diagnoses)}")
        print(f"   Healthy: {healthy_count}")
        print(f"   With issues: {issues_count}")
        
        if issues_count > 0:
            print(f"\n⚠️  Run with 'fix' command to resolve dimension mismatches")

    def print_available_models(self):
        """Print available embedding models."""
        print("\n" + "="*80)
        print("AVAILABLE EMBEDDING MODELS")
        print("="*80)
        
        # Group by dimensions
        by_dimensions = {}
        for model, info in self.available_models.items():
            dim = info["dimensions"]
            if dim not in by_dimensions:
                by_dimensions[dim] = []
            by_dimensions[dim].append(model)
        
        for dim in sorted(by_dimensions.keys()):
            print(f"\n🎯 {dim}D Models:")
            for model in by_dimensions[dim]:
                print(f"   • {model}")
        
        current_model = self.default_embedding_provider.get_model_name()
        current_dim = self.default_embedding_provider.get_vector_size()
        print(f"\n🔧 Current default model: {current_model} ({current_dim}D)")

async def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    diagnostic = QdrantDiagnostic()
    
    try:
        if command == "diagnose":
            if len(sys.argv) > 2:
                # Diagnose specific collection
                collection_name = sys.argv[2]
                diagnosis = await diagnostic.diagnose_collection(collection_name)
                diagnostic.print_diagnosis_report([diagnosis])
            else:
                # Diagnose all collections
                diagnoses = await diagnostic.diagnose_all_collections()
                diagnostic.print_diagnosis_report(diagnoses)
        
        elif command == "fix":
            if len(sys.argv) < 3:
                print("Usage: python qdrant_diagnostic_fix.py fix <collection_name>")
                sys.exit(1)
            
            collection_name = sys.argv[2]
            diagnosis = await diagnostic.diagnose_collection(collection_name)
            
            if diagnosis["status"] == "dimension_mismatch":
                print(f"\n🔧 Fixing dimension mismatch for collection '{collection_name}'...")
                
                # Get target dimensions from collection
                config = diagnosis["collection_config"]
                vector_configs = config.get("vectors", {})
                
                if vector_configs:
                    target_dim = list(vector_configs.values())[0].get("size")
                    if target_dim:
                        compatible_models = diagnostic.find_model_for_dimensions(target_dim)
                        if compatible_models:
                            print(f"Available {target_dim}D models: {', '.join(compatible_models)}")
                            print("To fix this issue, you can:")
                            print(f"1. Set environment variable EMBEDDING_MODEL to one of: {compatible_models[0]}")
                            print(f"2. Or recreate the collection with current model dimensions")
                            print(f"\nFor option 2, run:")
                            print(f"python {sys.argv[0]} recreate {collection_name}")
                        else:
                            print(f"No compatible models found for {target_dim}D")
                            print("Consider recreating the collection with a different dimension")
            else:
                print(f"Collection '{collection_name}' doesn't have dimension mismatch issues")
        
        elif command == "recreate":
            if len(sys.argv) < 3:
                print("Usage: python qdrant_diagnostic_fix.py recreate <collection_name> [dimensions]")
                sys.exit(1)
            
            collection_name = sys.argv[2]
            target_dimensions = None
            
            if len(sys.argv) > 3:
                try:
                    target_dimensions = int(sys.argv[3])
                except ValueError:
                    print("Invalid dimensions value. Must be an integer.")
                    sys.exit(1)
            
            success = await diagnostic.recreate_collection_with_correct_dimensions(
                collection_name, target_dimensions
            )
            
            if success:
                print(f"✅ Collection '{collection_name}' recreated successfully")
            else:
                print(f"❌ Failed to recreate collection '{collection_name}'")
        
        elif command == "list-models":
            diagnostic.print_available_models()
        
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
