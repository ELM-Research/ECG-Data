"""Term agreement and pointwise 95% intervals, assuming independent ECGs."""

from dataclasses import dataclass
from math import sqrt
from statistics import NormalDist


CONFIDENCE = 0.95
_Z = NormalDist().inv_cdf((1 + CONFIDENCE) / 2)


@dataclass(frozen=True)
class Ratio:
    numerator: int
    denominator: int
    low: float | None = None
    high: float | None = None

    @property
    def value(self):
        return self.numerator / self.denominator if self.denominator else None


def proportion(numerator, denominator):
    """Wilson score interval; undefined when no eligible ECGs exist."""
    if not denominator:
        return Ratio(numerator, denominator)

    p = numerator / denominator
    scale = 1 + _Z**2 / denominator
    center = (p + _Z**2 / (2 * denominator)) / scale
    margin = _Z * sqrt(p * (1 - p) / denominator + _Z**2 / (4 * denominator**2)) / scale
    return Ratio(numerator, denominator, max(0, center - margin), min(1, center + margin))


def _f1(tp, fp, fn):
    # J = TP / (TP + FP + FN); F1 = 2J / (1 + J).
    jaccard = proportion(tp, tp + fp + fn)
    if jaccard.value is None:
        return Ratio(0, 0)
    return Ratio(
        2 * tp, 2 * tp + fp + fn,
        2 * jaccard.low / (1 + jaccard.low),
        2 * jaccard.high / (1 + jaccard.high),
    )


def _extras(fp, reference):
    # FP and reference positives are disjoint: FP/reference is the odds
    # of FP within their union. Transform the Wilson limits for that proportion.
    if not reference:
        return Ratio(fp, reference)
    extra = proportion(fp, fp + reference)
    high = extra.high / (1 - extra.high) if extra.high < 1 else float("inf")
    return Ratio(fp, reference, extra.low / (1 - extra.low), high)


def term_metrics(tp, fp, fn, tn):
    reference = tp + fn
    either = tp + fp + fn
    missed = proportion(fn, reference)
    return {
        "added_report_ratio": proportion(fn, fn + tn),
        "deleted_report_ratio": proportion(fp, tp + fp),
        "precision": proportion(tp, tp + fp),
        "recall": proportion(tp, reference),
        "f1": _f1(tp, fp, fn),
        "false_negative_rate": missed,
        "false_positive_rate": proportion(fp, fp + tn),
        "missed_ratio": proportion(fn, either),
        "extra_ratio": proportion(fp, either),
        "disagreement_ratio": proportion(fn + fp, either),
        "missed_per_reference": missed,
        "extra_per_reference": _extras(fp, reference),
    }
