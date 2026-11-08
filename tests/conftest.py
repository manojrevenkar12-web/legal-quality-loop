import pytest

from qloop.config import load
from qloop.world.tasks import all_tasks


@pytest.fixture(scope="session")
def settings():
    return load()


@pytest.fixture(scope="session")
def tasks(settings):
    return all_tasks(settings.tasks.heldout_topics)


@pytest.fixture(scope="session")
def dev(tasks):
    return [t for t in tasks if t.split == "dev"]
