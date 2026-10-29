"""Run from backend/: python -m unittest tests.test_retrieval (needs the Postgres in DATABASE_URL; nothing is kept)"""
import json
import math
import unittest
import uuid

from psycopg2.extras import Json

from core.database import pool
from services.retrieval_service import _CONTEXT_SQL

DIM = 1024
# Only this test's session, so real documents never compete
SQL = _CONTEXT_SQL.format(scope="d.session_id = %(session_id)s")


def vec(angle: float) -> str:
    """Unit vector at `angle` from the query vector: larger angle, larger distance."""
    return str([math.cos(angle), math.sin(angle)] + [0.0] * (DIM - 2))


@unittest.skipIf(pool is None, "database not available")
class TwoPhaseRetrieval(unittest.TestCase):
    def setUp(self):
        self.conn = pool.getconn()
        self.cur = self.conn.cursor()
        self.session = str(uuid.uuid4())

    def tearDown(self):
        self.conn.rollback()
        self.cur.close()
        pool.putconn(self.conn)

    def add_doc(self, name: str, metadata: dict, chunks: list[tuple[str, float]]):
        self.cur.execute("INSERT INTO documents (filename, session_id, metadata) VALUES (%s, %s, %s) RETURNING id",
                         (f"{self.session}-{name}", self.session, Json(metadata)))
        doc_id = self.cur.fetchone()[0]
        for text, angle in chunks:
            self.cur.execute("INSERT INTO chunks (doc_id, chunk_text, chunk_embedding) VALUES (%s, %s, %s)",
                             (doc_id, text, vec(angle)))

    def search(self, profile: dict) -> list[str]:
        self.cur.execute(SQL, {"query": vec(0), "profile": json.dumps(profile),
                               "session_id": self.session, "filename": None})
        return [text for _, text, _ in self.cur.fetchall()]

    def test_only_documents_matching_the_profile_are_searched(self):
        self.add_doc("math", {"subject": "Mathematics", "grade": "Grade 8"}, [(f"m{i}", 0.01 * i) for i in range(6)])
        self.add_doc("bio", {"subject": "Biology", "grade": "Grade 8"}, [(f"b{i}", 0.5 + 0.01 * i) for i in range(6)])
        # Math chunks are closer, but math's metadata does not match, so it is never searched
        self.assertEqual(self.search({"subject": "biology"}), ["b0", "b1", "b2", "b3", "b4"])

    def test_no_matching_document_falls_back_to_all_documents(self):
        self.add_doc("math", {"subject": "Mathematics"}, [("m0", 0.1)])
        self.add_doc("bio", {"subject": "Biology"}, [("b0", 0.2)])
        self.assertEqual(self.search({"subject": "history"}), ["m0", "b0"])
        self.assertEqual(self.search({}), ["m0", "b0"])

    def test_returns_at_most_five_chunks(self):
        self.add_doc("bio", {"subject": "Biology"}, [(f"b{i}", 0.01 * i) for i in range(12)])
        self.assertEqual(len(self.search({"subject": "biology"})), 5)


if __name__ == "__main__":
    unittest.main()
