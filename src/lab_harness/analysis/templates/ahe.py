"""AHE (Anomalous Hall Effect) data analysis."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

data_path = Path("{{DATA_PATH}}")
output_dir = Path("{{OUTPUT_DIR}}")
output_dir.mkdir(parents=True, exist_ok=True)

# Load data
data = np.genfromtxt(data_path, delimiter=",", skip_header=1, names=True)
field = data[data.dtype.names[0]]  # First column: field (Oe)
v_xy = data[data.dtype.names[1]]  # Second column: V_xy (V)

# Calculate Hall resistance (assuming source current from filename or default)
I_source = 1e-4  # 100 uA default
R_xy = v_xy / I_source

# Extract parameters
R_AHE = (np.max(R_xy) - np.min(R_xy)) / 2
# Find coercive field from zero-crossings
sign_changes = np.where(np.diff(np.sign(R_xy - np.mean(R_xy))))[0]
H_c = np.mean(np.abs(field[sign_changes])) if len(sign_changes) > 0 else 0

# Plot
fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(field, R_xy * 1e3, "b-", linewidth=1.5)
ax.set_xlabel("Magnetic Field (Oe)", fontsize=14)
ax.set_ylabel("R$_{xy}$ (m$\\Omega$)", fontsize=14)
ax.set_title("Anomalous Hall Effect", fontsize=16)
ax.text(
    0.05,
    0.95,
    f"R_AHE = {R_AHE * 1e3:.2f} m\u03a9\nH_c = {H_c:.0f} Oe",
    transform=ax.transAxes,
    fontsize=12,
    verticalalignment="top",
    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
)
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(output_dir / "ahe_plot.png", dpi=300)
fig.savefig(output_dir / "ahe_plot.pdf")
plt.close()

print(f"R_AHE = {R_AHE:.6e} Ohm")
print(f"H_c = {H_c:.1f} Oe")
print(f"Figures saved to {output_dir}")
