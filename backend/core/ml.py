try:
    from sentence_transformers import SentenceTransformer
    # Load model (dimension 384)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
except ImportError:
    embedder = None
    print("sentence_transformers not installed.")

