"""Structure-aware chunking: one chunk per paragraph, list, table or table row group. No size cap."""
import io
import logging
import re
import threading
from typing import Optional

import pytesseract
from PIL import Image
from docling.datamodel.base_models import DocumentStream
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DocItemLabel, ListItem, SectionHeaderItem, TableItem, TextItem, TitleItem

logger = logging.getLogger(__name__)

_converter = DocumentConverter()
# Docling pipelines are not documented as thread-safe; uploads run in a threadpool
_convert_lock = threading.Lock()


def chunk_document(content: bytes, content_type: Optional[str], file_name: str = "upload") -> list[dict]:
    """Chunks for an uploaded file; [] when nothing can be extracted."""
    content_type = content_type or ""
    try:
        if content_type == "application/pdf":
            with _convert_lock:
                doc = _converter.convert(DocumentStream(name=file_name, stream=io.BytesIO(content))).document
            return chunk_docling(doc)
        if content_type.startswith("image/"):
            return chunk_plain_text(pytesseract.image_to_string(Image.open(io.BytesIO(content))))
        return chunk_plain_text(content.decode("utf-8"))
    except Exception as e:
        logger.warning("Chunking failed for %s (%s): %s", file_name, content_type, e)
        return []


def chunk_plain_text(text: str) -> list[dict]:
    """One chunk per blank-line-separated paragraph."""
    blocks = [{"type": "paragraph", "text": p.strip()} for p in re.split(r"\n\s*\n", text) if p.strip()]
    return _render(_merge_lead_ins(blocks))


def chunk_docling(doc) -> list[dict]:
    return _render(_merge_lead_ins(_docling_blocks(doc)))


# ---------- parsing: Docling document -> blocks ----------

def _page(item) -> Optional[int]:
    return item.prov[0].page_no if item.prov else None


def _docling_blocks(doc) -> list[dict]:
    """Paragraph, list and table blocks in reading order, each tagged with its section path."""
    table_captions = {ref.cref for table in doc.tables for ref in table.captions}
    title: Optional[str] = None
    headings: list[str] = []  # headings[i] is the current level-(i+1) section header
    blocks: list[dict] = []

    for item, _ in doc.iterate_items():
        section = " > ".join(filter(None, [title, *headings])) or None
        last = blocks[-1] if blocks else None

        if isinstance(item, TitleItem):
            title, headings = item.text.strip(), []
        elif isinstance(item, SectionHeaderItem):
            headings = headings[:max(item.level, 1) - 1] + [item.text.strip()]
        elif isinstance(item, TableItem):
            table = _table_block(item, doc, section)
            if table is None:
                continue
            if last and _continues(last, table):
                last["body"].extend(r for r in table["body"] if _texts(r) not in last["header"])
                last["last_page"] = table["page"]
            else:
                blocks.append(table)
        elif isinstance(item, ListItem):
            text = item.text.strip()
            if not text:
                continue
            line = f"{item.marker or '-'} {text}".strip()
            if last and last["type"] == "list" and last["section"] == section:
                last["text"] += "\n" + line
            else:
                blocks.append({"type": "list", "text": line, "page": _page(item), "section": section})
        elif isinstance(item, TextItem):
            text = item.text.strip()
            if not text or item.self_ref in table_captions or item.label in (DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER):
                continue
            blocks.append({"type": "paragraph", "text": text, "page": _page(item), "section": section})
    return blocks


def _texts(row) -> list[str]:
    return [" ".join(cell.text.split()) for cell in row]


def _table_block(item: TableItem, doc, section: Optional[str]) -> Optional[dict]:
    grid = item.data.grid
    if not grid or not item.data.num_cols:
        return None
    # Leading rows Docling marks as column headers; otherwise assume the first row is the header
    n_header = 0
    while n_header < len(grid) and any(cell.column_header for cell in grid[n_header]):
        n_header += 1
    if n_header == 0 and len(grid) > 1:
        n_header = 1
    return {
        "type": "table",
        "caption": item.caption_text(doc).strip() or None,
        "header": [_texts(row) for row in grid[:n_header]],
        "body": grid[n_header:],
        "num_cols": item.data.num_cols,
        "page": _page(item),
        "last_page": _page(item),
        "section": section,
    }


def _continues(prev: dict, table: dict) -> bool:
    """A captionless table on the next page with the same columns is the rest of the previous table."""
    return (
        prev["type"] == "table"
        and table["caption"] is None
        and table["num_cols"] == prev["num_cols"]
        and prev["last_page"] is not None and table["page"] == prev["last_page"] + 1
    )


