from pathlib import Path
"""
These functions have no UI dependencies so they can be unit tested and reused
independently from the Tkinter layer.
"""

def normalize_pdf_file(file_entry) -> dict:
    """Coerce a stored file entry (str path or dict) into the canonical dict."""
    if isinstance(file_entry, str):
        return {
            'name': file_entry.split('/')[-1],
            'path': file_entry,
            'metadata': ''
        }

    return {
        'name': file_entry.get('name', ''),
        'path': file_entry.get('path', ''),
        'metadata': file_entry.get('metadata', '') or ''
    }


def collect_ingest_files(files: list[dict]) -> list[dict]:
    """Validate metadata and return the files ready to be ingested.

    Metadata is optional, but when present it must be 5-15 characters. Files
    that violate this are collected and reported together via ValueError.
    """
    ingest_files = []
    invalid_files = []

    for file_entry in files:
        normalized = normalize_pdf_file(file_entry)
        metadata = normalized['metadata'].strip()

        if metadata and not 5 <= len(metadata) <= 15:
            invalid_files.append(normalized['name'])
            continue

        if metadata:
            normalized['metadata'] = metadata
        else:
            normalized.pop('metadata', None)

        ingest_files.append(normalized)

    if invalid_files:
        raise ValueError(
            "Metadata must be 5-15 characters for: " + ", ".join(invalid_files)
        )

    return ingest_files


def load_pdfs_from_folder(folder: str) -> list[dict]:
    """Return file entries for every PDF directly inside ``folder``."""
    entries = []
    for pdf_file in Path(folder).glob("*.pdf"):
        fstr = str(pdf_file.as_posix())
        entries.append({
            'name': fstr.split('/')[-1],
            'path': fstr,
            'metadata': ""
        })
    return entries
