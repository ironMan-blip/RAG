"""Run from backend/: python -m unittest discover tests"""
import io
import unittest

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.document_converter import DocumentConverter
from docling_core.types.doc import BoundingBox, DoclingDocument, ProvenanceItem, TableCell, TableData

from core.ml import embedder
from services.chunk_service import embed_chunks
from services.chunker import chunk_docling, chunk_plain_text

_html = DocumentConverter(allowed_formats=[InputFormat.HTML])


def chunks_from_html(body: str) -> list[dict]:
    html = f"<html><body>{body}</body></html>".encode()
    return chunk_docling(_html.convert(DocumentStream(name="t.html", stream=io.BytesIO(html))).document)


HEADER = "<tr><th>Region</th><th>Country</th><th>Sales</th></tr>"


class TableGrouping(unittest.TestCase):
    def test_merged_cells_make_one_chunk_per_group(self):
        chunks = chunks_from_html(f"""<table>{HEADER}
            <tr><td rowspan="2">Asia</td><td>Japan</td><td>10</td></tr><tr><td>India</td><td>20</td></tr>
            <tr><td rowspan="2">Europe</td><td>France</td><td>30</td></tr><tr><td>Spain</td><td>40</td></tr>
        </table>""")
        self.assertEqual([c["group_value"] for c in chunks], ["Asia", "Europe"])
        self.assertTrue(all(c["type"] == "table_group" and c["group_column"] == "Region" for c in chunks))
        self.assertTrue(all("| Region | Country | Sales |" in c["text"] for c in chunks))
        # merged value copied into every row of its group
        self.assertIn("| Europe | Spain | 40 |", chunks[1]["text"])
        self.assertNotIn("Japan", chunks[1]["text"])

    def test_full_width_rows_start_groups(self):
        chunks = chunks_from_html(f"""<table>{HEADER}
            <tr><td colspan="3">North</td></tr><tr><td>A</td><td>X</td><td>1</td></tr>
            <tr><td colspan="3">South</td></tr><tr><td>B</td><td>Y</td><td>2</td></tr><tr><td>C</td><td>Z</td><td>3</td></tr>
        </table>""")
        self.assertEqual([c["group_value"] for c in chunks], ["North", "South"])
        self.assertIn("| C | Z | 3 |", chunks[1]["text"])
        self.assertNotIn("| North", chunks[0]["text"])

    def test_blank_first_column_fills_down(self):
        chunks = chunks_from_html(f"""<table>{HEADER}
            <tr><td>Asia</td><td>Japan</td><td>10</td></tr><tr><td></td><td>India</td><td>20</td></tr>
            <tr><td>Europe</td><td>France</td><td>30</td></tr>
        </table>""")
        self.assertEqual([c["group_value"] for c in chunks], ["Asia", "Europe"])
        self.assertIn("| Asia | India | 20 |", chunks[0]["text"])

    def test_no_pattern_is_one_whole_table(self):
        chunks = chunks_from_html(f"""<table>{HEADER}
            <tr><td>Asia</td><td>Japan</td><td>10</td></tr><tr><td>Europe</td><td>France</td><td>30</td></tr>
        </table>""")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["type"], "table")
        self.assertNotIn("group_value", chunks[0])

    def test_table_split_across_pages_is_joined_before_grouping(self):
        doc = DoclingDocument(name="t")
        box = BoundingBox(l=0, t=0, r=1, b=1)

        def add_table(page, rows):
            cells = [TableCell(text=t, start_row_offset_idx=r, end_row_offset_idx=r + 1, start_col_offset_idx=c,
                               end_col_offset_idx=c + 1, column_header=(r == 0))
                     for r, row in enumerate(rows) for c, t in enumerate(row)]
            doc.add_table(data=TableData(num_rows=len(rows), num_cols=2, table_cells=cells),
                          prov=ProvenanceItem(page_no=page, bbox=box, charspan=(0, 0)))

        add_table(1, [["Name", "Score"], ["Ann", "1"]])
        add_table(2, [["Name", "Score"], ["Bob", "2"]])  # header repeated on the new page
        chunks = chunk_docling(doc)
        self.assertEqual(len(chunks), 1)
        self.assertIn("| Bob | 2 |", chunks[0]["text"])
        self.assertEqual(chunks[0]["text"].count("| Name | Score |"), 1)


class Paragraphs(unittest.TestCase):
    def test_paragraphs_carry_section_and_lead_ins_join_next_block(self):
        chunks = chunks_from_html("""<h1>Report</h1><h2>Costs</h2><p>First paragraph.</p>
            <p>The items are:</p><ul><li>rent</li><li>food</li></ul>""")
        self.assertEqual([c["type"] for c in chunks], ["paragraph", "list"])
        self.assertTrue(all(c["section"] == "Report > Costs" for c in chunks))
        self.assertTrue(chunks[0]["text"].startswith("Section: Report > Costs"))
        self.assertIn("The items are:\n", chunks[1]["text"])
        self.assertIn("rent", chunks[1]["text"])

    def test_plain_text_splits_on_blank_lines(self):
        chunks = chunk_plain_text("One long paragraph\nwrapped.\n\n\nSecond.\n")
        self.assertEqual([c["text"] for c in chunks], ["One long paragraph\nwrapped.", "Second."])


class Embedding(unittest.TestCase):
    def test_chunk_over_the_token_limit_is_embedded_from_its_summary(self):
        limit = embedder.max_seq_length
        embedder.max_seq_length = 4
        try:
            embeddings, sources = embed_chunks(
                [{"text": "a long chunk with far more than four tokens in it"}, {"text": "hi"}],
                ["short summary", None])
        finally:
            embedder.max_seq_length = limit
        self.assertEqual(sources, ["summary", "text"])
        self.assertEqual(len(embeddings[0]), embedder.get_sentence_embedding_dimension())


if __name__ == "__main__":
    unittest.main()
