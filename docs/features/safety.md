# Safety System

LabAgent implements a three-tier safety architecture to prevent instrument damage and sample destruction. Every measurement plan is validated against configurable safety boundaries before execution. The system combines deterministic limit checking with optional AI-powered contextual advice.

## Three-Tier Safety Model

### Tier 1: Absolute Limits (BLOCK)

Absolute limits are hard boundaries that can **never** be exceeded, regardless of user intent or AI suggestions. If any parameter violates an absolute limit, the plan is blocked and cannot be executed.

Default absolute limits (configurable in `configs/default_safety.yaml`):

| Parameter | Default Limit | Description |
|-----------|--------------|-------------|
| `abs_max_current_a` | 10.0 A | Maximum source current |
| `abs_max_voltage_v` | 1000.0 V | Maximum voltage |
| `abs_max_field_oe` | 50,000 Oe | Maximum magnetic field |
| `abs_max_temperature_k` | 500 K | Maximum temperature |
| `abs_max_pulse_width_s` | 10.0 s | Maximum pulse duration |

These limits are checked against both the plan's declared maximums and the actual sweep ranges. For example, if a current sweep goes from -5 mA to +5 mA but the unit is milliamps, the checker converts to amps before comparing.

### Tier 2: Warning Thresholds (REQUIRE_CONFIRM)

Warning thresholds flag parameters that are within absolute limits but unusually high. Plans triggering warnings require explicit operator confirmation before proceeding.

Default warning thresholds:

| Parameter | Default Threshold | Description |
|-----------|------------------|-------------|
| `warn_current_a` | 100 mA | High current warning |
| `warn_voltage_v` | 50 V | High voltage warning |
| `warn_field_oe` | 20,000 Oe | High field warning |
| `warn_temperature_k` | 350 K | High temperature warning |

Warnings are only evaluated when no absolute limit violations exist (Tier 1 takes precedence).

### Tier 3: Consistency Checks (ALLOW with caveats)

Sanity checks catch common parameter mistakes:

- **Zero step size** -- sweep will produce only one data point
- **Excessive point count** -- plans with >10,000 points are flagged as potentially very long-running

## Safety Policy Configuration

Safety limits are defined in `configs/default_safety.yaml`:

```yaml
# Absolute limits (hard block)
abs_max_current_a: 10.0       # 10 A
abs_max_voltage_v: 1000.0     # 1 kV
abs_max_field_oe: 50000.0     # 50 kOe
abs_max_temperature_k: 500.0  # 500 K
abs_max_pulse_width_s: 10.0   # 10 s

# Warning thresholds (require confirmation)
warn_current_a: 0.1           # 100 mA
warn_voltage_v: 50.0          # 50 V
warn_field_oe: 20000.0        # 20 kOe
warn_temperature_k: 350.0     # 350 K
```

You can create a custom safety policy file and load it:

```python
from lab_harness.planning.boundary_checker import load_safety_policy, check_boundaries

policy = load_safety_policy(Path("my_lab_safety.yaml"))
result = check_boundaries(plan, policy=policy)
```

## Validation Results

The `check_boundaries()` function returns a `ValidationResult` with:

- **decision** -- one of `ALLOW`, `REQUIRE_CONFIRM`, or `BLOCK`
- **violations** -- list of `BoundaryViolation` objects (parameter, limit, requested value, severity, message)
- **warnings** -- list of warning message strings
- **ai_advice** -- optional AI-generated safety advice (see below)

```python
from lab_harness.planning.boundary_checker import check_boundaries

result = check_boundaries(plan)

if result.decision == Decision.BLOCK:
    print("BLOCKED:", [v.message for v in result.violations])
elif result.needs_confirmation:
    print("WARNINGS:", result.warnings)
    # Ask operator to confirm
else:
    print("Safe to proceed")
```

## AI Safety Advisor

When a plan triggers warnings and a `sample_description` is provided, LabAgent consults an LLM safety advisor. The advisor provides context-aware advice specific to the material and measurement type:

1. **Why the limit exists** -- explains the specific damage mechanism
2. **What could happen** -- describes potential sample or instrument damage
3. **Safer alternatives** -- suggests parameter adjustments that still yield useful data
4. **Severity assessment** -- whether the warning is critical or merely cautionary

```python
result = check_boundaries(
    plan,
    sample_description="5nm Ta/CoFeB/MgO thin film"
)

if result.ai_advice:
    print(result.ai_advice)
    # Example: "100 mA through a 5nm CoFeB film risks electromigration.
    # For Hall measurements on this thickness, 1-10 mA is typical.
    # Reduce to 10 mA to stay well within safe operating range."
```

The AI advisor is purely informational -- it does not modify the plan or override safety decisions.

## AI Suggestion Clamping

When the plan builder uses AI to optimize measurement parameters, all AI-suggested values are clamped to the template's safety limits before they are applied. The clamping covers:

- `max_current_a`
- `max_voltage_v`
- `max_field_oe`
- `max_temperature_k`

If an AI suggestion exceeds a template limit, it is silently dropped with a warning logged. This ensures AI assistance never weakens safety boundaries.

## Safety in the Web GUI

The web GUI validates plans through the same boundary checker. The `/api/configure` endpoint returns the full validation result alongside the plan, allowing the frontend to display warnings and block unsafe configurations before any instrument communication occurs.

## Best Practices

1. **Set conservative limits first** -- start with tight safety policies and relax only after verifying your setup
2. **Use sample descriptions** -- the AI advisor provides much better guidance when it knows your material
3. **Review warnings carefully** -- warnings exist because the parameters are outside typical ranges for good reason
4. **Create lab-specific policies** -- different labs and instruments have different safe operating ranges; customize `default_safety.yaml` for your setup
5. **Never bypass Tier 1** -- absolute limits protect against hardware damage and should reflect your instruments' actual ratings
