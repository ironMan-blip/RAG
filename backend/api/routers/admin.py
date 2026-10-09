from fastapi import APIRouter, HTTPException
from core.database import get_db_connection

router = APIRouter()

@router.get("/tables")
def get_tables():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cur.fetchall()]
            return {"tables": tables}

@router.get("/tables/{table_name}")
def get_table_data(table_name: str, limit: int = 100):
    # Basic validation against sql injection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            valid_tables = [row[0] for row in cur.fetchall()]
            
            if table_name not in valid_tables:
                raise HTTPException(status_code=404, detail="Table not found")
                
            cur.execute(f"SELECT * FROM {table_name} LIMIT %s", (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            
            # format data to be json serializable (e.g. handle datetimes, memoryview)
            data = []
            for row in rows:
                row_dict = {}
                for col, val in zip(columns, row):
                    row_dict[col] = str(val) if val is not None else None
                data.append(row_dict)
                
            return {"columns": columns, "data": data}
