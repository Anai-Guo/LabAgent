"""MR (Magnetoresistance) data analysis."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

data_path = Path("{{DATA_PATH}}")
output_dir = Path("{{OUTPUT_DIR}}")
output_dir.mkdir(parents=True, exist_ok=True)

data = np.genfromtxt(data_path, delimiter=",", skip_header=1, names=True)
field = data[data.dtype.names[0]]
v_xx = data[data.dtype.names[1]]
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
fig.savefig(output_dir / "mr_plot.png", dpi=300)
fig.savefig(output_dir / "mr_plot.pdf")
plt.close()
print(f"MR ratio = {MR_ratio:.2f}%")
