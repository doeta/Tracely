"""Case-level analyses required by the BPIC17 assignment."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .exceptions import AnalysisPrerequisiteError, DatasetValidationError
from .models import AnalysisResult, DatasetOverview, FastSlowComparison

ACCEPTED = "O_Accepted"
REFUSED = "O_Refused"
CANCELLED = "O_Cancelled"
FRAUD_ACTIVITY = "W_Assess Potential Fraud"


def _require_normalized(data: pd.DataFrame) -> pd.DataFrame:
    required = {"case_id", "activity", "timestamp", "source_order"}
    missing = required.difference(data.columns)
    if missing:
        raise DatasetValidationError(
            "DataFrame belum dinormalisasi. Kolom yang hilang: " + ", ".join(sorted(missing))
        )
    if data.empty:
        raise DatasetValidationError("Tidak ada event pada dataset aktif.")
    return data


def cycle_time_by_case(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate each case duration as last timestamp minus first timestamp."""
    frame = _require_normalized(data)
    grouped = frame.groupby("case_id", sort=False)["timestamp"].agg(
        start_time="min", end_time="max", event_count="count"
    )
    grouped["cycle_time"] = grouped["end_time"] - grouped["start_time"]
    grouped["cycle_time_days"] = grouped["cycle_time"].dt.total_seconds() / 86400.0
    grouped["event_count"] = grouped["event_count"].astype(int)
    return grouped.reset_index()


def _activity_mask(series: pd.Series, activity: str) -> pd.Series:
    return series.astype("string").str.strip().str.casefold().eq(activity.strip().casefold())


def _case_ids_with_activity(data: pd.DataFrame, activity: str) -> list[str]:
    selected = data.loc[_activity_mask(data["activity"], activity), "case_id"].drop_duplicates()
    return selected.astype(str).tolist()


def _activity_membership_evidence(
    data: pd.DataFrame,
    durations: pd.DataFrame,
    activity: str,
    case_ids: list[str],
) -> list[dict[str, Any]]:
    if not case_ids:
        return []
    duration_map = durations.set_index(durations["case_id"].astype(str))["cycle_time_days"].to_dict()
    matching = data.loc[_activity_mask(data["activity"], activity)]
    grouped = matching.groupby("case_id", sort=False)
    evidence: list[dict[str, Any]] = []
    for case_id, group in grouped:
        case_id_str = str(case_id)
        evidence.append({
            "case_id": case_id_str,
            "activity": str(group["activity"].iloc[0]),
            "occurrence_count": int(len(group)),
            "first_occurrence_timestamp": group["timestamp"].iloc[0].isoformat(),
            "last_occurrence_timestamp": group["timestamp"].iloc[-1].isoformat(),
            "cycle_time_days": float(duration_map[case_id_str]),
        })
    return evidence


def _mean_cycle_time_from_table(
    durations: pd.DataFrame,
    case_ids: list[str],
) -> float | None:
    if not case_ids:
        return None
    selected = durations.loc[
        durations["case_id"].astype(str).isin(case_ids), "cycle_time_days"
    ]
    if selected.empty:
        return None
    return float(selected.mean())


