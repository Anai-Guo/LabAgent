# Safety System

LabAgent implements a 3-tier safety system to protect instruments and samples. Actions are classified as **block** (never allowed), **confirm** (requires user approval), or **allow** (safe to execute automatically).

Safety boundaries are defined per instrument and per measurement type, with hardware limits that cannot be overridden by AI suggestions.
