"""Unit tests for ESPI parser flowDirection/intervalLength filtering.

Tests that the parser correctly includes monthly electricity data
(flowDirection=1, intervalLength=2678400) and other interval sizes,
not just sub-daily intervals.
"""

import textwrap
from xml.etree import ElementTree as ET

from custom_components.green_button.parsers.espi import GreenButtonFeed

# ── Helpers ──────────────────────────────────────────────────────────────────

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
}


def _make_espi_xml(
    interval_length: int = 3600,
    flow_direction: int = 1,
    commodity: int = 1,  # 1 = electricity
    include_usage_point: bool = True,
    reading_value: int = 1500,
    interval_start: int = 1719504000,  # 2024-06-27T12:00:00Z
    interval_duration: int | None = None,
) -> str:
    """Build a minimal ESPI XML feed for testing.

    Args:
        interval_length: The espi:intervalLength value for the ReadingType
            (e.g. 900 for 15-min, 3600 for hourly, 86400 for daily, 2678400 for monthly)
        flow_direction: The espi:flowDirection value (1=forward/consumption)
        commodity: The espi:commodity value (1=electricity, other values possible)
        include_usage_point: Whether to include a UsagePoint entry
        reading_value: The value for the IntervalReading
        interval_start: Unix timestamp for the interval start
        interval_duration: Duration of the IntervalReading in seconds
            (defaults to interval_length if not specified)
    """
    if interval_duration is None:
        interval_duration = interval_length

    usage_point_block = ""
    if include_usage_point:
        usage_point_block = textwrap.dedent("""\
            <atom:entry>
              <atom:id>urn:uuid:up-001</atom:id>
              <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001"/>
              <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading"/>
              <atom:content type="xml">
                <espi:UsagePoint>
                  <espi:ServiceCategory><espi:kind>0</espi:kind></espi:ServiceCategory>
                </espi:UsagePoint>
              </atom:content>
            </atom:entry>
        """)

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <atom:feed xmlns:atom="http://www.w3.org/2005/Atom"
                   xmlns:espi="http://naesb.org/espi">
          <atom:entry>
            <atom:id>urn:uuid:rt-001</atom:id>
            <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/ReadingType/01"/>
            <atom:content type="xml">
              <espi:ReadingType>
                <espi:commodity>{commodity}</espi:commodity>
                <espi:flowDirection>{flow_direction}</espi:flowDirection>
                <espi:intervalLength>{interval_length}</espi:intervalLength>
                <espi:powerOfTenMultiplier>-3</espi:powerOfTenMultiplier>
                <espi:uom>72</espi:uom>
                <espi:currency>840</espi:currency>
              </espi:ReadingType>
            </atom:content>
          </atom:entry>
          <atom:entry>
            <atom:id>urn:uuid:mr-001</atom:id>
            <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01"/>
            <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/ReadingType/01"/>
            <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/IntervalBlock"/>
            <atom:content type="xml">
              <espi:MeterReading/>
            </atom:content>
          </atom:entry>
          <atom:entry>
            <atom:id>urn:uuid:ib-001</atom:id>
            <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/IntervalBlock/01"/>
            <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01"/>
            <atom:content type="xml">
              <espi:IntervalBlock>
                <espi:interval>
                  <espi:duration>{interval_duration}</espi:duration>
                  <espi:start>{interval_start}</espi:start>
                </espi:interval>
                <espi:IntervalReading>
                  <espi:value>{reading_value}</espi:value>
                </espi:IntervalReading>
              </espi:IntervalBlock>
            </atom:content>
          </atom:entry>
          {usage_point_block}
        </atom:feed>
    """)


def _parse_feed(xml_str: str) -> GreenButtonFeed:
    """Parse a GreenButtonFeed from XML string."""
    elem = ET.fromstring(xml_str.strip())
    return GreenButtonFeed(elem)


# ── Tests: to_usage_point() path (explicit UsagePoint in XML) ───────────────


class TestUsagePointWithMeterReading:
    """Tests for the to_usage_point() filter (lines 583-601 in espi.py).

    This is the path taken when the XML contains a UsagePoint entry
    with related MeterReading entries.
    """

    def test_hourly_electricity_accepted(self):
        """Hourly electricity (flowDirection=1, intervalLength=3600) should be included."""
        xml = _make_espi_xml(interval_length=3600, flow_direction=1, commodity=1)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) == 1

    def test_15min_electricity_accepted(self):
        """15-minute electricity (flowDirection=1, intervalLength=900) should be included."""
        xml = _make_espi_xml(interval_length=900, flow_direction=1, commodity=1)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) == 1

    def test_monthly_electricity_accepted(self):
        """Monthly electricity (flowDirection=1, intervalLength=2678400) should be included.

        DTE Energy provides monthly billing data with intervalLength=2678400 (~31 days).
        This was previously rejected by the < 86400 filter, causing zero sensors.
        """
        xml = _make_espi_xml(
            interval_length=2678400,
            flow_direction=1,
            commodity=1,
            interval_duration=2678400,
        )
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) == 1

    def test_daily_electricity_accepted(self):
        """Daily electricity (flowDirection=1, intervalLength=86400) should be included.

        Some utilities provide daily consumption summaries rather than hourly/15-min.
        """
        xml = _make_espi_xml(interval_length=86400, flow_direction=1, commodity=1)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) == 1

    def test_reverse_flow_electricity_rejected(self):
        """Electricity with flowDirection != 1 (e.g. 2=reverse) should be skipped."""
        xml = _make_espi_xml(interval_length=3600, flow_direction=2, commodity=1)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) == 0

    def test_daily_gas_accepted(self):
        """Daily gas (flowDirection=1, intervalLength=86400) should be included."""
        xml = _make_espi_xml(
            interval_length=86400,
            flow_direction=1,
            commodity=1,
            # ServiceCategory kind=1 signals gas in some feeds, but commodity in
            # ReadingType is what matters for the gas path. We test via the
            # UsagePoint's ServiceCategory by modifying the XML.
        )
        # For gas, we need ServiceCategory kind=1 (gas) in the UsagePoint
        # The test helper uses kind=0 (electricity) by default.
        # We'll build the XML manually for gas.
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <atom:feed xmlns:atom="http://www.w3.org/2005/Atom"
                       xmlns:espi="http://naesb.org/espi">
              <atom:entry>
                <atom:id>urn:uuid:rt-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/ReadingType/01"/>
                <atom:content type="xml">
                  <espi:ReadingType>
                    <espi:commodity>1</espi:commodity>
                    <espi:flowDirection>1</espi:flowDirection>
                    <espi:intervalLength>86400</espi:intervalLength>
                    <espi:powerOfTenMultiplier>-3</espi:powerOfTenMultiplier>
                    <espi:uom>72</espi:uom>
                    <espi:currency>840</espi:currency>
                  </espi:ReadingType>
                </atom:content>
              </atom:entry>
              <atom:entry>
                <atom:id>urn:uuid:mr-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/ReadingType/01"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/IntervalBlock"/>
                <atom:content type="xml">
                  <espi:MeterReading/>
                </atom:content>
              </atom:entry>
              <atom:entry>
                <atom:id>urn:uuid:ib-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/IntervalBlock/01"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01"/>
                <atom:content type="xml">
                  <espi:IntervalBlock>
                    <espi:interval>
                      <espi:duration>86400</espi:duration>
                      <espi:start>1719504000</espi:start>
                    </espi:interval>
                    <espi:IntervalReading>
                      <espi:value>1500</espi:value>
                    </espi:IntervalReading>
                  </espi:IntervalBlock>
                </atom:content>
              </atom:entry>
              <atom:entry>
                <atom:id>urn:uuid:up-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading"/>
                <atom:content type="xml">
                  <espi:UsagePoint>
                    <espi:ServiceCategory><espi:kind>1</espi:kind></espi:ServiceCategory>
                  </espi:UsagePoint>
                </atom:content>
              </atom:entry>
            </atom:feed>
        """)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        # Gas with daily intervals should be accepted
        assert len(usage_points[0].meter_readings) >= 1

    def test_hourly_gas_rejected(self):
        """Hourly gas (flowDirection=1, intervalLength=3600) should be skipped.

        Gas data uses daily intervals; hourly gas readings are likely net metering
        or other artifacts that should not create gas sensors.
        """
        xml = textwrap.dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <atom:feed xmlns:atom="http://www.w3.org/2005/Atom"
                       xmlns:espi="http://naesb.org/espi">
              <atom:entry>
                <atom:id>urn:uuid:rt-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/ReadingType/01"/>
                <atom:content type="xml">
                  <espi:ReadingType>
                    <espi:commodity>1</espi:commodity>
                    <espi:flowDirection>1</espi:flowDirection>
                    <espi:intervalLength>3600</espi:intervalLength>
                    <espi:powerOfTenMultiplier>-3</espi:powerOfTenMultiplier>
                    <espi:uom>72</espi:uom>
                    <espi:currency>840</espi:currency>
                  </espi:ReadingType>
                </atom:content>
              </atom:entry>
              <atom:entry>
                <atom:id>urn:uuid:mr-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/ReadingType/01"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/IntervalBlock"/>
                <atom:content type="xml">
                  <espi:MeterReading/>
                </atom:content>
              </atom:entry>
              <atom:entry>
                <atom:id>urn:uuid:ib-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01/IntervalBlock/01"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading/01"/>
                <atom:content type="xml">
                  <espi:IntervalBlock>
                    <espi:interval>
                      <espi:duration>3600</espi:duration>
                      <espi:start>1719504000</espi:start>
                    </espi:interval>
                    <espi:IntervalReading>
                      <espi:value>1500</espi:value>
                    </espi:IntervalReading>
                  </espi:IntervalBlock>
                </atom:content>
              </atom:entry>
              <atom:entry>
                <atom:id>urn:uuid:up-001</atom:id>
                <atom:link rel="self" href="RetailCustomer/cust001/UsagePoint/up001"/>
                <atom:link rel="related" href="RetailCustomer/cust001/UsagePoint/up001/MeterReading"/>
                <atom:content type="xml">
                  <espi:UsagePoint>
                    <espi:ServiceCategory><espi:kind>1</espi:kind></espi:ServiceCategory>
                  </espi:UsagePoint>
                </atom:content>
              </atom:entry>
            </atom:feed>
        """)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        # Gas with hourly intervals should be skipped
        assert len(usage_points[0].meter_readings) == 0


# ── Tests: _create_default_usage_point_with_consumed_energy() path ──────────


class TestDefaultUsagePoint:
    """Tests for the fallback path when no UsagePoint entry exists in XML.

    This exercises the filter in _create_default_usage_point_with_consumed_energy()
    (lines 162-203 in espi.py).
    """

    def test_hourly_electricity_accepted_default(self):
        """Hourly electricity should be included in default usage point path."""
        xml = _make_espi_xml(interval_length=3600, flow_direction=1, include_usage_point=False)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        # Default usage point should have meter readings
        assert len(usage_points[0].meter_readings) >= 1

    def test_monthly_electricity_accepted_default(self):
        """Monthly electricity should be included in default usage point path.

        Previously skipped because intervalLength >= 86400 was treated as
        a 'daily summary' to be excluded.
        """
        xml = _make_espi_xml(
            interval_length=2678400,
            flow_direction=1,
            include_usage_point=False,
            interval_duration=2678400,
        )
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) >= 1

    def test_daily_electricity_accepted_default(self):
        """Daily electricity (intervalLength=86400) should be included in default path."""
        xml = _make_espi_xml(interval_length=86400, flow_direction=1, include_usage_point=False)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        assert len(usage_points) == 1
        assert len(usage_points[0].meter_readings) >= 1

    def test_reverse_flow_rejected_default(self):
        """Non-consumption flowDirection should be rejected in default path."""
        xml = _make_espi_xml(interval_length=3600, flow_direction=2, include_usage_point=False)
        feed = _parse_feed(xml)
        usage_points = feed.to_usage_points()
        # Default usage point is still created, but with no meter readings
        # (or the default empty meter reading)
        total_readings = sum(len(mr.interval_blocks) for mr in usage_points[0].meter_readings)
        assert total_readings == 0