def analyze_exercise_117(
    data: pd.DataFrame,
    accepted_activity: str = ACCEPTED,
    refused_activity: str = REFUSED,
    cancelled_activity: str = CANCELLED,
) -> dict[str, AnalysisResult]:
    """Calculate Process Outcomes (Exercises 11.7 A–E) from the active event log.

    Defaults to BPIC17 outcome activities (O_Accepted, O_Refused, O_Cancelled),
    but accepts any user-selected outcome activities for general XES event logs.
    """
    frame = _require_normalized(data)
    acc_act = accepted_activity.strip() or ACCEPTED
    ref_act = refused_activity.strip() or REFUSED
    can_act = cancelled_activity.strip() or CANCELLED

    durations = cycle_time_by_case(frame)
    all_cases = durations["case_id"].astype(str).tolist()
    total_cases = len(all_cases)
    duration_map = durations.set_index(durations["case_id"].astype(str))["cycle_time_days"].to_dict()

    result_a = AnalysisResult(
        code="11.7A",
        title="Jumlah keseluruhan case",
        rule="Menghitung setiap case ID unik satu kali pada keseluruhan event log.",
        count=total_cases,
        case_ids=all_cases,
        denominator=total_cases,
    )

    result_b = AnalysisResult(
        code="11.7B",
        title="Rata-rata cycle time seluruh case",
        rule="Cycle time setiap case = timestamp event terakhir − timestamp event pertama; mean dihitung antar-case.",
        count=total_cases,
        case_ids=all_cases,
        denominator=total_cases,
        mean_cycle_time_days=float(durations["cycle_time_days"].mean()) if total_cases else None,
    )

    accepted_cases = _case_ids_with_activity(frame, acc_act)
    result_c = AnalysisResult(
        code="11.7C",
        title=f"Successful cases ({acc_act}) dan rata-rata cycle time",
        rule=f"Case dipilih jika mengandung minimal satu event {acc_act}; case dihitung satu kali.",
        count=len(accepted_cases),
        case_ids=accepted_cases,
        denominator=total_cases,
        percentage=(len(accepted_cases) / total_cases * 100.0) if total_cases else 0.0,
        mean_cycle_time_days=_mean_cycle_time_from_table(durations, accepted_cases),
        evidence=_activity_membership_evidence(frame, durations, acc_act, accepted_cases),
    )

    refused_cases = _case_ids_with_activity(frame, ref_act)
    result_d = AnalysisResult(
        code="11.7D",
        title=f"Unsuccessful cases ({ref_act}) dan rata-rata cycle time",
        rule=f"Case dipilih jika mengandung minimal satu event {ref_act}; case dihitung satu kali dan dapat overlap dengan 11.7C.",
        count=len(refused_cases),
        case_ids=refused_cases,
        denominator=total_cases,
        percentage=(len(refused_cases) / total_cases * 100.0) if total_cases else 0.0,
        mean_cycle_time_days=_mean_cycle_time_from_table(durations, refused_cases),
        evidence=_activity_membership_evidence(frame, durations, ref_act, refused_cases),
    )

    # The event considered last is the last row after stable timestamp sorting.
    last_events = frame.groupby("case_id", sort=False, as_index=False).tail(1)
    last_cancelled_mask = _activity_mask(last_events["activity"], can_act)
    cancelled_cases = last_events.loc[last_cancelled_mask, "case_id"].astype(str).tolist()
    result_e = AnalysisResult(
        code="11.7E",
        title=f"Canceled cases (final {can_act}) dan rata-rata cycle time",
        rule=f"Case dipilih hanya jika event TERAKHIR dalam trace adalah {can_act}.",
        count=len(cancelled_cases),
        case_ids=cancelled_cases,
        denominator=total_cases,
        percentage=(len(cancelled_cases) / total_cases * 100.0) if total_cases else 0.0,
        mean_cycle_time_days=_mean_cycle_time_from_table(durations, cancelled_cases),
        evidence=[
            {
                "case_id": str(row.case_id),
                "last_activity": str(row.activity),
                "last_timestamp": row.timestamp.isoformat(),
                "cycle_time_days": float(duration_map[str(row.case_id)]),
            }
            for row in last_events.loc[last_cancelled_mask].itertuples()
        ],
    )

    return {result.code: result for result in (result_a, result_b, result_c, result_d, result_e)}


def _has_attribute(frame: pd.DataFrame, attr_name: str) -> bool:
    available_attributes = frame.attrs.get("available_attributes")
    if available_attributes is not None:
        return attr_name in available_attributes
    return attr_name in frame.columns and bool(frame[attr_name].notna().any())


def _complete_occurrences(
    data: pd.DataFrame,
    activity: str,
    target_lifecycle: str = "complete",
) -> pd.DataFrame:
    frame = _require_normalized(data)
    lc_goal = target_lifecycle.strip().casefold() or "complete"
    if not _has_attribute(frame, "lifecycle"):
        raise AnalysisPrerequisiteError(
            "Atribut lifecycle:transition tidak tersedia untuk aktivitas target. "
            "Analisis complete-only tidak boleh menebak status event."
        )

    target_events = frame.loc[_activity_mask(frame["activity"], activity)].copy()
    if target_events.empty:
        return target_events

    cleaned_lifecycle = target_events["lifecycle"].astype("string").str.strip()
    missing_mask = cleaned_lifecycle.isna() | cleaned_lifecycle.eq("")
    if bool(missing_mask.all()):
        raise AnalysisPrerequisiteError(
            "Atribut lifecycle:transition tidak tersedia untuk aktivitas target. "
            "Analisis complete-only tidak boleh menebak status event."
        )

    missing_lifecycle = int(missing_mask.sum())
    if missing_lifecycle:
        raise AnalysisPrerequisiteError(
            f"Ada {missing_lifecycle} event {activity} tanpa lifecycle:transition. "
            "Lengkapi/validasi atribut tersebut sebelum menghitung occurrence complete agar hasil tidak bias."
        )

    lifecycle = cleaned_lifecycle.str.casefold()
    return target_events.loc[lifecycle.eq(lc_goal)].copy()


