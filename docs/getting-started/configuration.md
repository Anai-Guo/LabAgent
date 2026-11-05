# Configuration

## AI Model Selection

Model settings come from two sources, applied in this order:

1. The `model:` block of a YAML config file (`configs/models.yaml` by default).
2. `LABHARNESS_*` environment variables, which override any value from the file.

Anything not set by either falls back to the built-in defaults
(`provider: anthropic`, `model: claude-sonnet-4-20250514`, `temperature: 0.0`,
`max_tokens: 4096`).

### Config file

Edit `configs/models.yaml`:

```yaml
model:
  provider: "anthropic"
  model: "claude-sonnet-4-20250514"
  # api_key: "sk-..."    # or set LABHARNESS_API_KEY
  # base_url: "..."      # only for local / OpenAI-compatible servers
  temperature: 0.0
  max_tokens: 4096
```

The CLI reads `configs/models.yaml` relative to the current working directory.
Point it at a different file with the global `--config` option:

```bash
labharness --config path/to/models.yaml scan
```

The file ships with commented-out presets for OpenAI, Gemini, Ollama, vLLM and
DeepSeek — uncomment the one you want.

!!! note
    Some entry points (for example the web GUI and the MCP server tools) load
    settings without a config path, so they only see environment variables and
    the built-in defaults. Use environment variables if you want one setting to
    apply everywhere.

### Environment variables

```bash
export LABHARNESS_PROVIDER=anthropic
export LABHARNESS_MODEL=claude-sonnet-4-20250514
export LABHARNESS_API_KEY=sk-...
```

| Variable | Overrides | Notes |
|----------|-----------|-------|
| `LABHARNESS_PROVIDER` | `model.provider` | `anthropic`, `openai`, `ollama`, `deepseek`, ... |
| `LABHARNESS_MODEL` | `model.model` | Model name passed to litellm |
| `LABHARNESS_API_KEY` | `model.api_key` | Not needed for local providers such as Ollama |
| `LABHARNESS_BASE_URL` | `model.base_url` | Endpoint for Ollama, vLLM or any OpenAI-compatible server |
| `LABHARNESS_DATA_DIR` | — | Where experiment data is written (default `./data`) |

### Local and OpenAI-compatible servers

For Ollama:

```bash
export LABHARNESS_PROVIDER=ollama
export LABHARNESS_MODEL=qwen3:32b
export LABHARNESS_BASE_URL=http://localhost:11434
```

For vLLM or any other OpenAI-compatible server, use the `openai` provider with
a `base_url`:

```bash
export LABHARNESS_PROVIDER=openai
export LABHARNESS_MODEL=Qwen/Qwen2.5-32B-Instruct
export LABHARNESS_BASE_URL=http://localhost:8000/v1
```

### Setup wizard

`labharness setup` asks for a provider, model and API key, then writes the
answers as `LABHARNESS_*` lines to a `.env` file in the current directory and
tests the connection. LabAgent's settings loader does not read `.env` itself
(litellm may pick it up once it is imported, but settings are often loaded
before that), so export those variables in your shell, or load the file with
your usual tooling, before running other commands.

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

See `configs/instruments/example.yaml` for a fuller example covering several
common instruments.
