"""Test the lightweight observability core (Counter / Gauge / Histogram).

Covers: label handling, negative Counter rejection, Histogram bucket
cumulation, Prometheus exposition format, and the ``unavailable`` marker
for metrics that were never observed (任务书 §7 验收).
"""
from __future__ import annotations

import math
import re

import pytest

from app.core.observability import (
    Counter,
    Gauge,
    Histogram,
    Registry,
    get_registry,
)


# ---- Registry is singleton ----------------------------------------------

def test_registry_is_singleton():
    assert Registry.instance() is Registry.instance()
    assert get_registry() is Registry.instance()


# ---- Counter -------------------------------------------------------------

class TestCounter:
    def test_inc_increments(self):
        c = Counter("test_counter_inc", "h", ("label_a",))
        c.inc(labels={"label_a": "x"})
        c.inc(labels={"label_a": "x"})
        collected = c._collect()
        # _collect returns List[Tuple[label_tuple, value]]
        assert len(collected) == 1
        lbls, val = collected[0]
        assert lbls == (("label_a", "x"),)
        assert val == 2.0

    def test_negative_inc_forbidden(self):
        c = Counter("test_counter_neg", "h", ())
        with pytest.raises(ValueError):
            c.inc(-1.0)

    def test_wrong_label_name_defaults_to_empty(self):
        c = Counter("test_counter_bad_label", "h", ("expected",))
        # Counter silently maps unknown key → empty string — does not raise
        c.inc(labels={"expected": "ok", "extra": "ignored"})
        collected = c._collect()
        lbls, _ = collected[0]
        assert lbls == (("expected", "ok"),)

    def test_empty_labels(self):
        c = Counter("test_counter_no_labels", "h", ())
        c.inc()
        collected = c._collect()
        lbls, val = collected[0]
        assert lbls == ()
        assert val == 1.0


# ---- Gauge ---------------------------------------------------------------

class TestGauge:
    def test_set_and_get(self):
        g = Gauge("test_gauge_set", "h", ())
        g.set(42.0)
        assert g.get() == 42.0

    def test_never_set_is_unavailable(self):
        g = Gauge("test_gauge_noset", "h", ())
        assert g.get() is None

    def test_inc_dec(self):
        g = Gauge("test_gauge_id", "h", ("m",))
        g.set(10.0, labels={"m": "a"})
        g.inc(5.0, labels={"m": "a"})
        g.dec(2.0, labels={"m": "a"})
        assert g.get(labels={"m": "a"}) == 13.0

    def test_different_labels_independent(self):
        g = Gauge("test_gauge_indep", "h", ("k",))
        g.set(1.0, labels={"k": "x"})
        g.set(99.0, labels={"k": "y"})
        assert g.get(labels={"k": "x"}) == 1.0
        assert g.get(labels={"k": "y"}) == 99.0


# ---- Histogram -----------------------------------------------------------

class TestHistogram:
    def test_buckets_cumulate(self):
        h = Histogram(
            "test_hist_buckets", "h", (),
            buckets=(1.0, 5.0, 10.0, math.inf),
        )
        h.observe(0.5)
        h.observe(3.0)
        h.observe(7.0)
        h.observe(7.0)
        h.observe(15.0)
        rows = h._collect()
        bucket_rows = [r for r in rows if r[0].endswith("_bucket")]
        sums = [float(r[2]) for r in bucket_rows]
        # cumulative: 0.5→1, +3→2, +7,7→4, +15→5
        assert sums == [1.0, 2.0, 4.0, 5.0]

    def test_sum_and_count(self):
        h = Histogram("test_hist_sum", "h", (), buckets=(10.0, math.inf))
        h.observe(1.5)
        h.observe(2.5)
        rows = h._collect()
        sum_row = [r for r in rows if r[0].endswith("_sum")][0]
        cnt_row = [r for r in rows if r[0].endswith("_count")][0]
        assert sum_row[2] == 4.0
        assert cnt_row[2] == 2.0

    def test_nan_skipped(self):
        h = Histogram("test_hist_nan", "h", (), buckets=(1.0, math.inf))
        h.observe(float("nan"))
        h.observe(0.5)
        rows = h._collect()
        cnt_row = [r for r in rows if r[0].endswith("_count")][0]
        assert cnt_row[2] == 1.0


# ---- Prometheus exposition -----------------------------------------------

class TestExposition:
    def test_counter_line_format(self):
        c = Counter("expo_counter", "h h", ("a",))
        c.inc(labels={"a": "x"})
        reg = Registry()
        reg.register(c)
        text = reg.exposition_text()
        assert "# HELP expo_counter h h" in text
        assert "# TYPE expo_counter counter" in text
        assert 'expo_counter{a="x"} 1' in text

    def test_gauge_format(self):
        g = Gauge("expo_gauge", "g", ())
        g.set(3.14)
        reg = Registry()
        reg.register(g)
        text = reg.exposition_text()
        assert "expo_gauge 3.14" in text

    def test_histogram_has_le_labels(self):
        h = Histogram("expo_hist", "h", (), buckets=(1.0, 10.0, math.inf))
        h.observe(0.5)
        reg = Registry()
        reg.register(h)
        text = reg.exposition_text()
        assert 'expo_hist_bucket{le="1"}' in text
        assert 'expo_hist_bucket{le="10"}' in text
        assert 'expo_hist_bucket{le="+Inf"}' in text
        assert "expo_hist_sum" in text
        assert "expo_hist_count" in text


# ---- overview "unavailable" marker --------------------------------------

class TestOverviewUnavailable:
    def test_never_observed_is_unavailable(self):
        reg = Registry()
        unused = Counter("unused_counter_xyz", "never used", ())
        reg.register(unused)
        ov = reg.to_overview()
        assert ov["unused_counter_xyz"]["status"] == "unavailable"
        assert ov["unused_counter_xyz"]["series"] == []

    def test_observed_is_ok(self):
        reg = Registry()
        used = Counter("used_counter_xyz", "used once", ("l",))
        reg.register(used)
        used.inc(labels={"l": "a"})
        ov = reg.to_overview()
        assert ov["used_counter_xyz"]["status"] == "ok"
        assert ov["used_counter_xyz"]["series"][0]["l"] == "a"
