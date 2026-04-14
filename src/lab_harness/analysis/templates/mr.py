"""MR (Magnetoresistance) data analysis."""

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
x_col = "Magnetic Field" if "Magnetic Field" in df.columns else df.columns[0]
y_col = "V_xx" if "V_xx" in df.columns else df.columns[1]
field = df[x_col].to_numpy()
v_xx = df[y_col].to_numpy()
I_source = 1e-4
R_xx = v_xx / I_source

R_min, R_max = np.min(R_xx), np.max(R_xx)
MR_ratio = (R_max - R_min) / R_min * 100

fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(field, R_xx, "b-", linewidth=1.5)
ax.set_xlabel("Magnetic Field (Oe)", fontsize=14)
ax.set_ylabel("R$_{xx}$ (\u03a9)", fontsize=14)
ax.set_title("Magnetoresistance", fontsize=16)
ax.text(
    0.05,
    0.95,
    f"MR = {MR_ratio:.2f}%",
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
fig.savefig(output_dir / "mr_plot.png", dpi=300)
fig.savefig(output_dir / "mr_plot.pdf")
plt.close()
print(f"MR ratio = {MR_ratio:.2f}%")
