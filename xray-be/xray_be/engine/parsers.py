import csv
import io
import os
from typing import List, Dict, Tuple, Any


def read_table_file(file_obj, filename: str) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses CSV or Excel file.
    Returns:
      columns: list of unique normalized header names
      sample_rows: up to 5 dicts for preview
      all_rows: list of all row dicts
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext in ['.xlsx', '.xls']:
        import pandas as pd
        excel_file = pd.ExcelFile(file_obj)
        # Select first sheet or best sheet
        df = excel_file.parse(excel_file.sheet_names[0])
        # Drop rows where all elements are NaN
        df = df.dropna(how='all')
        # Columns
        raw_cols = [str(c).strip() for c in df.columns]
        # Disambiguate duplicate columns
        cols = []
        counts = {}
        for c in raw_cols:
            if c in counts:
                counts[c] += 1
                cols.append(f"{c} ({counts[c]})")
            else:
                counts[c] = 1
                cols.append(c)
        df.columns = cols
        # Convert df to list of dicts, converting timestamps/floats to strings
        records = df.to_dict(orient='records')
        cleaned_records = []
        for r in records:
            row_dict = {}
            for k, v in r.items():
                if v is None or (isinstance(v, float) and str(v) == 'nan'):
                    row_dict[k] = ''
                else:
                    row_dict[k] = str(v)
            cleaned_records.append(row_dict)

        sample = cleaned_records[:5]
        return cols, sample, cleaned_records

    # CSV Parsing
    raw_bytes = file_obj.read()
    if isinstance(raw_bytes, str):
        content = raw_bytes
    else:
        # Detect encoding
        encodings = ['utf-8-sig', 'utf-8', 'cp1251']
        content = None
        for enc in encodings:
            try:
                content = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            raise ValueError("bad_encoding")

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("not_a_table")

    header_line = lines[0]
    delimiter = ';' if header_line.count(';') >= header_line.count(',') else ','

    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise ValueError("not_a_table")

    raw_headers = [h.strip() for h in rows[0]]
    cols = []
    counts = {}
    for h in raw_headers:
        if h in counts:
            counts[h] += 1
            cols.append(f"{h} ({counts[h]})")
        else:
            counts[h] = 1
            cols.append(h)

    all_records = []
    for r in rows[1:]:
        if not any(cell.strip() for cell in r):
            continue
        row_dict = {}
        for i, col_name in enumerate(cols):
            row_dict[col_name] = r[i].strip() if i < len(r) else ''
        all_records.append(row_dict)

    return cols, all_records[:5], all_records