def _merge_lead_ins(blocks: list[dict]) -> list[dict]:
    """A paragraph ending in ':' introduces the next block in its section, so it joins that block."""
    merged: list[dict] = []
    lead_in: Optional[dict] = None
    for block in blocks:
        if lead_in is not None:
            if lead_in.get("section") == block.get("section"):
                if block["type"] == "table":
                    block["caption"] = " ".join(filter(None, [lead_in["text"], block["caption"]]))
                else:
                    block["text"] = lead_in["text"] + "\n" + block["text"]
            else:
                merged.append(lead_in)
            lead_in = None
        if block["type"] == "paragraph" and block["text"].endswith(":"):
            lead_in = block
        else:
            merged.append(block)
    if lead_in is not None:
        merged.append(lead_in)
    return merged


# ---------- tables: row grouping ----------

def _column_names(header: list[list[str]], num_cols: int) -> list[str]:
    names = []
    for c in range(num_cols):
        parts = []
        for row in header:
            if c < len(row) and row[c] and row[c] not in parts:
                parts.append(row[c])
        names.append(" / ".join(parts) or f"Column {c + 1}")
    return names


def _is_section_row(row, num_cols: int) -> bool:
    return any(cell.row_section for cell in row) or (num_cols > 1 and len({id(cell) for cell in row}) == 1)


def table_groups(header: list[list[str]], body: list, num_cols: int) -> list[dict]:
    """Split table body rows into groups; one group (the whole table) when no grouping pattern exists.

    Checked in order: full-width section rows, merged (row-spanning) cells, then blank fill-down in the
    first column. Each group is {"label": str | None, "column": str | None, "rows": list[list[str]]}.
    """
    names = _column_names(header, num_cols)

    # 1. Full-width section rows start a new group each
    if any(_is_section_row(row, num_cols) for row in body):
        groups = []
        for row in body:
            if _is_section_row(row, num_cols):
                groups.append({"label": " ".join(row[0].text.split()), "column": None, "rows": []})
            elif groups:
                groups[-1]["rows"].append(_texts(row))
            else:
                groups.append({"label": None, "column": None, "rows": [_texts(row)]})
        return [g for g in groups if g["rows"]]

    # 2. Group by the leftmost column that has a merged (row-spanning) cell
    for c in range(num_cols):
        if any(row[c].row_span > 1 for row in body):
            groups, prev = [], None
            for row in body:
                if row[c] is not prev:
                    groups.append({"label": " ".join(row[c].text.split()), "column": names[c], "rows": []})
                    prev = row[c]
                groups[-1]["rows"].append(_texts(row))
            return groups

    # 3. Merged cells extracted as a value followed by blanks; first column only, since blanks
    # elsewhere are usually missing data
    first = [_texts(row)[0] if row else "" for row in body]
    if len(body) > 1 and first[0] and not all(first) and any(first[1:]):
        groups = []
        for row, value in zip(body, first):
            texts = _texts(row)
            if value:
                groups.append({"label": value, "column": names[0], "rows": []})
            else:
                texts[0] = groups[-1]["label"]  # copy the merged value into every row
            groups[-1]["rows"].append(texts)
        return groups

    # 4. No pattern: the whole table is one chunk
    return [{"label": None, "column": None, "rows": [_texts(row) for row in body]}]


def _markdown(names: list[str], rows: list[list[str]]) -> str:
    def line(cells):
        return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"
    return "\n".join([line(names), "|" + "---|" * len(names)] + [line(r) for r in rows])


# ---------- rendering: blocks -> chunks ----------

def _render(blocks: list[dict]) -> list[dict]:
    chunks = []
    table_no = 0
    for block in blocks:
        section_line = f"Section: {block['section']}" if block.get("section") else None
        base = {"type": block["type"], "page": block.get("page"), "section": block.get("section")}
        if block["type"] != "table":
            text = "\n\n".join(filter(None, [section_line, block["text"]]))
            chunks.append({**base, "text": text})
            continue

        table_no += 1
        names = _column_names(block["header"], block["num_cols"])
        groups = table_groups(block["header"], block["body"], block["num_cols"])
        grouped = len(groups) > 1 or groups[0]["label"] is not None
        for group in groups:
            if group["column"]:
                group_line = f"Group: {group['column']} = {group['label']}"
            elif group["label"]:
                group_line = f"Group: {group['label']}"
            else:
                group_line = None
            context = "\n".join(filter(None, [
                section_line,
                f"Table: {block['caption']}" if block.get("caption") else None,
                group_line,
            ]))
            chunk = {
                **base,
                "type": "table_group" if grouped else "table",
                "text": "\n\n".join(filter(None, [context, _markdown(names, group["rows"])])),
                "table_id": f"t{table_no}",
            }
            if group["label"]:
                chunk["group_column"] = group["column"]
                chunk["group_value"] = group["label"]
            chunks.append(chunk)
    return [{k: v for k, v in c.items() if v is not None} for c in chunks]