def analyze_exercise_1115(
    data: pd.DataFrame,
    target_activity: str = FRAUD_ACTIVITY,
    min_occurrences: int = 2,
    target_lifecycle: str = "complete",
) -> AnalysisResult:
    """Find cases with at least `min_occurrences` lifecycle-matching occurrences of `target_activity`."""
    act_name = target_activity.strip() or FRAUD_ACTIVITY
    lc_name = target_lifecycle.strip() or "complete"
    min_occ = max(1, int(min_occurrences))
    occurrences = _complete_occurrences(data, act_name, target_lifecycle=lc_name)
    counts = occurrences.groupby("case_id", sort=False).size()
    selected = counts.loc[counts >= min_occ]
    case_ids = selected.index.astype(str).tolist()
    denom = int(data["case_id"].nunique())

    evidence: list[dict[str, Any]] = []
    qualifying_groups = occurrences.loc[
        occurrences["case_id"].isin(selected.index)
    ].groupby("case_id", sort=False)
    for case_id, case_events in qualifying_groups:
        evidence.append({
            "case_id": str(case_id),
            "complete_occurrence_count": int(len(case_events)),
            "events": [
                {
                    "timestamp": row.timestamp.isoformat(),
                    "activity": str(row.activity),
                    "lifecycle": str(row.lifecycle),
                    "resource": None if pd.isna(row.resource) else str(row.resource),
                    "source_order": int(row.source_order),
                }
                for row in case_events.itertuples()
            ],
        })

    return AnalysisResult(
        code="11.15",
        title=f"Case dengan {act_name} ({lc_name}) minimal {min_occ} kali",
        rule=f"Dalam satu case, hitung occurrence {act_name} hanya ketika lifecycle:transition = {lc_name}; case lolos jika total occurrence >= {min_occ}.",
        count=len(case_ids),
        case_ids=case_ids,
        denominator=denom,
        percentage=(len(case_ids) / denom * 100.0) if denom else 0.0,
        evidence=evidence,
    )


def analyze_exercise_1118(
    data: pd.DataFrame,
    target_activity: str = FRAUD_ACTIVITY,
    min_occurrences: int = 2,
    target_lifecycle: str = "complete",
) -> AnalysisResult:
    """Find cases with >= `min_occurrences` target activity completions by the same known resource."""
    frame = _require_normalized(data)
    act_name = target_activity.strip() or FRAUD_ACTIVITY
    lc_name = target_lifecycle.strip() or "complete"
    min_occ = max(2, int(min_occurrences))
    occurrences = _complete_occurrences(frame, act_name, target_lifecycle=lc_name)
    if not _has_attribute(frame, "resource"):
        raise AnalysisPrerequisiteError(
            "Atribut org:resource tidak tersedia pada file XES. Analisis same-resource tidak dapat dilakukan."
        )

    cleaned_resource = occurrences["resource"].astype("string").str.strip()
    valid_resource_mask = cleaned_resource.notna() & cleaned_resource.ne("")
    known = occurrences.loc[valid_resource_mask].copy()
    qualifying_groups = [
        (case_id, resource, matching)
        for (case_id, resource), matching in known.groupby(["case_id", "resource"], sort=False)
        if len(matching) >= min_occ
    ]
    case_ids = list(dict.fromkeys(str(case_id) for case_id, _, _ in qualifying_groups))
    denom = int(data["case_id"].nunique())

    evidence: list[dict[str, Any]] = []
    for case_id, resource, matching in qualifying_groups:
        evidence.append({
            "case_id": str(case_id),
            "resource": str(resource),
            "complete_occurrence_count": int(len(matching)),
            "events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "activity": str(event.activity),
                    "lifecycle": str(event.lifecycle),
                    "resource": str(event.resource),
                    "source_order": int(event.source_order),
                }
                for event in matching.itertuples()
            ],
        })

    missing_resource_count = int((~valid_resource_mask).sum())
    warnings = ["Case dihitung satu kali meskipun lebih dari satu resource memenuhi syarat."]
    if missing_resource_count:
        warnings.append(
            f"{missing_resource_count} complete occurrence tidak memiliki org:resource dan tidak digunakan untuk pengelompokan same-resource."
        )

    return AnalysisResult(
        code="11.18",
        title=f"Case dengan minimal {min_occ} {lc_name} ({act_name}) oleh resource yang sama",
        rule=f"Case lolos jika terdapat resource teridentifikasi yang melakukan {act_name} berstatus {lc_name} minimal {min_occ} kali dalam case tersebut. Resource kosong tidak dikelompokkan.",
        count=len(case_ids),
        case_ids=case_ids,
        denominator=denom,
        percentage=(len(case_ids) / denom * 100.0) if denom else 0.0,
        evidence=evidence,
        warnings=warnings,
    )


