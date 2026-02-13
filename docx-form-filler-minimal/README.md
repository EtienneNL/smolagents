# DOCX Form Filler (Minimal)

Minimal backend-style solution for filling `.docx` templates that use placeholders like:

- Scalar placeholders: `{{item1}}`, `{{full_name}}`
- Table placeholders: `{{table_1}}`, `{{table_2}}`

This project intentionally uses open-source Python packages only (no LlamaParse):

- `python-docx` for reading/writing Word files while retaining document structure/formatting
- `pandas` (+ `openpyxl`) for reading Excel data used in table placeholders
- `FastAPI` for a minimal API
- Optional: `anthropic` for structured LLM extraction with Pydantic `BaseModel`

---

## What this does

1. Analyze a DOCX template and list placeholders.
2. Fill scalar placeholders from JSON values.
3. Fill table placeholders from Excel sheets and write a new `.docx`.
4. Preserve existing document formatting outside replaced placeholders.
5. Optional: extract scalar values from natural language via LLM structured output.

---

## Project layout

```text
docx-form-filler-minimal/
├── backend/
│   ├── cli.py
│   ├── docx_processor.py
│   ├── llm_mapper.py
│   └── main.py
└── requirements.txt
```

---

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Placeholder conventions

### Scalar placeholders

Use placeholders like:

```text
{{item1}}
{{customer_name}}
{{date}}
```

Pass values as JSON:

```json
{
  "item1": "ABC-123",
  "customer_name": "Jane Doe",
  "date": "2026-02-13"
}
```

Keys can be provided either as `item1` or `{{item1}}`.

### Optional LLM extraction (typed)

If you prefer natural language instructions, the project can optionally use an LLM to produce typed scalar values via a Pydantic `BaseModel`.

- The model output is constrained to a schema (`dict[str, str|bool|int|float]`)
- Unknown placeholder keys are filtered out after parsing
- The final document fill step stays deterministic

### Table placeholders

Use placeholders like:

```text
{{table_1}}
{{table_2}}
```

Table placeholders are populated from Excel sheets using `pandas.read_excel`.

Mapping logic:

- `table_1` -> first Excel sheet by default
- `table_2` -> second Excel sheet by default
- if a sheet is literally named `table_1`, that exact name is preferred

Inserted tables include header row + all sheet rows.

---

## CLI usage

### Analyze placeholders

```bash
python backend/cli.py analyze --input template.docx
```

### Fill template

```bash
python backend/cli.py fill \
  --input template.docx \
  --output filled.docx \
  --values '{"item1":"ABC-123","customer_name":"Jane Doe"}' \
  --excel data.xlsx
```

Or pass values from a file:

```bash
python backend/cli.py fill \
  --input template.docx \
  --output filled.docx \
  --values-file values.json \
  --excel data.xlsx
```

### Fill template with optional LLM extraction

```bash
python backend/cli.py fill \
  --input template.docx \
  --output filled.docx \
  --use-llm \
  --instructions "Customer name is Jane Doe and policy number is P-12345" \
  --anthropic-api-key "$ANTHROPIC_API_KEY" \
  --excel data.xlsx
```

You can still pass `--values` / `--values-file`; explicit values override LLM output.

---

## API usage

Run server:

```bash
uvicorn backend.main:app --reload --port 8001
```

### `POST /analyze-docx`

Multipart upload:

- `file`: `.docx` template

Returns all placeholders + scalar/table split.

### `POST /fill-docx`

Multipart upload:

- `file`: `.docx` template
- `values`: JSON string for scalar placeholders (optional, default `{}`)
- `excel_file`: `.xlsx` or `.xls` for table placeholders (optional unless template has `{{table_*}}`)
- `use_llm`: `true|false` (optional, default `false`)
- `instructions`: natural language text (required when `use_llm=true`)
- `anthropic_api_key`: optional API key for LLM extraction
- `llm_model`: optional model name (default `claude-sonnet-4-5`)

Returns filled `.docx` as a download.

### `POST /extract-values`

Multipart upload:

- `file`: `.docx` template
- `instructions`: natural language instructions
- `anthropic_api_key`: optional API key
- `llm_model`: optional model name

Returns typed scalar placeholder values extracted by structured output.

---

## Notes / limitations

- This targets placeholder-based templates, not native Word legacy form controls.
- Best formatting retention is achieved when placeholders are kept as standalone tokens in the template.
- Table placeholder insertion is applied in document body paragraphs (recommended placement: placeholder in its own paragraph).
- LLM extraction is optional; fill itself remains deterministic.
