# AI Analysis

LabAgent provides a three-tier data analysis pipeline that scales from fully deterministic template scripts to AI-generated custom analysis with physics interpretation. All tiers produce publication-ready plots (PNG at 300 dpi and PDF) and extract key physical quantities from measurement data.

## Three-Tier Analysis Architecture

### Tier 1: Template-Based Analysis

Built-in analysis scripts handle common measurement types with zero configuration. Each template is a complete Python script with placeholder substitution for the data path and output directory.

Available analysis templates:

| Measurement Type | Template | Key Outputs |
|-----------------|----------|-------------|
| AHE | `ahe.py` | Anomalous Hall resistance, coercive field, loop area |
| IV | `iv.py` | Differential resistance, threshold voltage, conductance |
| MR | `mr.py` | Magnetoresistance ratio, coercive field, saturation field |
| RT | `rt.py` | Residual resistance ratio, transition temperature, TCR |

```bash
# Analyze data with the built-in IV template
labharness analyze data.csv --type IV
```

Template scripts use numpy, scipy, and matplotlib. They handle common edge cases (empty data, NaN values, comment-line headers) and print extracted values in a `key = value` format that the analyzer parses automatically.

### Tier 2: AI-Generated Analysis

When no built-in template exists for a measurement type, or when you need custom analysis, the AI generator creates a tailored Python script. It receives:

- The measurement type
- A preview of the data (column headers, row count, first 20 rows)
- Optional custom instructions from the user

The LLM generates a complete, self-contained script that follows the same conventions as the built-in templates: load data, process, extract values, save figures.

```bash
# Force AI-generated analysis even when a template exists
labharness analyze data.csv --type AHE --ai

# Add custom analysis instructions
labharness analyze data.csv --type IV --ai \
  --instructions "Fit the forward bias region to extract ideality factor"
```

If no template is found and no LLM is configured, the system raises an error with a clear message listing available templates.

### Tier 3: AI Interpretation

After analysis (from either tier), the interpreter provides physics-level insights about the results. It examines extracted values and script output to deliver:

1. **Physical meaning** -- what the extracted values indicate about the sample
2. **Reasonableness check** -- whether results are physically plausible
3. **Literature comparison** -- how values compare to typical ranges
4. **Anomaly detection** -- flags unexpected or suspicious results
5. **Follow-up suggestions** -- recommends additional measurements if warranted

```bash
# Run analysis with AI interpretation
labharness analyze data.csv --type AHE --interpret
```

## Python API

The `Analyzer` class provides programmatic access to all three tiers:

```python
from pathlib import Path
from lab_harness.analysis.analyzer import Analyzer

analyzer = Analyzer(output_dir=Path("./results"))

# Full pipeline: template script -> execute -> interpret
result = analyzer.analyze(
    data_path=Path("ahe_data.csv"),
    measurement_type="AHE",
    interpret=True,
)

print(result.extracted_values)  # {"R_AHE": "0.15 Ohm", "H_c": "250 Oe"}
print(result.figures)           # ["./results/ahe_Rxy_vs_H.png", ...]
print(result.ai_interpretation) # Physics insights string
```

### AnalysisResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `measurement_type` | str | Type of measurement analyzed |
| `script_path` | str | Path to the generated analysis script |
| `script_source` | str | Full source code of the script |
| `figures` | list[str] | Paths to generated PNG and PDF figures |
| `extracted_values` | dict | Key-value pairs of extracted physical quantities |
| `ai_interpretation` | str | AI-generated physics insights (empty if not requested) |
| `stdout` | str | Raw script output |

## Script Execution

Analysis scripts run in a sandboxed subprocess with a configurable timeout (default 120 seconds). The analyzer:

1. Saves the generated script to the output directory
2. Runs it with `python` in a subprocess
3. Captures stdout/stderr
4. Parses extracted values from stdout lines matching `key = value`
5. Collects all PNG and PDF files from the output directory as figures

If the script fails (non-zero exit code), the error is raised with the first 500 characters of stderr for debugging.

## Supported Output Formats

Analysis figures are saved in both PNG (300 dpi, for viewing) and PDF (vector, for publication). The data export system supports three formats for raw data:

| Format | Extension | Features |
|--------|-----------|----------|
| CSV | `.csv` | Metadata header as comments, standard column format |
| JSON | `.json` | Structured metadata + data array, human-readable |
| HDF5 | `.h5` | Columnar datasets with metadata attributes (requires h5py) |

```bash
# Export measurement data
labharness export data.csv --format json
labharness export data.csv --format hdf5
```

## Extending Analysis Templates

To add a new analysis template:

1. Create a Python script in `src/lab_harness/analysis/templates/` named `{type}.py`
2. Use `{{DATA_PATH}}` and `{{OUTPUT_DIR}}` as placeholders
3. Print extracted values as `key = value` lines to stdout
4. Save figures to `{{OUTPUT_DIR}}` as PNG and PDF

The template will be automatically discovered by the analyzer for that measurement type.
