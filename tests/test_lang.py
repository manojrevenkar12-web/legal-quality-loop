import pytest

from qloop.lang import FINE, anchor, duration, extract, language, rate, realise

POINTS = [
    duration(3, "month"),
    duration(1, "month"),
    duration(6, "week"),
    duration(72, "hour"),
    duration(2, "week"),
    duration(5, "year"),
    rate(9, "base"),
    rate(9.2, "base"),
    rate(8, "ecb"),
    FINE,
    anchor("end_of_month"),
    anchor("end_of_quarter"),
    anchor("written_form"),
    anchor("extendable_two_months"),
]


@pytest.mark.parametrize("lang", ["en", "de"])
@pytest.mark.parametrize("words", [False, True])
@pytest.mark.parametrize("point", POINTS, ids=str)
def test_every_point_reads_back_in_every_language_and_style(point, lang, words):
    assert point in extract(realise(point, lang, words))


def test_articles_are_not_numbers():
    assert duration(1, "month") not in extract("Notice ends on the last day of a month.")


def test_contradicting_values_are_both_seen():
    assert {duration(2, "month"), duration(3, "month")} <= extract("two months, not 3 months")


def test_language_detection():
    assert language("Nach § 622 BGB beträgt die Frist drei Monate zum Ende eines Kalendermonats.") == "de"
    assert language("Under § 622 BGB the period is three months to the end of a calendar month.") == "en"
