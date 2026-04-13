"""Tests for the analysis module."""
from __future__ import annotations

from pathlib import Path

import pytest

from lab_harness.analysis.analyzer import Analyzer


class TestAnalyzer:
    def test_generate_ahe_script(self):
        """Generates valid Python script with data path substituted for AHE."""
        data = Path("/data/ahe_run1.csv")
        analyzer = Analyzer()
        script = analyzer.generate_script(
            data_path=data,
            measurement_type="AHE",
        )
        # Placeholder replaced with actual path (str() uses OS separators)
        assert "{{DATA_PATH}}" not in script
        assert str(data) in script
        # Template content is present
        assert "Anomalous Hall Effect" in script or "R_AHE" in script

    def test_generate_iv_script(self):
        """Generates valid Python script with data path substituted for IV."""
        data = Path("/data/iv_curve.csv")
        analyzer = Analyzer()
        script = analyzer.generate_script(
            data_path=data,
            measurement_type="IV",
        )
        assert "{{DATA_PATH}}" not in script
        assert str(data) in script
        assert "{{OUTPUT_DIR}}" not in script

    def test_output_dir_substituted(self):
        """OUTPUT_DIR placeholder is replaced in the generated script."""
        out = Path("/results/analysis")
        analyzer = Analyzer(output_dir=out)
        script = analyzer.generate_script(
            data_path=Path("/data/test.csv"),
            measurement_type="AHE",
        )
        assert "{{OUTPUT_DIR}}" not in script
        assert str(out) in script

    def test_unknown_type_raises(self):
        """Unknown measurement type raises FileNotFoundError."""
        analyzer = Analyzer()
        with pytest.raises(FileNotFoundError, match="No analysis template"):
            analyzer.generate_script(
                data_path=Path("/data/test.csv"),
                measurement_type="NONEXISTENT",
            )

    def test_save_script(self, tmp_path: Path):
        """Saves script to output dir and returns the path."""
        analyzer = Analyzer(output_dir=tmp_path)
        script_content = "print('hello')\n"
        result = analyzer.save_script(script_content, "test_run")

        assert result == tmp_path / "test_run_analysis.py"
        assert result.exists()
        assert result.read_text() == script_content

    def test_save_script_creates_dir(self, tmp_path: Path):
        """save_script creates the output directory if it does not exist."""
        out = tmp_path / "nested" / "output"
        analyzer = Analyzer(output_dir=out)
        result = analyzer.save_script("x = 1\n", "nested_run")
        assert result.exists()
        assert result.parent == out
