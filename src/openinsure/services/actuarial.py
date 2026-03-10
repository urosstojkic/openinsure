"""Actuarial business-logic services.

Provides chain-ladder IBNR estimation, loss-triangle generation,
and rate-adequacy analysis.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Types used by the service layer (plain dicts for storage flexibility)
# ---------------------------------------------------------------------------

TriangleRow = dict[int, Decimal]  # development_month -> incurred_amount
Triangle = dict[int, TriangleRow]  # accident_year -> row


def generate_loss_triangle(
    lob: str,
    claims_data: list[dict[str, Any]],
) -> Triangle:
    """Build a loss-development triangle from raw claims data.

    Each claim dict is expected to carry at minimum:
      - accident_year: int
      - development_month: int
      - incurred_amount: numeric (str/float/Decimal)
    """
    triangle: Triangle = {}
    for claim in claims_data:
        ay = int(claim["accident_year"])
        dm = int(claim["development_month"])
        amt = Decimal(str(claim["incurred_amount"]))
        triangle.setdefault(ay, {})[dm] = triangle.get(ay, {}).get(dm, Decimal("0")) + amt

    logger.info("actuarial.triangle_generated", lob=lob, rows=len(triangle))
    return triangle


def _age_to_age_factors(triangle: Triangle) -> dict[int, Decimal]:
    """Calculate weighted-average age-to-age development factors."""
    sorted_years = sorted(triangle.keys())
    all_periods = sorted({dm for row in triangle.values() for dm in row})

    factors: dict[int, Decimal] = {}
    for i in range(len(all_periods) - 1):
        curr_period = all_periods[i]
        next_period = all_periods[i + 1]
        sum_curr = Decimal("0")
        sum_next = Decimal("0")
        for ay in sorted_years:
            row = triangle[ay]
            if curr_period in row and next_period in row:
                sum_curr += row[curr_period]
                sum_next += row[next_period]
        if sum_curr > 0:
            factors[curr_period] = (sum_next / sum_curr).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return factors


def estimate_ibnr(
    triangle: Triangle,
    method: str = "chain_ladder",
) -> dict[str, Any]:
    """Estimate IBNR reserves using the chain-ladder method.

    Returns a dict with:
      - factors: age-to-age development factors
      - ultimates: projected ultimate losses per accident year
      - ibnr_by_year: IBNR per accident year
      - total_ibnr: aggregate IBNR
    """
    if method != "chain_ladder":
        raise ValueError(f"Unsupported method: {method}")

    factors = _age_to_age_factors(triangle)
    if not factors:
        return {
            "factors": {},
            "ultimates": {},
            "ibnr_by_year": {},
            "total_ibnr": "0",
        }

    # Cumulative development factor (CDF) from each period to ultimate
    sorted_periods = sorted(factors.keys())
    cdfs: dict[int, Decimal] = {}
    cumulative = Decimal("1")
    for period in reversed(sorted_periods):
        cumulative *= factors[period]
        cdfs[period] = cumulative.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    ultimates: dict[int, Decimal] = {}
    ibnr_by_year: dict[int, Decimal] = {}

    for ay, row in triangle.items():
        latest_period = max(row.keys())
        current_incurred = row[latest_period]
        cdf = cdfs.get(latest_period, Decimal("1"))
        ultimate = (current_incurred * cdf).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ultimates[ay] = ultimate
        ibnr_by_year[ay] = (ultimate - current_incurred).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_ibnr = sum(ibnr_by_year.values(), Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    logger.info(
        "actuarial.ibnr_estimated",
        method=method,
        total_ibnr=str(total_ibnr),
    )

    return {
        "factors": {str(k): str(v) for k, v in factors.items()},
        "ultimates": {str(k): str(v) for k, v in ultimates.items()},
        "ibnr_by_year": {str(k): str(v) for k, v in ibnr_by_year.items()},
        "total_ibnr": str(total_ibnr),
    }


def calculate_rate_adequacy(
    lob: str,
    current_rates: dict[str, Decimal],
    loss_data: dict[str, Decimal],
) -> list[dict[str, Any]]:
    """Rate-adequacy analysis comparing current rates to indicated rates.

    ``current_rates`` maps segment -> current rate.
    ``loss_data`` maps segment -> indicated rate (from loss experience).

    Returns a list of segment-level adequacy records.
    """
    results: list[dict[str, Any]] = []
    for segment, current in current_rates.items():
        indicated = loss_data.get(segment, current)
        adequacy = (
            (indicated / current).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if current > 0 else Decimal("0")
        )
        results.append(
            {
                "line_of_business": lob,
                "segment": segment,
                "current_rate": str(current),
                "indicated_rate": str(indicated),
                "adequacy_ratio": str(adequacy),
            }
        )

    logger.info(
        "actuarial.rate_adequacy",
        lob=lob,
        segments=len(results),
    )
    return results
