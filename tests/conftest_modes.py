"""Test mode configuration.

Usage:
  pytest tests/             # Runs with in-memory storage (default, no Azure needed)
  pytest tests/ --azure     # Runs with real Azure resources (requires .env config)
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--azure",
        action="store_true",
        default=False,
        help="Run tests against real Azure resources (requires .env configuration)",
    )


@pytest.fixture
def azure_mode(request):
    """Whether tests should use real Azure resources."""
    return request.config.getoption("--azure")


@pytest.fixture
def storage_mode(request):
    """Returns 'azure' or 'memory' based on test flags."""
    if request.config.getoption("--azure"):
        return "azure"
    return "memory"
