#!/usr/bin/env python3
"""List supported fastembed models"""

from fastembed import TextEmbedding

print("Supported FastEmbed models:")
print("=" * 60)

supported_models = TextEmbedding.list_supported_models()
for model in supported_models:
    print(f"Model: {model['model']}")
    print(f"  Dimensions: {model.get('dim', 'Unknown')}")
    print(f"  Description: {model.get('description', 'No description')}")
    print()
