from __future__ import annotations

from dataclasses import dataclass

from fh_admin_tui.catalog import Catalog
from fh_admin_tui.mutations import diff_summary_lines, validate_data


@dataclass(frozen=True)
class ReviewData:
    lines: list[str]
    errors: list[str]


def build_review(baseline: dict, current: dict, catalog: Catalog) -> ReviewData:
    return ReviewData(diff_summary_lines(baseline, current, catalog), validate_data(current))
