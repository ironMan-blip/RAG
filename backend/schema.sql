CREATE TABLE IF NOT EXISTS chunks (
    chunk_id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_embedding vector(384) -- adjust dimension if needed
);
