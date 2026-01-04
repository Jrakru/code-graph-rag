import pytest


@pytest.mark.integration
def test_cli_staleness_integration() -> None:
    pytest.skip("staleness CLI integration requires external setup")
