import logging
from mem0 import Memory
from qdrant_client import QdrantClient
from qdrant_client.http import models

def ensure_qdrant_collection(collection_name="mem0_default", vector_size=768):
    """Ensures a Qdrant collection exists with the correct vector dimensions."""
    client = QdrantClient(host="qdrant", port=6333)
    
    # Check if collection exists
    try:
        collection_info = client.get_collection(collection_name)
        existing_vector_size = collection_info.config.params.vectors.size
        
        if existing_vector_size != vector_size:
            logging.info(f"Collection exists but with wrong dimensions: {existing_vector_size}. Recreating...")
            client.delete_collection(collection_name)
            create_collection = True
        else:
            create_collection = False
    except Exception:
        create_collection = True
    
    # Create collection if needed
    if create_collection:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE
            )
        )
        logging.info(f"Created Qdrant collection '{collection_name}' with {vector_size} dimensions")

def initialize_mem0():
    """Initialize the Mem0 memory system"""
    try:
        # Create Qdrant collection with correct dimensions
        ensure_qdrant_collection(collection_name="mem0_default", vector_size=768)
        
        # Initialize Mem0 with explicit configuration using Google's embedding model
        mem0_config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": "qdrant",
                    "port": 6333,
                    "collection_name": "mem0_default"
                }
            },
            "llm": {
                "provider": "gemini",
                "config": {
                    "model": "gemini-2.0-flash",
                    "temperature": 0.2,
                    "max_tokens": 1500,
                }
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": "models/text-embedding-004",  # Google's embedding model
                }
            }
        }
        
        # Create a new Mem0 instance with the configuration
        mem0_instance = Memory.from_config(mem0_config)
        logging.info("Mem0 initialized successfully.")
        return mem0_instance
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"Error initializing Mem0: {e}")
        return None
