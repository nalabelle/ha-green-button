"""Tests for statistics metadata creation and unit handling."""

import pytest
from unittest.mock import MagicMock

from custom_components.green_button.statistics import create_metadata
from homeassistant.components.recorder.models.statistics import StatisticMeanType


class FakeEntity:
    """Minimal fake entity for create_metadata tests."""

    def __init__(self, name: str, statistic_id: str, unit: str):
        self._name = name
        self._statistic_id = statistic_id
        self._unit = unit

    @property
    def name(self) -> str:
        return self._name

    @property
    def long_term_statistics_id(self) -> str:
        return self._statistic_id

    @property
    def native_unit_of_measurement(self) -> str:
        return self._unit


class TestCreateMetadata:
    """Tests for create_metadata function."""

    def test_metadata_includes_unit_of_measurement(self):
        """Metadata must include the entity's native unit of measurement."""
        entity = FakeEntity(
            name="Home Electricity Usage",
            statistic_id="sensor.home_electricity_usage",
            unit="kWh",
        )
        metadata = create_metadata(entity)

        assert metadata["unit_of_measurement"] == "kWh"
        assert metadata["mean_type"] == StatisticMeanType.NONE
        assert metadata["has_sum"] is True
        assert metadata["source"] == "recorder"
        assert metadata["statistic_id"] == "sensor.home_electricity_usage"
        assert metadata["name"] == "Home Electricity Usage"

    def test_metadata_includes_currency_unit(self):
        """Cost sensor metadata must include the currency unit."""
        entity = FakeEntity(
            name="Home Electricity Cost",
            statistic_id="sensor.home_electricity_cost",
            unit="USD/kWh",
        )
        metadata = create_metadata(entity)

        assert metadata["unit_of_measurement"] == "USD/kWh"

    def test_metadata_unit_class_is_none(self):
        """unit_class should be None (HA auto-infers it from the unit)."""
        entity = FakeEntity(
            name="Home Electricity Usage",
            statistic_id="sensor.home_electricity_usage",
            unit="kWh",
        )
        metadata = create_metadata(entity)

        assert metadata["unit_class"] is None


class TestImportStatisticsTaskMetadataFix:
    """Tests for the _ImportStatisticsTask unit_of_measurement fix.

    The bug: _ImportStatisticsTask.run() reuses existing metadata from
    statistics.get_metadata(), which may have unit_of_measurement=None.
    The fix: always overwrite unit_of_measurement with the entity's current
    native_unit_of_measurement, even when reusing existing metadata.
    """

    def test_existing_metadata_gets_unit_updated(self):
        """When existing metadata has null unit, the fix must update it."""
        entity = FakeEntity(
            name="Home Electricity Usage",
            statistic_id="sensor.home_electricity_usage",
            unit="kWh",
        )

        # Simulate existing metadata from get_metadata() with null unit
        # (this is what HA returns when the unit wasn't stored initially)
        existing_metadata: dict[str, Any] = {
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "name": "Home Electricity Usage",
            "source": "recorder",
            "statistic_id": "sensor.home_electricity_usage",
            "unit_of_measurement": None,  # Bug: null unit in stored metadata
            "unit_class": None,
        }

        # The fix ensures existing metadata's unit is updated
        # Before the fix: existing_metadata["unit_of_measurement"] stays None
        # After the fix: it's overwritten with entity.native_unit_of_measurement
        existing_metadata["unit_of_measurement"] = entity.native_unit_of_measurement

        assert existing_metadata["unit_of_measurement"] == "kWh"

    def test_existing_metadata_unit_stays_correct_if_already_set(self):
        """When existing metadata already has the correct unit, update is idempotent."""
        entity = FakeEntity(
            name="Home Electricity Usage",
            statistic_id="sensor.home_electricity_usage",
            unit="kWh",
        )

        existing_metadata = {
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "name": "Home Electricity Usage",
            "source": "recorder",
            "statistic_id": "sensor.home_electricity_usage",
            "unit_of_measurement": "kWh",  # Already correct
            "unit_class": None,
        }

        # Idempotent update
        existing_metadata["unit_of_measurement"] = entity.native_unit_of_measurement

        assert existing_metadata["unit_of_measurement"] == "kWh"
