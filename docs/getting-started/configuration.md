# Configuration

## AI Model Selection

Edit `configs/models.yaml` or use environment variables:

```bash
export LABHARNESS_PROVIDER=anthropic
export LABHARNESS_MODEL=claude-sonnet-4-20250514
export LABHARNESS_API_KEY=sk-...
```

## Instrument Configuration

Create `configs/instruments/mylab.yaml`:
```yaml
instruments:
  source_meter:
    driver: keithley2400
    resource: "GPIB0::5::INSTR"
    settings:
      compliance_v: 20.0
```
