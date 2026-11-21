"""Create a tiny synthetic XES file for local GUI smoke testing.

This is NOT the official BPIC17 dataset and must never be used as final BPIC17
result evidence. It only exercises the XES import and assignment filters.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROWS = {
    "SYN-001": [
        ("O_Submitted", "2026-01-01T08:00:00Z", "complete", "Clerk"),
        ("O_Cancelled", "2026-01-01T09:00:00Z", "complete", "Clerk"),
        ("O_Review", "2026-01-01T09:30:00Z", "complete", "Clerk"),
        ("O_Accepted", "2026-01-01T10:00:00Z", "complete", "Manager"),
        ("W_Assess Potential Fraud", "2026-01-01T12:00:00Z", "start", "Alice"),
        ("W_Assess Potential Fraud", "2026-01-01T13:00:00Z", "complete", "Alice"),
        ("W_Assess Potential Fraud", "2026-01-01T14:00:00Z", "complete", "Alice"),
        ("W_Assess Potential Fraud", "2026-01-01T15:00:00Z", "complete", "Bob"),
    ],
    "SYN-002": [
        ("O_Refused", "2026-01-02T08:00:00Z", "complete", "Manager"),
        ("W_Assess Potential Fraud", "2026-01-02T09:00:00Z", "complete", "Alice"),
        ("W_Assess Potential Fraud", "2026-01-02T10:00:00Z", "complete", "Bob"),
        ("O_Accepted", "2026-01-02T11:00:00Z", "complete", "Manager"),
        ("O_Cancelled", "2026-01-02T12:00:00Z", "complete", "Manager"),
    ],
    "SYN-003": [
        ("O_Accepted", "2026-01-03T08:00:00Z", "complete", "Manager"),
        ("W_Assess Potential Fraud", "2026-01-03T09:00:00Z", "complete", "Alice"),
        ("O_Refused", "2026-01-04T08:00:00Z", "complete", "Manager"),
    ],
    "SYN-004": [
        ("O_Cancelled", "2026-01-05T08:00:00Z", "complete", "Manager"),
        ("O_Review", "2026-01-05T09:00:00Z", "complete", "Manager"),
    ],
}


def add_attribute(parent: ET.Element, tag: str, key: str, value: str) -> None:
    ET.SubElement(parent, tag, {"key": key, "value": value})


def main() -> None:
    log = ET.Element("log", {
        "xes.version": "1.0",
        "xes.features": "nested-attributes",
        "openxes.version": "1.0RC7",
    })
    add_attribute(log, "string", "concept:name", "Synthetic BPIC17 Assignment Demo")
    for case_id, events in ROWS.items():
        trace = ET.SubElement(log, "trace")
        add_attribute(trace, "string", "concept:name", case_id)
        for activity, timestamp, lifecycle, resource in events:
            event = ET.SubElement(trace, "event")
            add_attribute(event, "string", "concept:name", activity)
            add_attribute(event, "date", "time:timestamp", timestamp)
            add_attribute(event, "string", "lifecycle:transition", lifecycle)
            add_attribute(event, "string", "org:resource", resource)

    output = Path(__file__).with_name("synthetic_bpic17_demo.xes")
    ET.indent(log, space="  ")
    ET.ElementTree(log).write(output, encoding="utf-8", xml_declaration=True)
    print(f"Synthetic XES created: {output}")


if __name__ == "__main__":
    main()
