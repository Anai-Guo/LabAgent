"""Tests for the reference instrument procedure catalog."""

import string

import pytest

from lab_harness.reference.instrument_procedures import PROCEDURES, get_procedure, list_procedures

SEQUENCE_KEYS = ("init", "measure", "shutdown")

# Placeholders that are filled per sweep step rather than from the defaults,
# e.g. IV_K2400 steps ``current`` from ``current_start`` to ``current_stop``.
SWEEP_VARIABLES = {"IV_K2400": {"current"}}


def _placeholders(line: str) -> set[str]:
    return {field for _, field, _, _ in string.Formatter().parse(line) if field}


def test_list_procedures_matches_catalog():
    names = list_procedures()
    assert names == list(PROCEDURES)
    assert len(names) == len(set(names))
    assert "IV_K2400" in names


def test_get_procedure_returns_catalog_entry():
    assert get_procedure("IV_K2400") is PROCEDURES["IV_K2400"]


def test_get_procedure_unknown_returns_none():
    assert get_procedure("NO_SUCH_PROCEDURE") is None
    assert get_procedure("iv_k2400") is None  # lookup is case-sensitive


@pytest.mark.parametrize("name", list(PROCEDURES))
def test_procedure_structure(name):
    proc = PROCEDURES[name]
    assert set(proc) <= {"description", "parameters", *SEQUENCE_KEYS}
    assert isinstance(proc["description"], str) and proc["description"].strip()
    # init may be empty (e.g. balances / DAQ tasks need no setup), but must exist
    assert isinstance(proc["init"], list)
    assert proc["init"] or proc.get("measure"), "procedure has no commands at all"
    for key in SEQUENCE_KEYS:
        if key in proc:
            assert isinstance(proc[key], list)
            assert all(isinstance(line, str) and line for line in proc[key])
    for key in ("measure", "shutdown"):
        if key in proc:
            assert proc[key], f"{key} sequence is present but empty"
    params = proc.get("parameters", {})
    assert isinstance(params, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in params.items())


@pytest.mark.parametrize("name", list(PROCEDURES))
def test_placeholders_have_defaults(name):
    """Every ``{placeholder}`` must be a default parameter or a known sweep variable."""
    proc = PROCEDURES[name]
    fields = set()
    for key in SEQUENCE_KEYS:
        for line in proc.get(key, []):
            fields |= _placeholders(line)
    allowed = set(proc.get("parameters", {})) | SWEEP_VARIABLES.get(name, set())
    assert fields <= allowed, f"{name} has placeholders without defaults: {sorted(fields - allowed)}"


def test_sequences_render_with_defaults():
    proc = get_procedure("IV_K2400")
    values = {**proc["parameters"], "current": proc["parameters"]["current_start"]}
    rendered = [line.format(**values) for line in proc["init"] + proc["measure"]]
    assert ":SENS:VOLT:PROT 20" in rendered
    assert ":SOUR:CURR -1e-3" in rendered
    assert not any("{" in line for line in rendered)


def test_cli_procedures_lists_every_entry(capsys):
    from lab_harness.cli import cmd_procedures

    cmd_procedures(None, None)
    out = capsys.readouterr().out
    for name, proc in PROCEDURES.items():
        assert name in out
        assert proc["description"] in out
    assert "compliance=20" in out
