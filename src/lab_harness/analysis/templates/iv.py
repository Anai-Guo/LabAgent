"""IV (Current-Voltage) data analysis."""

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

data_path = Path("{{DATA_PATH}}")
output_dir = Path("{{OUTPUT_DIR}}")
output_dir.mkdir(parents=True, exist_ok=True)

# comment='#' skips the SIMULATED-data metadata header written by flow.py.
df = pd.read_csv(data_path, comment="#")
# Prefer labelled columns; fall back to positional for legacy single-column CSVs.
x_col = "Source Current" if "Source Current" in df.columns else df.columns[0]
y_col = "Voltage" if "Voltage" in df.columns else df.columns[1]
current = df[x_col].to_numpy()  # mA
voltage = df[y_col].to_numpy()  # V

# Linear fit for resistance
coeffs = np.polyfit(current * 1e-3, voltage, 1)  # convert mA to A
R = coeffs[0]

fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(current, voltage * 1e3, "ro-", markersize=3, linewidth=1)
ax.set_xlabel("Current (mA)", fontsize=14)
ax.set_ylabel("Voltage (mV)", fontsize=14)
ax.set_title("I-V Characteristic", fontsize=16)
ax.text(
    0.05,
    0.95,
    f"R = {R:.2f} \u03a9",
    transform=ax.transAxes,
    fontsize=12,
    verticalalignment="top",
    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
)
ax.grid(True, alpha=0.3)
fig.tight_layout()
# Diagonal watermark so nobody confuses simulated output for real data.
fig.text(
    0.5,
    0.5,
    "SIMULATED DATA\n(LabAgent)",
    fontsize=40,
    color="red",
    alpha=0.15,
    ha="center",
    va="center",
    rotation=30,
    transform=fig.transFigure,
    zorder=0,
)
fig.savefig(output_dir / "iv_plot.png", dpi=300)
fig.savefig(output_dir / "iv_plot.pdf")
plt.close()
print(f"R = {R:.6e} Ohm")
