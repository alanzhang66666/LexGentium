"""State_Fingerprint：对规范化持久化状态的稳定摘要。

规则（design.md Data Models）：canonical JSON（稳定 key order、UTF-8、
排除非语义时间戳由各领域 allowlist 自行决定）后取 SHA-256。禁止对任意
对象粗暴移除字段来制造相等。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Iterable, Optional, Sequence


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonical_digest(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def rows_fingerprint(
    conn: sqlite3.Connection,
    table: str,
    *,
    columns: Optional[Sequence[str]] = None,
    order_by: Optional[str] = None,
) -> str:
    """对单表全部行做规范化指纹（供 data-track 前后状态比较）。"""
    if columns is None:
        columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    col_sql = ", ".join(f'"{c}"' for c in columns)
    sql = f"SELECT {col_sql} FROM {table}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    rows = [list(row) for row in conn.execute(sql)]
    return canonical_digest({"table": table, "columns": list(columns), "rows": rows})


def tables_fingerprint(conn: sqlite3.Connection, tables: Iterable[str]) -> str:
    """多表合成指纹。"""
    return canonical_digest({t: rows_fingerprint(conn, t) for t in sorted(tables)})
