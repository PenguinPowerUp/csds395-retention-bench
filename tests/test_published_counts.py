import pytest

from retention_bench.run import check_published_counts


def results(counts, sens_counts=None):
    return {"population": {"counts": counts}, "sensitivity": {"s": {"counts": sens_counts or {}}}}


def test_counts_of_ten_or_more_and_zero_are_allowed():
    check_published_counts(results({"eligible": 79497, "excluded_partial_outage": 0}, {"excluded_next_day_not_observed": 162}))


@pytest.mark.parametrize("where", ["population", "sensitivity"])
def test_a_count_between_one_and_nine_is_refused(where):
    small = {"excluded_next_day_not_observed": 3}
    r = results(small) if where == "population" else results({}, small)
    with pytest.raises(SystemExit, match="below 10"):
        check_published_counts(r)
