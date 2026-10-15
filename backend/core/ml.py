from sentence_transformers import SentenceTransformer

# 384-dim embeddings; must match chunks.chunk_embedding in schema.sql
embedder = SentenceTransformer("all-MiniLM-L6-v2")