def analyze_exercise_1122(
    data: pd.DataFrame,
    first_activity: str = CANCELLED,
    second_activity: str = ACCEPTED,
) -> AnalysisResult:
    """Find cases where `first_activity` (default O_Cancelled) occurs before a later `second_activity` (default O_Accepted)."""
    frame = _require_normalized(data)
    act_first = first_activity.strip() or CANCELLED
    act_second = second_activity.strip() or ACCEPTED
    case_ids: list[str] = []
    evidence: list[dict[str, Any]] = []
    cancelled_cf = act_first.casefold()
    accepted_cf = act_second.casefold()

    # Data is already sorted by case, timestamp and stable source order.
    for case_id, trace in frame.groupby("case_id", sort=False):
        activities = [str(act).strip().casefold() for act in trace["activity"].tolist()]
        cancelled_positions = [i for i, activity in enumerate(activities) if activity == cancelled_cf]
        accepted_positions = [i for i, activity in enumerate(activities) if activity == accepted_cf]

        pair: tuple[int, int] | None = None
        for cancelled_position in cancelled_positions:
            later_accepts = [position for position in accepted_positions if position > cancelled_position]
            if later_accepts:
                pair = (cancelled_position, later_accepts[0])
                break

        if pair is None:
            continue

        case_id_text = str(case_id)
        case_ids.append(case_id_text)
        cancelled_event = trace.iloc[pair[0]]
        accepted_event = trace.iloc[pair[1]]
        evidence.append({
            "case_id": case_id_text,
            "cancelled_event": {
                "activity": str(cancelled_event["activity"]),
                "timestamp": cancelled_event["timestamp"].isoformat(),
                "source_order": int(cancelled_event["source_order"]),
            },
            "subsequent_accepted_event": {
                "activity": str(accepted_event["activity"]),
                "timestamp": accepted_event["timestamp"].isoformat(),
                "source_order": int(accepted_event["source_order"]),
            },
            "intervening_events": max(0, pair[1] - pair[0] - 1),
        })

    denominator = int(frame["case_id"].nunique())
    percentage = (len(case_ids) / denominator * 100.0) if denominator else 0.0

    return AnalysisResult(
        code="11.22",
        title=f"{act_first} eventually followed by {act_second}",
        rule=f"Case lolos jika terdapat posisi i < j dalam trace dengan activity[i] = {act_first} dan activity[j] = {act_second}; kedua event tidak harus bersebelahan.",
        count=len(case_ids),
        case_ids=case_ids,
        denominator=denominator,
        percentage=percentage,
        evidence=evidence,
    )


def build_overview(
    data: pd.DataFrame,
    cycle_times: pd.DataFrame | None = None,
) -> DatasetOverview:
    """Build dataset overview and activity frequencies."""
    frame = _require_normalized(data)
    if cycle_times is None:
        cycle_times = cycle_time_by_case(frame)
    frequencies = (
        frame.groupby("activity", sort=False).size()
        .sort_values(ascending=False)
        .rename("frequency")
        .reset_index()
    )
    timestamps = frame["timestamp"]

    return DatasetOverview(
        total_cases=int(frame["case_id"].nunique()),
        total_events=int(len(frame)),
        unique_activities=int(frame["activity"].nunique()),
        first_timestamp=timestamps.min().isoformat() if not timestamps.empty else None,
        last_timestamp=timestamps.max().isoformat() if not timestamps.empty else None,
        mean_cycle_time_days=float(cycle_times["cycle_time_days"].mean()) if not cycle_times.empty else None,
        activity_frequencies=[
            {"activity": str(row.activity), "frequency": int(row.frequency)}
            for row in frequencies.itertuples()
        ],
        available_attributes=[
            name for name in ("lifecycle", "resource")
            if name in frame.columns and frame[name].notna().any()
        ],
    )


