import psycopg2
from core.config import settings

def migrate():
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS file_groups (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS file_group_documents (
            group_id INTEGER REFERENCES file_groups(id) ON DELETE CASCADE,
            document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, document_id)
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("Migration successful")

if __name__ == '__main__':
    migrate()
