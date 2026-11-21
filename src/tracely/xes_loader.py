"""XES loading through PM4Py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .event_log import normalize_event_log
from .exceptions import DatasetLoadError


def read_xes_dataframe(path: str | Path) -> pd.DataFrame:
    """Read an XES file using PM4Py and return the normalized DataFrame.

    PM4Py is deliberately imported inside the function so unit tests for the
    analysis rules can run with synthetic DataFrames without installing the
    comparatively heavy desktop/XES dependencies.
    """
    xes_path = Path(path).expanduser().resolve()
    if not xes_path.exists() or not xes_path.is_file():
        raise DatasetLoadError(f"File XES tidak ditemukan: {xes_path}")
    lower_name = xes_path.name.casefold()
    if not (lower_name.endswith(".xes") or lower_name.endswith(".xes.gz")):
        raise DatasetLoadError(
            "Format file tidak sesuai. Pilih file dengan ekstensi .xes atau .xes.gz."
        )

    try:
        import pm4py
    except ImportError as exc:
        raise DatasetLoadError(
            "PM4Py belum terpasang. Jalankan: pip install -r requirements.txt"
        ) from exc

    try:
        # Current PM4Py returns a DataFrame by default. The compatibility branch
        # handles versions that still return a legacy EventLog object.
        try:
            imported: Any = pm4py.read_xes(str(xes_path), return_legacy_log_object=False)
        except TypeError:
            imported = pm4py.read_xes(str(xes_path))

        if isinstance(imported, pd.DataFrame):
            dataframe = imported
        else:
            dataframe = pm4py.convert_to_dataframe(imported)

        return normalize_event_log(dataframe)
    except DatasetLoadError:
        raise
    except Exception as exc:  # PM4Py exposes several parser-specific exception types.
        raise DatasetLoadError(f"Gagal membaca atau memvalidasi file XES: {exc}") from exc
