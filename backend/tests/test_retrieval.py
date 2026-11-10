"""Run from backend/: python -m unittest tests.test_retrieval (needs the Postgres in DATABASE_URL; nothing is kept)"""
import json
import math
import unittest
import uuid

from psycopg2.extras import Json

from core.database import pool
from services.retrieval_service import _CONTEXT_SQL, MIN_CHUNKS, MIN_SIMILARITY

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

    def add_doc(self, name: str, metadata: dict, chunks: list[tuple[str, float]], country: str = None):
        self.cur.execute("INSERT INTO documents (filename, session_id, metadata, country) VALUES (%s, %s, %s, %s)"
                         " RETURNING id", (f"{self.session}-{name}", self.session, Json(metadata), country))
        doc_id = self.cur.fetchone()[0]
        for text, angle in chunks:
            self.cur.execute("INSERT INTO chunks (doc_id, chunk_text, chunk_embedding) VALUES (%s, %s, %s)",
                             (doc_id, text, vec(angle)))

    def search(self, profile: dict) -> list[str]:
        self.cur.execute(SQL, {"query": vec(0), "profile": json.dumps(profile),
                               "session_id": self.session, "filename": None, "min_similarity": MIN_SIMILARITY,
                               "min_chunks": MIN_CHUNKS})
        return [text for _, text, _ in self.cur.fetchall()]

    def test_only_documents_matching_the_profile_are_searched(self):
        self.add_doc("math", {"subject": "Mathematics", "grade": "Grade 8"}, [(f"m{i}", 0.01 * i) for i in range(6)])
        self.add_doc("bio", {"subject": "Biology", "grade": "Grade 8"}, [(f"b{i}", 0.5 + 0.01 * i) for i in range(6)])
        # Math chunks are closer, but math's metadata does not match, so it is never searched
        self.assertEqual(self.search({"subject": "biology"}), ["b0", "b1", "b2", "b3", "b4", "b5"])

    def test_no_matching_document_falls_back_to_all_documents(self):
        self.add_doc("math", {"subject": "Mathematics"}, [("m0", 0.1)])
        self.add_doc("bio", {"subject": "Biology"}, [("b0", 0.2)])
        self.assertEqual(self.search({"subject": "history"}), ["m0", "b0"])
        self.assertEqual(self.search({}), ["m0", "b0"])

    def test_returns_every_chunk_at_or_above_the_similarity_cutoff(self):
        # cos(0.7) ~ 0.76 passes, cos(0.9) ~ 0.62 fails
        self.add_doc("bio", {"subject": "Biology"}, [(f"b{i}", 0.01 * i) for i in range(12)] + [("near", 0.7), ("far", 0.9)])
        self.assertEqual(self.search({"subject": "biology"}), [f"b{i}" for i in range(12)] + ["near"])

    def test_most_similar_chunks_pass_even_below_the_cutoff(self):
        # All below 0.7 (cos(1.0) ~ 0.54), so only the MIN_CHUNKS closest come back
        self.add_doc("bio", {"subject": "Biology"}, [(f"b{i}", 1.0 + 0.01 * i) for i in range(5)])
        self.assertEqual(self.search({"subject": "biology"}), ["b0", "b1", "b2"])

    def test_only_the_most_common_country_is_kept_with_na_and_untagged(self):
        bio = {"subject": "Biology"}
        self.add_doc("in1", bio, [("in1", 0.3)], "India")
        self.add_doc("bd", bio, [("bd", 0.1)], "Bangladesh")
        self.add_doc("na", bio, [("na", 0.2)], "Global")
        self.add_doc("untagged", bio, [("untagged", 0.5)])
        self.add_doc("in2", bio, [("in2", 0.6)], "India")
        # India 2 vs Bangladesh 1: Bangladesh's chunk is dropped even though it is the closest
        self.assertEqual(self.search({"subject": "biology"}), ["na", "in1", "untagged", "in2"])

    def test_country_tie_goes_to_the_best_ranked_document(self):
        self.add_doc("bd", {"subject": "Biology"}, [("bd", 0.1)], "Bangladesh")
        self.add_doc("in", {"subject": "Biology", "grade": "Grade 8"}, [("in", 0.2)], "India")
        self.assertEqual(self.search({"subject": "biology", "grade": "8"}), ["in"])

    def test_country_is_counted_only_within_the_top_10(self):
        # 3 Bangladesh documents rank 11th-13th, so India's 2 in the top 10 still win
        for i in range(8):
            self.add_doc(f"na{i}", {"subject": "Biology", "grade": "Grade 8"}, [(f"na{i}", 0.2)], "Global")
        self.add_doc("in1", {"subject": "Biology", "grade": "Grade 8"}, [("in1", 0.3)], "India")
        self.add_doc("in2", {"subject": "Biology", "grade": "Grade 8"}, [("in2", 0.3)], "India")
        for i in range(3):
            self.add_doc(f"bd{i}", {"subject": "Biology"}, [(f"bd{i}", 0.1)], "Bangladesh")
        self.assertEqual(sorted(self.search({"subject": "biology", "grade": "8"})),
                         sorted([f"na{i}" for i in range(8)] + ["in1", "in2"]))

    def test_fallback_documents_follow_the_country_rule(self):
        self.add_doc("in1", {}, [("in1", 0.1)], "India")
        self.add_doc("in2", {}, [("in2", 0.2)], "India")
        self.add_doc("bd", {}, [("bd", 0.3)], "Bangladesh")
        self.add_doc("na", {}, [("na", 0.4)], "Global")
        self.assertEqual(self.search({}), ["in1", "in2", "na"])


if __name__ == "__main__":
    unittest.main()
