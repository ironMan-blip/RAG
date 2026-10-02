CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    file_hash VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_embedding vector(384) -- adjust dimension if needed
);

CREATE TABLE IF NOT EXISTS chats (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES chats(id) ON DELETE CASCADE,
    user_message TEXT NOT NULL,
    bot_reply TEXT NOT NULL,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source (
    uuid VARCHAR(255) PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL
);

INSERT INTO source (uuid, source_name) 
VALUES 
    ('20a26963-d20c-469f-8837-620321d589a6', 'files attached from chat interface'),
    ('79279d88-e2c3-4a36-9da6-3f02dd71796b', 'files directly attached from library')
ON CONFLICT (uuid) DO NOTHING;
