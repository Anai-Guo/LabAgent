"""Tests for the manual_lookup harness tool.

The tool has two branches:
1. Offline hint-only mode (search_web=False) — returns curated manufacturer
   documentation URLs even without network.
2. Online search mode — adds DuckDuckGo web hits. Under pytest we mock the
   network to avoid flakiness and to keep CI offline-clean.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lab_harness.harness.tools.base import ToolContext
from lab_harness.harness.tools.manual_lookup_tool import (
    MANUFACTURER_HINTS,
    ManualLookupInput,
    ManualLookupTool,
    _detect_manufacturer,
)


def test_detect_manufacturer_known_vendor():
    """Manufacturer detection is case-insensitive and matches loose substrings."""
    assert _detect_manufacturer("Keithley") is not None
    assert _detect_manufacturer("KEITHLEY") is not None
    assert _detect_manufacturer("Thorlabs Inc.") is not None
    assert _detect_manufacturer("BioLogic Science Instruments") is not None


def test_detect_manufacturer_unknown_vendor():
    """Unknown vendors return None so the tool falls through to web search only."""
    assert _detect_manufacturer("ACME Widget Co.") is None
    assert _detect_manufacturer("") is None
    assert _detect_manufacturer("   ") is None


def test_manufacturer_hints_have_urls():
    """Every curated vendor hint must have at least a `docs` URL."""
    for vendor, hints in MANUFACTURER_HINTS.items():
        assert hints.get("docs"), f"Missing docs URL for {vendor}"


async def test_offline_mode_returns_hints_without_network():
    """With search_web=False, the tool must not touch the network."""
    tool = ManualLookupTool()

    # Patch urlopen to raise if accidentally called
    with patch(
        "lab_harness.harness.tools.manual_lookup_tool.urllib.request.urlopen",
        side_effect=AssertionError("should not be called in offline mode"),
    ):
        result = await tool.execute(
            ManualLookupInput(
                make="Keithley",
                model="2400",
                interface_or_topic="SCPI reference",
                search_web=False,
            ),
            ToolContext(),
        )

    assert not result.is_error
    assert "2400" in result.output
    assert "keithley" in result.output.lower()
    assert result.metadata["web_hits"] == 0
    assert result.metadata["vendor_matched"] is True


async def test_online_mode_handles_network_failure_gracefully():
    """If urlopen raises, the tool still returns curated hints without crashing."""
    import urllib.error

    tool = ManualLookupTool()

    with patch(
        "lab_harness.harness.tools.manual_lookup_tool.urllib.request.urlopen",
        side_effect=urllib.error.URLError("no network"),
    ):
        result = await tool.execute(
            ManualLookupInput(make="BioLogic", model="SP-200"),
            ToolContext(),
        )

    assert not result.is_error
    assert "SP-200" in result.output
    assert result.metadata["web_hits"] == 0
    assert result.metadata["vendor_matched"] is True


async def test_online_mode_parses_ddg_html():
    """Mock DuckDuckGo HTML to verify the scraper extracts links and titles."""
    fake_html = """
    <html><body>
      <div class="result">
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fmanual.pdf">
          Keysight 33622A Programming Manual
        </a>
      </div>
      <div class="result">
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Ffoo%2Fbar">
          github.com/foo/bar — Python driver for 33622A
        </a>
      </div>
    </body></html>
    """

    class _FakeResponse:
        def __init__(self, body: str):
            self._body = body.encode("utf-8")

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    tool = ManualLookupTool()
    with patch(
        "lab_harness.harness.tools.manual_lookup_tool.urllib.request.urlopen",
        return_value=_FakeResponse(fake_html),
    ):
        result = await tool.execute(
            ManualLookupInput(make="Keysight", model="33622A"),
            ToolContext(),
        )

    assert not result.is_error
    assert result.metadata["web_hits"] > 0
    # URL unescape should have worked
    assert "https://example.com/manual.pdf" in result.output
    assert "https://github.com/foo/bar" in result.output


async def test_unknown_vendor_still_produces_usable_output():
    """Even with no vendor match, suggested_queries must be present."""
    tool = ManualLookupTool()

    with patch(
        "lab_harness.harness.tools.manual_lookup_tool.urllib.request.urlopen",
        side_effect=OSError("offline"),
    ):
        result = await tool.execute(
            ManualLookupInput(
                make="ObscureVendor",
                model="X-1000",
                search_web=True,
            ),
            ToolContext(),
        )

    assert not result.is_error
    assert result.metadata["vendor_matched"] is False
    assert "X-1000" in result.output
    assert "suggested_queries" in result.output


def test_tool_schema_exports():
    """The tool should produce a valid OpenAI-function-style schema."""
    tool = ManualLookupTool()
    schema = tool.to_api_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "manual_lookup"
    props = schema["function"]["parameters"]["properties"]
    assert "make" in props
    assert "model" in props
    assert "search_web" in props


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
