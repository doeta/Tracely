"""Normalize PM4Py event-log data into a predictable DataFrame schema."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .exceptions import DatasetValidationError

# Canonical internal names. XES/PM4Py names are kept as accepted aliases.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "case_id": ("case:concept:name", "case_id", "case id", "case"),
    "activity": ("concept:name", "activity", "activity_name", "activity name"),
    "timestamp": ("time:timestamp", "timestamp", "event_timestamp", "event time"),
    "lifecycle": ("lifecycle:transition", "lifecycle", "transition"),
    "resource": ("org:resource", "resource", "employee", "user"),
}
REQUIRED_COLUMNS = ("case_id", "activity", "timestamp")


def _find_column(columns: Iterable[object], aliases: tuple[str, ...]) -> object | None:
    lookup = {str(column).strip().casefold(): column for column in columns}
    for alias in aliases:
        match = lookup.get(alias.casefold())
        if match is not None:
            return match
    return None


def normalize_event_log(data: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized, chronologically ordered event log.

    Required data quality policy:
    - case ID, activity, and timestamp columns must exist;
    - rows missing any required value are rejected instead of silently dropped;
    - timestamps are normalized to UTC;
    - timestamp ties preserve the input/trace order using ``source_order``.

    Optional lifecycle and resource attributes are retained when present. Missing
    resource values remain missing and are never treated as a shared resource.
    """
    if not isinstance(data, pd.DataFrame):
        raise DatasetValidationError("Data event log harus berupa pandas DataFrame.")
    if data.empty:
        raise DatasetValidationError("Event log kosong; tidak ada event untuk dianalisis.")

    # Do not copy the complete PM4Py DataFrame up front; BPIC17 is a large log.
    # Only canonical columns are materialized below.
    source = data
    mapping: dict[str, object] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        original = _find_column(source.columns, aliases)
        if original is not None:
            mapping[canonical] = original

    missing_columns = [name for name in REQUIRED_COLUMNS if name not in mapping]
    if missing_columns:
        raise DatasetValidationError(
            "Kolom wajib tidak ditemukan: " + ", ".join(missing_columns)
            + ". Kolom XES yang diharapkan: case:concept:name, concept:name, time:timestamp."
        )

    normalized = pd.DataFrame(index=source.index)
    for canonical, original in mapping.items():
        normalized[canonical] = source[original]

    # Preserve original row order for deterministic ordering when timestamps tie.
    normalized["source_order"] = range(len(normalized))

    for column in ("case_id", "activity"):
        normalized[column] = normalized[column].astype("string").str.strip()

    normalized["timestamp"] = pd.to_datetime(
        normalized["timestamp"], errors="coerce", utc=True
    )

    invalid_counts = {
        "case_id": int((normalized["case_id"].isna() | normalized["case_id"].eq("")).sum()),
        "activity": int((normalized["activity"].isna() | normalized["activity"].eq("")).sum()),
        "timestamp": int(normalized["timestamp"].isna().sum()),
    }

    invalid_summary = [f"{column}: {count} baris" for column, count in invalid_counts.items() if count]
    if invalid_summary:
        raise DatasetValidationError(
            "Terdapat nilai wajib yang kosong/tidak valid (" + "; ".join(invalid_summary)
            + "). Data tidak dibuang otomatis agar hasil analisis tidak berubah diam-diam."
        )

    if "lifecycle" in normalized.columns:
        normalized["lifecycle"] = normalized["lifecycle"].astype("string").str.strip()
        normalized.loc[normalized["lifecycle"].eq(""), "lifecycle"] = pd.NA
    else:
        normalized["lifecycle"] = pd.NA

    if "resource" in normalized.columns:
        normalized["resource"] = normalized["resource"].astype("string").str.strip()
        normalized.loc[normalized["resource"].eq(""), "resource"] = pd.NA
    else:
        normalized["resource"] = pd.NA

    # Stable ordering: case ID, timestamp, then original order for timestamp ties.
    normalized = normalized.sort_values(
        ["case_id", "timestamp", "source_order"], kind="mergesort"
    ).reset_index(drop=True)
    # Retain which optional fields actually existed in the source file. This
    # distinguishes an absent attribute from a present-but-empty attribute.
    normalized.attrs["available_attributes"] = sorted(mapping.keys())
    normalized.attrs["source_columns"] = [str(column) for column in source.columns]

    return normalized
