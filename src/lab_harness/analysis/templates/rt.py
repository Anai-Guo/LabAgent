"""RT (Resistance vs Temperature) data analysis."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

data_path = Path("{{DATA_PATH}}")
output_dir = Path("{{OUTPUT_DIR}}")
output_dir.mkdir(parents=True, exist_ok=True)

data = np.genfromtxt(data_path, delimiter=",", skip_header=1, names=True)
temp = data[data.dtype.names[0]]  # K
v_xx = data[data.dtype.names[1]]  # V
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
fig.savefig(output_dir / "rt_plot.png", dpi=300)
fig.savefig(output_dir / "rt_plot.pdf")
plt.close()
print(f"R(min) = {np.min(R):.4f} Ohm at T = {temp[np.argmin(R)]:.1f} K")
print(f"R(max) = {np.max(R):.4f} Ohm at T = {temp[np.argmax(R)]:.1f} K")
