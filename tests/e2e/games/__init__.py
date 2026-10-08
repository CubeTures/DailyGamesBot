"""One driver per game in games/: how to learn the day's solution and play
each outcome. See tests/e2e/harness.py for the Driver and Player types."""

import importlib
import pkgutil

from tests.e2e.harness import Driver


def _load() -> dict[str, Driver]:
    drivers: dict[str, Driver] = {}
    for module in pkgutil.iter_modules(__path__):
        driver: Driver = importlib.import_module(f"{__name__}.{module.name}").DRIVER
        drivers[driver.name] = driver
    return drivers


DRIVERS = _load()
