"""Online manual lookup tool.

Implements the mandatory "look up the manual first" rule from AGENTS.md
and AI_GUIDE.md: when the AI meets an unknown instrument or interface,
this tool returns a ranked list of authoritative documentation URLs and
known open-source driver hits.

Uses stdlib only (urllib) — no new dependencies. Falls back gracefully
when the network is unavailable, returning the curated hint list so the
caller still has something actionable.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from pydantic import BaseModel, Field

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult

# Manufacturer -> (documentation portal, Python driver landing page if any).
# Curated from research; extend as we add new vendors.
MANUFACTURER_HINTS: dict[str, dict[str, str]] = {
    "keithley": {
        "docs": "https://www.tek.com/en/support/manuals",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/keithley/",
    },
    "tektronix": {
        "docs": "https://www.tek.com/en/support/manuals",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/tektronix/",
    },
    "keysight": {
        "docs": "https://www.keysight.com/us/en/support.html",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/keysight/",
    },
    "agilent": {
        "docs": "https://www.keysight.com/us/en/support.html",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/agilent/",
    },
    "rohde & schwarz": {
        "docs": "https://www.rohde-schwarz.com/us/driver-pages/remote-control/drivers-6_98785.html",
        "driver": "https://github.com/Rohde-Schwarz/RsInstrument",
    },
    "rigol": {
        "docs": "https://www.rigolna.com/products/",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/rigol/",
    },
    "stanford research": {
        "docs": "https://www.thinksrs.com/downloads/soft.html",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/srs/",
    },
    "lake shore": {
        "docs": "https://www.lakeshore.com/support/software-firmware",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/lakeshore/",
    },
    "biologic": {
        "docs": "https://www.biologic.net/support-software/",
        "driver": "https://github.com/bicarlsen/easy-biologic",
    },
    "gamry": {
        "docs": "https://www.gamry.com/support/technical-support/software/",
        "driver": "https://github.com/GamryElectrochem",
    },
    "ch instruments": {
        "docs": "https://www.chinstruments.com/software.shtml",
        "driver": "https://github.com/jmarrec/hardpotato",
    },
    "palmsens": {
        "docs": "https://www.palmsens.com/knowledgebase/",
        "driver": "https://github.com/MStoelzle/PalmSensSDK",
    },
    "metrohm autolab": {
        "docs": "https://www.metrohm.com/en/products/electrochemistry/autolab.html",
        "driver": "",
    },
    "thorlabs": {
        "docs": "https://www.thorlabs.com/navigation.cfm?guide_id=2060",
        "driver": "https://pylablib.readthedocs.io/en/latest/devices/Thorlabs.html",
    },
    "zurich instruments": {
        "docs": "https://docs.zhinst.com/",
        "driver": "https://github.com/zhinst/zhinst-toolkit",
    },
    "mettler toledo": {
        "docs": "https://www.mt.com/us/en/home/library.html",
        "driver": "",
    },
    "ohaus": {
        "docs": "https://us.ohaus.com/en-US/Support",
        "driver": "",
    },
    "alicat": {
        "docs": "https://www.alicat.com/documents/",
        "driver": "https://github.com/numat/alicat",
    },
    "mks": {
        "docs": "https://www.mksinst.com/c/technical-support",
        "driver": "",
    },
    "oxford instruments": {
        "docs": "https://nanoscience.oxinst.com/support",
        "driver": "https://github.com/AlanGiles/pyOxford",
    },
    "quantum design": {
        "docs": "https://www.qdusa.com/products/",
        "driver": "https://pypi.org/project/MultiPyVu/",
    },
    "national instruments": {
        "docs": "https://www.ni.com/docs/en-US/bundle/ni-daqmx/",
        "driver": "https://nidaqmx-python.readthedocs.io/",
    },
    "ni": {
        "docs": "https://www.ni.com/docs/en-US/bundle/ni-daqmx/",
        "driver": "https://nidaqmx-python.readthedocs.io/",
    },
    "molecular devices": {
        "docs": "https://www.moleculardevices.com/support",
        "driver": "",
    },
    "bmg labtech": {
        "docs": "https://www.bmglabtech.com/en/support/",
        "driver": "",
    },
    "bk precision": {
        "docs": "https://www.bkprecision.com/support/downloads.html",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/bkprecision/",
    },
    "anritsu": {
        "docs": "https://www.anritsu.com/en-us/test-measurement/support/downloads",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/anritsu/",
    },
    "hp": {
        "docs": "https://www.keysight.com/us/en/support.html",
        "driver": "https://pymeasure.readthedocs.io/en/latest/api/instruments/hp/",
    },
}

# Lightweight DuckDuckGo HTML endpoint - no API key, no JS rendering needed.
_DDG_URL = "https://duckduckgo.com/html/?q={query}"
_USER_AGENT = "Mozilla/5.0 (compatible; LabAgent-ManualLookup/0.1)"


def _detect_manufacturer(make: str) -> dict[str, str] | None:
    m = make.strip().lower()
    if not m:
        return None
    for key, hints in MANUFACTURER_HINTS.items():
        if key in m or m in key:
            return {"manufacturer": key, **hints}
    return None


def _ddg_search(query: str, limit: int = 5, timeout: float = 6.0) -> list[dict[str, str]]:
    """Best-effort DuckDuckGo HTML scrape. Returns [] on any network error."""
    url = _DDG_URL.format(query=urllib.parse.quote_plus(query))
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return []

    # DDG HTML links look like: <a ... class="result__a" href="URL">TEXT</a>
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    results: list[dict[str, str]] = []
    for m in pattern.finditer(html):
        raw_href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()

        # DDG wraps outbound links via /l/?uddg=<encoded>
        if raw_href.startswith("//duckduckgo.com/l/") or raw_href.startswith("/l/"):
            parsed = urllib.parse.urlparse(raw_href)
            qs = urllib.parse.parse_qs(parsed.query)
            if "uddg" in qs:
                raw_href = urllib.parse.unquote(qs["uddg"][0])

        if raw_href.startswith("//"):
            raw_href = "https:" + raw_href
        results.append({"title": title, "url": raw_href})
        if len(results) >= limit:
            break
    return results


class ManualLookupInput(BaseModel):
    make: str = Field(
        description="Manufacturer name as found in *IDN? response or on the front panel.",
    )
    model: str = Field(
        description="Model number as found in *IDN? response or on the front panel.",
    )
    interface_or_topic: str = Field(
        default="",
        description=(
            "Optional: the specific thing you need (e.g. 'SCPI command reference', "
            "'IEEE-488 bus address', 'Python driver', 'trigger options')."
        ),
    )
    search_web: bool = Field(
        default=True,
        description=(
            "If True (default), perform a live DuckDuckGo search in addition to "
            "returning curated manufacturer hints. Set False for offline hint-only mode."
        ),
    )


class ManualLookupTool(BaseTool):
    name = "manual_lookup"
    description = (
        "Look up the programming manual, command reference, or open-source Python "
        "driver for an unknown instrument. ALWAYS call this BEFORE classifying an "
        "unfamiliar instrument or writing SCPI commands from memory. Combines a "
        "curated manufacturer documentation index with a live web search."
    )
    input_model = ManualLookupInput

    async def execute(self, arguments: ManualLookupInput, context: ToolContext) -> ToolResult:
        make = arguments.make.strip()
        model = arguments.model.strip()
        topic = arguments.interface_or_topic.strip() or "programming manual"

        hint = _detect_manufacturer(make)
        queries = [
            f'"{make}" "{model}" {topic}',
            f'"{make} {model}" SCPI command reference',
            f"{make} {model} site:github.com python driver",
            f"{make} {model} pymeasure OR pylablib OR PyExpLabSys",
        ]

        web_hits: list[dict[str, str]] = []
        if arguments.search_web:
            seen: set[str] = set()
            for q in queries:
                for hit in _ddg_search(q, limit=5):
                    u = hit["url"]
                    if u in seen:
                        continue
                    seen.add(u)
                    web_hits.append({**hit, "query": q})
                if len(web_hits) >= 12:
                    break

        response: dict[str, Any] = {
            "make": make,
            "model": model,
            "topic": topic,
            "manufacturer_hints": hint,
            "suggested_queries": queries,
            "web_results": web_hits,
            "next_steps": [
                "1. Open the manufacturer docs link above and locate the model's programming manual PDF.",
                "2. Skim the 'Remote Interface', 'SCPI commands', or 'IEEE-488 "
                "common commands' chapter for the verbs you need.",
                "3. Check the driver link — if a pymeasure/pylablib wrapper exists, "
                "reuse it instead of hand-rolling SCPI.",
                "4. Cite the manual URL in any skill or driver code you produce.",
            ],
        }

        summary_parts = [f"Manual lookup: {make} {model} ({topic})"]
        if hint:
            summary_parts.append(f"Vendor hint: {hint['manufacturer']} -> {hint.get('docs', 'n/a')}")
        summary_parts.append(f"Web results: {len(web_hits)} hit(s) from DuckDuckGo")

        return ToolResult(
            output="\n".join(summary_parts) + "\n\n" + json.dumps(response, indent=2),
            metadata={
                "web_hits": len(web_hits),
                "vendor_matched": bool(hint),
            },
        )
