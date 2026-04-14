"""RT (Resistance vs Temperature) data analysis."""

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
x_col = "Temperature" if "Temperature" in df.columns else df.columns[0]
y_col = "V_xx" if "V_xx" in df.columns else df.columns[1]
temp = df[x_col].to_numpy()  # K
v_xx = df[y_col].to_numpy()  # V
I_source = 1e-5  # 10 uA default for RT
R = v_xx / I_source

# Calculate dR/dT for transition detection
dRdT = np.gradient(R, temp)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10), sharex=True)
ax1.plot(temp, R, "b-", linewidth=1.5)
ax1.set_ylabel("R (\u03a9)", fontsize=14)
ax1.set_title("Resistance vs Temperature", fontsize=16)
ax1.grid(True, alpha=0.3)

ax2.plot(temp, dRdT, "r-", linewidth=1)
ax2.set_xlabel("Temperature (K)", fontsize=14)
ax2.set_ylabel("dR/dT (\u03a9/K)", fontsize=14)
ax2.grid(True, alpha=0.3)

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
fig.savefig(output_dir / "rt_plot.png", dpi=300)
fig.savefig(output_dir / "rt_plot.pdf")
plt.close()
print(f"R(min) = {np.min(R):.4f} Ohm at T = {temp[np.argmin(R)]:.1f} K")
print(f"R(max) = {np.max(R):.4f} Ohm at T = {temp[np.argmax(R)]:.1f} K")