def search_case_durations(
    data: pd.DataFrame,
    query: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Search the case list and return its duration summary.

    The default cap prevents a large XES file from forcing the GUI to render
    tens of thousands of table rows at once. Users can refine the case-ID query.
    """
    if limit < 1:
        raise ValueError("limit harus lebih besar dari nol.")
    durations = cycle_time_by_case(data)
    selected = durations
    normalized_query = query.strip().casefold()
    if normalized_query:
        selected = durations.loc[
            durations["case_id"].astype(str).str.casefold().str.contains(
                normalized_query, regex=False
            )
        ]
    selected = selected.head(limit)
    return [
        {
            "case_id": str(row.case_id),
            "event_count": int(getattr(row, "event_count", 0)),
            "start_time": row.start_time.isoformat(),
            "end_time": row.end_time.isoformat(),
            "cycle_time_days": float(row.cycle_time_days),
        }
        for row in selected.itertuples()
    ]


def get_case_events(data: pd.DataFrame, case_id: str) -> list[dict[str, Any]]:
    """Return the full ordered event trace for a selected case."""
    frame = _require_normalized(data)
    trace = frame.loc[frame["case_id"].astype(str).eq(str(case_id))]
    return [
        {
            "case_id": str(row.case_id),
            "timestamp": row.timestamp.isoformat(),
            "activity": str(row.activity),
            "lifecycle": None if pd.isna(row.lifecycle) else str(row.lifecycle),
            "resource": None if pd.isna(row.resource) else str(row.resource),
            "source_order": int(row.source_order),
        }
        for row in trace.itertuples()
    ]


def analyze_fast_slow_cases(
    data: pd.DataFrame,
    threshold_days: float = 45.0,
    cycle_times: pd.DataFrame | None = None,
) -> FastSlowComparison:
    """Analyze Fast Cases (< threshold_days) vs Slow Cases (>= threshold_days) (Example 11.10)."""
    if threshold_days <= 0:
        raise ValueError("threshold_days harus lebih besar dari 0.")
    frame = _require_normalized(data)
    durations = cycle_times if cycle_times is not None else cycle_time_by_case(frame)
    total_cases = len(durations)

    fast_df = durations.loc[durations["cycle_time_days"] < threshold_days]
    slow_df = durations.loc[durations["cycle_time_days"] >= threshold_days]

    fast_ids = fast_df["case_id"].astype(str).tolist()
    slow_ids = slow_df["case_id"].astype(str).tolist()
    fast_set = set(fast_ids)
    slow_set = set(slow_ids)

    fast_pct = (len(fast_ids) / total_cases * 100.0) if total_cases else 0.0
    slow_pct = (len(slow_ids) / total_cases * 100.0) if total_cases else 0.0
    fast_mean = float(fast_df["cycle_time_days"].mean()) if not fast_df.empty else None
    slow_mean = float(slow_df["cycle_time_days"].mean()) if not slow_df.empty else None

    fast_result = AnalysisResult(
        code="11.10-FAST",
        title=f"Fast cases (cycle time < {threshold_days:g} hari)",
        rule=f"Case dengan durasi trace utuh (last timestamp − first timestamp) < {threshold_days:g} hari.",
        count=len(fast_ids),
        case_ids=fast_ids,
        denominator=total_cases,
        percentage=fast_pct,
        mean_cycle_time_days=fast_mean,
        evidence=[
            {
                "case_id": str(row.case_id),
                "start_time": row.start_time.isoformat(),
                "end_time": row.end_time.isoformat(),
                "cycle_time_days": float(row.cycle_time_days),
            }
            for row in fast_df.head(500).itertuples()
        ],
    )

    slow_result = AnalysisResult(
        code="11.10-SLOW",
        title=f"Slow cases (cycle time >= {threshold_days:g} hari)",
        rule=f"Case dengan durasi trace utuh (last timestamp − first timestamp) >= {threshold_days:g} hari.",
        count=len(slow_ids),
        case_ids=slow_ids,
        denominator=total_cases,
        percentage=slow_pct,
        mean_cycle_time_days=slow_mean,
        evidence=[
            {
                "case_id": str(row.case_id),
                "start_time": row.start_time.isoformat(),
                "end_time": row.end_time.isoformat(),
                "cycle_time_days": float(row.cycle_time_days),
            }
            for row in slow_df.head(500).itertuples()
        ],
    )

    # Compute comparative characteristics per group
    events_per_case = frame.groupby("case_id", sort=False).size()
    events_per_case.index = events_per_case.index.astype(str)
    fast_ev_counts = events_per_case.loc[events_per_case.index.isin(fast_set)]
    slow_ev_counts = events_per_case.loc[events_per_case.index.isin(slow_set)]

    accepted_set = set(_case_ids_with_activity(frame, ACCEPTED))
    refused_set = set(_case_ids_with_activity(frame, REFUSED))
    fraud_set = set(_case_ids_with_activity(frame, FRAUD_ACTIVITY))
    last_events = frame.groupby("case_id", sort=False, as_index=False).tail(1)
    last_cancelled_set = set(
        last_events.loc[_activity_mask(last_events["activity"], CANCELLED), "case_id"].astype(str)
    )

    def _group_rate(group_set: set[str], target_set: set[str]) -> str:
        if not group_set:
            return "0 (0.00%)"
        matched = len(group_set.intersection(target_set))
        return f"{matched:,} ({matched / len(group_set) * 100.0:.2f}%)"

    comparison_metrics = [
        {
            "metric": "Jumlah Case",
            "fast_cases": f"{len(fast_ids):,} ({fast_pct:.2f}%)",
            "slow_cases": f"{len(slow_ids):,} ({slow_pct:.2f}%)",
        },
        {
            "metric": "Mean Cycle Time (hari)",
            "fast_cases": f"{fast_mean:.4f}" if fast_mean is not None else "-",
            "slow_cases": f"{slow_mean:.4f}" if slow_mean is not None else "-",
        },
        {
            "metric": "Median Cycle Time (hari)",
            "fast_cases": f"{float(fast_df['cycle_time_days'].median()):.4f}" if not fast_df.empty else "-",
            "slow_cases": f"{float(slow_df['cycle_time_days'].median()):.4f}" if not slow_df.empty else "-",
        },
        {
            "metric": "Max Cycle Time (hari)",
            "fast_cases": f"{float(fast_df['cycle_time_days'].max()):.4f}" if not fast_df.empty else "-",
            "slow_cases": f"{float(slow_df['cycle_time_days'].max()):.4f}" if not slow_df.empty else "-",
        },
        {
            "metric": "Rata-rata Event per Case",
            "fast_cases": f"{float(fast_ev_counts.mean()):.2f}" if not fast_ev_counts.empty else "-",
            "slow_cases": f"{float(slow_ev_counts.mean()):.2f}" if not slow_ev_counts.empty else "-",
        },
        {
            "metric": f"Mengandung {ACCEPTED} (Successful)",
            "fast_cases": _group_rate(fast_set, accepted_set),
            "slow_cases": _group_rate(slow_set, accepted_set),
        },
        {
            "metric": f"Mengandung {REFUSED} (Unsuccessful)",
            "fast_cases": _group_rate(fast_set, refused_set),
            "slow_cases": _group_rate(slow_set, refused_set),
        },
        {
            "metric": f"Berakhir dengan {CANCELLED} (Canceled)",
            "fast_cases": _group_rate(fast_set, last_cancelled_set),
            "slow_cases": _group_rate(slow_set, last_cancelled_set),
        },
        {
            "metric": f"Mengandung {FRAUD_ACTIVITY}",
            "fast_cases": _group_rate(fast_set, fraud_set),
            "slow_cases": _group_rate(slow_set, fraud_set),
        },
    ]

    return FastSlowComparison(
        threshold_days=threshold_days,
        fast_result=fast_result,
        slow_result=slow_result,
        comparison_metrics=comparison_metrics,
    )


def run_generic_filter(
    data: pd.DataFrame,
    filter_type: str,
    activity_a: str,
    activity_b: str = "",
    min_count: int = 2,
    lifecycle_filter: str = "",
    endpoint_position: str = "end",
    cycle_times: pd.DataFrame | None = None,
) -> AnalysisResult:
    """Generic rule builder supporting contains, endpoint, minimum_occurrence, same_resource, and eventually_follows."""
    frame = _require_normalized(data)
    act_a = activity_a.strip()
    if not act_a:
        raise ValueError("Nama aktivitas utama (Activity A) wajib diisi.")

    durations = cycle_times if cycle_times is not None else cycle_time_by_case(frame)
    total_cases = len(durations)
    mode = filter_type.strip().casefold()
    lc_target = lifecycle_filter.strip().casefold()

    def _filter_by_activity_and_lifecycle(df: pd.DataFrame, act_name: str) -> pd.DataFrame:
        sub = df.loc[_activity_mask(df["activity"], act_name)].copy()
        if lc_target and lc_target != "all":
            if not _has_attribute(df, "lifecycle"):
                raise AnalysisPrerequisiteError(
                    "Atribut lifecycle:transition tidak tersedia pada dataset untuk memfilter lifecycle."
                )
            cleaned_lc = sub["lifecycle"].astype("string").str.strip().str.casefold()
            sub = sub.loc[cleaned_lc.eq(lc_target)].copy()
        return sub

    if mode == "contains":
        matching = _filter_by_activity_and_lifecycle(frame, act_a)
        case_ids = matching["case_id"].drop_duplicates().astype(str).tolist()
        lc_note = f" (lifecycle={lc_target})" if lc_target and lc_target != "all" else ""
        return AnalysisResult(
            code="CUSTOM-CONTAINS",
            title=f"Custom Contains: {act_a}{lc_note}",
            rule=f"Case mengandung minimal satu event '{act_a}'{lc_note}; case dihitung satu kali.",
            count=len(case_ids),
            case_ids=case_ids,
            denominator=total_cases,
            percentage=(len(case_ids) / total_cases * 100.0) if total_cases else 0.0,
            mean_cycle_time_days=_mean_cycle_time_from_table(durations, case_ids),
            evidence=_activity_membership_evidence(frame, durations, act_a, case_ids),
        )

    if mode == "endpoint":
        pos = endpoint_position.strip().casefold()
        if pos == "start":
            boundary = frame.groupby("case_id", sort=False, as_index=False).head(1)
            pos_label = "PERTAMA"
        else:
            boundary = frame.groupby("case_id", sort=False, as_index=False).tail(1)
            pos_label = "TERAKHIR"
        mask = _activity_mask(boundary["activity"], act_a)
        if lc_target and lc_target != "all":
            cleaned_lc = boundary["lifecycle"].astype("string").str.strip().str.casefold()
            mask = mask & cleaned_lc.eq(lc_target)
        matched_rows = boundary.loc[mask]
        case_ids = matched_rows["case_id"].astype(str).tolist()
        return AnalysisResult(
            code="CUSTOM-ENDPOINT",
            title=f"Custom Endpoint ({pos_label}): {act_a}",
            rule=f"Case dipilih jika event {pos_label} dalam trace adalah '{act_a}'.",
            count=len(case_ids),
            case_ids=case_ids,
            denominator=total_cases,
            percentage=(len(case_ids) / total_cases * 100.0) if total_cases else 0.0,
            mean_cycle_time_days=_mean_cycle_time_from_table(durations, case_ids),
            evidence=[
                {
                    "case_id": str(row.case_id),
                    "endpoint_position": pos_label,
                    "activity": str(row.activity),
                    "timestamp": row.timestamp.isoformat(),
                }
                for row in matched_rows.itertuples()
            ],
        )

    if mode == "minimum_occurrence":
        if min_count < 1:
            raise ValueError("Minimum occurrence harus >= 1.")
        occurrences = _filter_by_activity_and_lifecycle(frame, act_a)
        counts = occurrences.groupby("case_id", sort=False).size()
        selected = counts.loc[counts >= min_count]
        case_ids = selected.index.astype(str).tolist()
        lc_note = f" berstatus '{lc_target}'" if lc_target and lc_target != "all" else ""
        evidence: list[dict[str, Any]] = []
        for cid, grp in occurrences.loc[occurrences["case_id"].isin(selected.index)].groupby("case_id", sort=False):
            evidence.append({
                "case_id": str(cid),
                "occurrence_count": int(len(grp)),
                "first_timestamp": grp["timestamp"].iloc[0].isoformat(),
                "last_timestamp": grp["timestamp"].iloc[-1].isoformat(),
            })
        return AnalysisResult(
            code="CUSTOM-MIN-OCC",
            title=f"Custom Min Occurrence (>={min_count}x): {act_a}{lc_note}",
            rule=f"Case dengan minimal {min_count} occurrence '{act_a}'{lc_note} dalam satu case.",
            count=len(case_ids),
            case_ids=case_ids,
            denominator=total_cases,
            percentage=(len(case_ids) / total_cases * 100.0) if total_cases else 0.0,
            mean_cycle_time_days=_mean_cycle_time_from_table(durations, case_ids),
            evidence=evidence,
        )

    if mode == "same_resource":
        if min_count < 2:
            raise ValueError("Minimum occurrence untuk same_resource harus >= 2.")
        if not _has_attribute(frame, "resource"):
            raise AnalysisPrerequisiteError("Atribut org:resource tidak tersedia pada dataset aktif.")
        occurrences = _filter_by_activity_and_lifecycle(frame, act_a)
        cleaned_res = occurrences["resource"].astype("string").str.strip()
        valid_mask = cleaned_res.notna() & cleaned_res.ne("")
        known = occurrences.loc[valid_mask].copy()
        qualifying = [
            (cid, res, grp)
            for (cid, res), grp in known.groupby(["case_id", "resource"], sort=False)
            if len(grp) >= min_count
        ]
        case_ids = list(dict.fromkeys(str(cid) for cid, _, _ in qualifying))
        lc_note = f" ({lc_target})" if lc_target and lc_target != "all" else ""
        evidence = [
            {
                "case_id": str(cid),
                "resource": str(res),
                "occurrence_count": int(len(grp)),
            }
            for cid, res, grp in qualifying
        ]
        return AnalysisResult(
            code="CUSTOM-SAME-RES",
            title=f"Custom Same Resource (>={min_count}x): {act_a}{lc_note}",
            rule=(
                f"Case dengan minimal {min_count} occurrence '{act_a}'{lc_note} oleh org:resource "
                "teridentifikasi yang sama. Resource kosong tidak dikelompokkan."
            ),
            count=len(case_ids),
            case_ids=case_ids,
            denominator=total_cases,
            percentage=(len(case_ids) / total_cases * 100.0) if total_cases else 0.0,
            mean_cycle_time_days=_mean_cycle_time_from_table(durations, case_ids),
            evidence=evidence,
        )

    if mode == "eventually_follows":
        act_b = activity_b.strip()
        if not act_b:
            raise ValueError("Aktivitas kedua (Activity B) wajib diisi untuk filter eventually_follows.")
        a_cf = act_a.casefold()
        b_cf = act_b.casefold()
        case_ids = []
        evidence = []
        for cid, trace in frame.groupby("case_id", sort=False):
            acts = [str(x).strip().casefold() for x in trace["activity"].tolist()]
            a_pos = [i for i, x in enumerate(acts) if x == a_cf]
            b_pos = [i for i, x in enumerate(acts) if x == b_cf]
            pair: tuple[int, int] | None = None
            for i in a_pos:
                later = [j for j in b_pos if j > i]
                if later:
                    pair = (i, later[0])
                    break
            if pair is None:
                continue
            cid_str = str(cid)
            case_ids.append(cid_str)
            ev_a = trace.iloc[pair[0]]
            ev_b = trace.iloc[pair[1]]
            evidence.append({
                "case_id": cid_str,
                "first_event": {
                    "activity": str(ev_a["activity"]),
                    "timestamp": ev_a["timestamp"].isoformat(),
                },
                "subsequent_event": {
                    "activity": str(ev_b["activity"]),
                    "timestamp": ev_b["timestamp"].isoformat(),
                },
                "intervening_events": max(0, pair[1] - pair[0] - 1),
            })
        return AnalysisResult(
            code="CUSTOM-FOLLOWS",
            title=f"Custom Eventually Follows: {act_a} -> {act_b}",
            rule=f"Case dengan event '{act_a}' pada posisi i < j sebelum event '{act_b}' di trace yang sama.",
            count=len(case_ids),
            case_ids=case_ids,
            denominator=total_cases,
            percentage=(len(case_ids) / total_cases * 100.0) if total_cases else 0.0,
            mean_cycle_time_days=_mean_cycle_time_from_table(durations, case_ids),
            evidence=evidence,
        )

    raise ValueError(f"Tipe filter tidak dikenali: {filter_type}")


def build_simple_dfg(
    data: pd.DataFrame,
    top_n: int = 25,
    include_self_loops: bool = False,
) -> list[dict[str, Any]]:
    """Compute a simple directly-follows frequency and duration table for exploration.

    NOTE: This strictly counts adjacent event pairs (A -> B) within traces using Pandas
    without any process discovery algorithm (no Alpha, Heuristics, Inductive Miner, or Petri Net).
    By default, trivial self-loops (A -> A from lifecycle steps) are excluded so inter-activity
    flow is clearly visible, unless `include_self_loops=True`.
    """
    if top_n < 1:
        raise ValueError("top_n harus >= 1.")
    frame = _require_normalized(data)

    # Compute per-activity node statistics (total events, unique cases, start/end counts, average trace rank)
    work = frame[["case_id", "activity", "timestamp"]].copy()
    work["step_rank"] = work.groupby("case_id", sort=False).cumcount()

    first_acts = work.groupby("case_id", sort=False).head(1)["activity"].value_counts().to_dict()
    last_acts = work.groupby("case_id", sort=False).tail(1)["activity"].value_counts().to_dict()

    node_stats_df = (
        work.groupby("activity", sort=False)
        .agg(
            event_count=("timestamp", "size"),
            case_count=("case_id", "nunique"),
            avg_rank=("step_rank", "mean"),
        )
        .reset_index()
    )
    node_meta: dict[str, dict[str, Any]] = {}
    for row in node_stats_df.itertuples():
        act_name = str(row.activity)
        node_meta[act_name] = {
            "activity": act_name,
            "event_count": int(row.event_count),
            "case_count": int(row.case_count),
            "start_count": int(first_acts.get(act_name, 0)),
            "end_count": int(last_acts.get(act_name, 0)),
            "avg_rank": float(row.avg_rank),
        }

    work["next_case_id"] = work["case_id"].shift(-1)
    work["target_activity"] = work["activity"].shift(-1)
    work["next_timestamp"] = work["timestamp"].shift(-1)

    same_case = work.loc[work["case_id"].eq(work["next_case_id"])].copy()
    if not include_self_loops:
        same_case = same_case.loc[same_case["activity"].ne(same_case["target_activity"])].copy()
    if same_case.empty:
        return []

    same_case["delta_hours"] = (
        (same_case["next_timestamp"] - same_case["timestamp"]).dt.total_seconds() / 3600.0
    )
    grouped = (
        same_case.groupby(["activity", "target_activity"], sort=False)
        .agg(
            frequency=("delta_hours", "size"),
            case_count=("case_id", "nunique"),
            mean_hours=("delta_hours", "mean"),
        )
        .reset_index()
        .sort_values("frequency", ascending=False)
        .head(top_n)
    )
    return [
        {
            "source_activity": str(row.activity),
            "target_activity": str(row.target_activity),
            "frequency": int(row.frequency),
            "case_count": int(row.case_count),
            "mean_hours": float(row.mean_hours),
            "source_meta": node_meta.get(str(row.activity), {}),
            "target_meta": node_meta.get(str(row.target_activity), {}),
        }
        for row in grouped.itertuples()
    ]

