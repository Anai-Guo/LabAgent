"""Data export utilities for measurement results.

Supports CSV (enhanced), JSON, and HDF5 (optional) formats.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExportConfig:
    """Configuration for data export."""

    output_dir: Path = Path("./data/exports")
    format: str = "csv"  # csv, json, hdf5
    include_metadata: bool = True
    timestamp_prefix: bool = True


class DataExporter:
    """Export measurement data in multiple formats."""

    def __init__(self, config: ExportConfig | None = None):
        self.config = config or ExportConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def _make_filename(self, name: str, ext: str) -> Path:
        if self.config.timestamp_prefix:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            return self.config.output_dir / f"{ts}_{name}.{ext}"
        return self.config.output_dir / f"{name}.{ext}"

    def export_csv(
        self,
        data: list[dict[str, Any]],
        name: str = "measurement",
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Export data as CSV with optional metadata header."""
        path = self._make_filename(name, "csv")

        with open(path, "w", newline="", encoding="utf-8") as f:
            # Write metadata as comments
            if metadata and self.config.include_metadata:
                for key, val in metadata.items():
                    f.write(f"# {key}: {val}\n")
                f.write(f"# exported: {datetime.now().isoformat()}\n")
                f.write("#\n")

            if not data:
                return path

            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

        logger.info("Exported CSV: %s (%d rows)", path, len(data))
        return path

    def export_json(
        self,
        data: list[dict[str, Any]],
        name: str = "measurement",
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Export data as JSON with metadata."""
        path = self._make_filename(name, "json")

        output = {
            "metadata": {
                **(metadata or {}),
                "exported": datetime.now().isoformat(),
                "points": len(data),
            },
            "data": data,
        }

        path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        logger.info("Exported JSON: %s (%d rows)", path, len(data))
        return path

    def export_hdf5(
        self,
        data: list[dict[str, Any]],
        name: str = "measurement",
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Export data as HDF5 (requires h5py)."""
        try:
            import h5py
            import numpy as np
        except ImportError:
            raise ImportError("HDF5 export requires h5py: pip install h5py")

        path = self._make_filename(name, "h5")

        with h5py.File(path, "w") as f:
            # Store metadata
            if metadata:
                for key, val in metadata.items():
                    f.attrs[str(key)] = str(val)
            f.attrs["exported"] = datetime.now().isoformat()

            # Store data columns
            if data:
                for key in data[0].keys():
                    values = [row.get(key, 0) for row in data]
                    try:
                        f.create_dataset(key, data=np.array(values, dtype=float))
                    except (ValueError, TypeError):
                        # String data
                        f.create_dataset(key, data=[str(v) for v in values])

        logger.info("Exported HDF5: %s (%d rows)", path, len(data))
        return path

    def export(
        self,
        data: list[dict[str, Any]],
        name: str = "measurement",
        metadata: dict[str, Any] | None = None,
        fmt: str | None = None,
    ) -> Path:
        """Export data in the configured format."""
        fmt = fmt or self.config.format

        if fmt == "csv":
            return self.export_csv(data, name, metadata)
        elif fmt == "json":
            return self.export_json(data, name, metadata)
        elif fmt == "hdf5":
            return self.export_hdf5(data, name, metadata)
        else:
            raise ValueError(f"Unknown format: {fmt}. Supported: csv, json, hdf5")
