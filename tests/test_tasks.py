from qloop.config import ROOT
from qloop.lang import duration
from qloop.world.corpus import index, provisions
from qloop.world.tasks import at_notice, de_notice, fingerprint, nl_notice


def test_statutory_tables():
    assert [de_notice(y) for y in (2, 5, 8, 10, 12, 15, 20)] == [1, 2, 3, 4, 5, 6, 7]
    assert de_notice(7) == 2 and de_notice(9) == 3
    assert (
        at_notice(1) == duration(6, "week")
        and at_notice(5) == duration(3, "month")
        and at_notice(25) == duration(5, "month")
    )
    assert [nl_notice(y) for y in (4, 5, 10, 15)] == [1, 2, 3, 4]


def test_every_reference_citation_exists(tasks):
    known = provisions()
    assert all(c in known for t in tasks for c in t.reference.citations)


def test_splits_and_families(tasks):
    held = [t for t in tasks if t.split == "heldout"]
    dev = [t for t in tasks if t.split == "dev"]
    assert {t.family for t in held} == {"research", "review", "discovery"}
    assert not {t.topic for t in held} & {t.topic for t in dev}
    assert sum(t.injected for t in dev) > 0 and sum(t.injected for t in held) > 0
    assert {t.language for t in dev} == {"en", "de"}


def test_heldout_pin_matches(tasks):
    held = [t for t in tasks if t.split == "heldout"]
    assert fingerprint(held) == (ROOT / "config" / "heldout.sha256").read_text().strip()


def test_retrieval_finds_the_rule_for_its_country():
    hits = index().search("What notice period must the employer observe in Austria after 10 years?", 3, "AT")
    assert hits[0].id == "AT-AngG-20"
    unfiltered = [p.jurisdiction for p in index().search("employer notice period years of service", 6)]
    assert len(set(unfiltered)) > 1  # without the filter, other countries' rules compete
