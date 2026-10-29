from sentence_transformers import SentenceTransformer

# 1024-dim embeddings, 32k-token context; must match chunks.chunk_embedding in schema.sql.
# Queries go through encode_query (adds the model's instruction prompt), chunks through encode_document.
# Output is last-token pooled and normalized to length 1, so pgvector's L2 distance ranks like cosine.
embedder = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
