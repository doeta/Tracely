"""CSV and PDF export for analysis summaries and selected-case evidence."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Iterable

from .models import AnalysisResult, DatasetOverview, FastSlowComparison


def export_results_csv(results: Iterable[AnalysisResult], output_dir: str | Path) -> tuple[Path, Path]:
    """Write analysis_summary.csv and case_evidence.csv.

    Every selected case ID is exported, even when an analysis rule does not
    require a separate event-pair evidence object (for example 11.7A/11.7B).
    """
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / "analysis_summary.csv"
    evidence_path = destination / "case_evidence.csv"

    result_list = list(results)
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "code", "title", "rule", "count", "denominator",
            "percentage", "mean_cycle_time_days", "case_ids", "warnings",
        ])
        writer.writeheader()
        for result in result_list:
            writer.writerow({
                "code": result.code,
                "title": result.title,
                "rule": result.rule,
                "count": result.count,
                "denominator": result.denominator,
                "percentage": result.percentage,
                "mean_cycle_time_days": result.mean_cycle_time_days,
                "case_ids": json.dumps(result.case_ids, ensure_ascii=False),
                "warnings": json.dumps(result.warnings, ensure_ascii=False),
            })

    with evidence_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["analysis_code", "case_id", "evidence_json"])
        writer.writeheader()
        for result in result_list:
            details_by_case: dict[str, list[dict]] = {}
            for item in result.evidence:
                case_id = str(item.get("case_id", ""))
                details_by_case.setdefault(case_id, []).append(item)

            for case_id in result.case_ids:
                writer.writerow({
                    "analysis_code": result.code,
                    "case_id": case_id,
                    "evidence_json": json.dumps(
                        details_by_case.get(case_id, []), ensure_ascii=False, default=str
                    ),
                })

    return summary_path, evidence_path


def build_report_html(
    results: Iterable[AnalysisResult],
    overview: DatasetOverview | None = None,
    source_path: str | Path | None = None,
    fast_slow: FastSlowComparison | None = None,
) -> str:
    """Build a structured HTML report containing dataset parameters, results, and case evidence."""
    result_list = list(results)
    esc = html.escape

    overview_section = ""
    if overview is not None:
        mean_str = (
            f"{overview.mean_cycle_time_days:.4f} hari"
            if overview.mean_cycle_time_days is not None
            else "-"
        )
        overview_section = f"""
        <h2>1. Ringkasan Dataset (Event Log Overview)</h2>
        <table>
            <tr><th>Sumber File XES</th><td>{esc(str(source_path or 'In-Memory Event Log'))}</td></tr>
            <tr><th>Total Unique Cases</th><td>{overview.total_cases:,}</td></tr>
            <tr><th>Total Events</th><td>{overview.total_events:,}</td></tr>
            <tr><th>Unique Activities</th><td>{overview.unique_activities:,}</td></tr>
            <tr><th>Rentang Timestamp (UTC)</th><td>{esc(str(overview.first_timestamp or '-'))} s/d {esc(str(overview.last_timestamp or '-'))}</td></tr>
            <tr><th>Mean Cycle Time</th><td>{esc(mean_str)}</td></tr>
            <tr><th>Atribut Opsional Tersedia</th><td>{esc(', '.join(overview.available_attributes) or '-')}</td></tr>
        </table>
        """

    rows_html = []
    for res in result_list:
        pct_str = "-" if res.percentage is None else f"{res.percentage:.4f}%"
        ct_str = "-" if res.mean_cycle_time_days is None else f"{res.mean_cycle_time_days:.6f}"
        denom_str = "-" if res.denominator is None else f"{res.denominator:,}"
        rows_html.append(
            f"<tr>"
            f"<td><b>{esc(res.code)}</b></td>"
            f"<td>{esc(res.title)}</td>"
            f"<td>{res.count:,}</td>"
            f"<td>{esc(denom_str)}</td>"
            f"<td>{esc(pct_str)}</td>"
            f"<td>{esc(ct_str)}</td>"
            f"<td>{esc(res.rule)}</td>"
            f"</tr>"
        )

    fast_slow_section = ""
    if fast_slow is not None:
        fs_rows = "".join(
            f"<tr><td>{esc(str(m['metric']))}</td><td>{esc(str(m['fast_cases']))}</td><td>{esc(str(m['slow_cases']))}</td></tr>"
            for m in fast_slow.comparison_metrics
        )
        fast_slow_section = f"""
        <h2>3. Perbandingan Fast Cases (&lt; {fast_slow.threshold_days:g} Hari) vs Slow Cases (&ge; {fast_slow.threshold_days:g} Hari)</h2>
        <table>
            <thead>
                <tr><th>Karakteristik</th><th>Fast Cases</th><th>Slow Cases</th></tr>
            </thead>
            <tbody>{fs_rows}</tbody>
        </table>
        """

    evidence_blocks = []
    for res in result_list:
        sample_cases = ", ".join(res.case_ids[:50]) + (" ..." if len(res.case_ids) > 50 else "")
        sample_ev = json.dumps(res.evidence[:10], ensure_ascii=False, indent=2, default=str)
        warnings_html = (
            f"<p><b>Peringatan:</b> {esc('; '.join(res.warnings))}</p>" if res.warnings else ""
        )
        evidence_blocks.append(
            f"<h3>{esc(res.code)} — {esc(res.title)}</h3>"
            f"<p><b>Aturan:</b> {esc(res.rule)}<br/>"
            f"<b>Jumlah Case:</b> {res.count:,} | "
            f"<b>Contoh Case ID (maks 50):</b> {esc(sample_cases or '-')}</p>"
            f"{warnings_html}"
            f"<pre>{esc(sample_ev)}</pre>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #0f172a; }}
h1 {{ font-size: 16pt; color: #1e3a8a; border-bottom: 2px solid #1e3a8a; padding-bottom: 4px; }}
h2 {{ font-size: 12pt; color: #1e293b; margin-top: 14px; }}
h3 {{ font-size: 10.5pt; color: #334155; margin-top: 10px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 6px; margin-bottom: 10px; }}
th, td {{ border: 1px solid #cbd5e1; padding: 5px 7px; text-align: left; font-size: 9pt; }}
th {{ background-color: #f1f5f9; font-weight: bold; }}
pre {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 6px; font-size: 8pt; white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>Laporan Analisis Event Log — BPIC17 Process Analyzer</h1>
{overview_section}
<h2>2. Ringkasan Hasil Analisis</h2>
<table>
    <thead>
        <tr>
            <th>Kode</th><th>Judul</th><th>Jumlah Case</th><th>Denominator</th>
            <th>Persentase</th><th>Mean Cycle Time (hari)</th><th>Aturan</th>
        </tr>
    </thead>
    <tbody>
        {''.join(rows_html)}
    </tbody>
</table>
{fast_slow_section}
<h2>4. Bukti Case &amp; Event (Case Evidence)</h2>
{''.join(evidence_blocks)}
</body>
</html>"""


def export_results_pdf(
    results: Iterable[AnalysisResult],
    output_path: str | Path,
    overview: DatasetOverview | None = None,
    source_path: str | Path | None = None,
    fast_slow: FastSlowComparison | None = None,
) -> Path:
    """Render an automatic PDF analysis report using PySide6 QPdfWriter and QTextDocument."""
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.casefold() != ".pdf":
        destination = destination / "analysis_report.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if QApplication.instance() is None:
        QApplication([])

    html_content = build_report_html(
        results=results,
        overview=overview,
        source_path=source_path,
        fast_slow=fast_slow,
    )

    writer = QPdfWriter(str(destination))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageOrientation(QPageLayout.Portrait)
    writer.setResolution(300)

    document = QTextDocument()
    document.setHtml(html_content)
    document.print_(writer)

    return destination

