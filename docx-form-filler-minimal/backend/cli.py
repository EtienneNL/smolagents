"""
CLI for analyzing/filling DOCX placeholder templates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from backend.docx_processor import analyze_docx_placeholders, fill_docx_template
except ModuleNotFoundError:
    from docx_processor import analyze_docx_placeholders, fill_docx_template


def _parse_values(values_raw: str | None, values_file: str | None) -> dict:
    if values_raw and values_file:
        raise ValueError("Use either --values or --values-file, not both.")

    if values_file:
        raw = Path(values_file).read_text(encoding="utf-8")
    elif values_raw:
        raw = values_raw
    else:
        return {}

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Values JSON must be an object/dictionary.")
    return parsed


def cmd_analyze(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return 1
    if input_path.suffix.lower() != ".docx":
        print("Error: input file must be .docx")
        return 1

    summary = analyze_docx_placeholders(input_path.read_bytes())
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def cmd_fill(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return 1
    if input_path.suffix.lower() != ".docx":
        print("Error: input file must be .docx")
        return 1

    try:
        values = _parse_values(args.values, args.values_file)
    except Exception as exc:
        print(f"Error parsing values: {exc}")
        return 1

    excel_bytes = None
    if args.excel:
        excel_path = Path(args.excel)
        if not excel_path.exists():
            print(f"Error: excel file not found: {excel_path}")
            return 1
        if excel_path.suffix.lower() not in {".xlsx", ".xls"}:
            print("Error: excel file must be .xlsx or .xls")
            return 1
        excel_bytes = excel_path.read_bytes()

    output_path = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}_filled.docx")

    try:
        filled_bytes = fill_docx_template(
            docx_bytes=input_path.read_bytes(),
            values=values,
            excel_bytes=excel_bytes,
        )
    except Exception as exc:
        print(f"Error filling template: {exc}")
        return 1

    output_path.write_bytes(filled_bytes)
    print(f"Saved filled DOCX: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DOCX placeholder analyzer/filler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="List placeholders in a DOCX template")
    analyze_parser.add_argument("--input", required=True, help="Path to input .docx template")
    analyze_parser.set_defaults(func=cmd_analyze)

    fill_parser = subparsers.add_parser("fill", help="Fill a DOCX template")
    fill_parser.add_argument("--input", required=True, help="Path to input .docx template")
    fill_parser.add_argument("--output", help="Path to output .docx file")
    fill_parser.add_argument("--values", help="Inline JSON object with scalar placeholder values")
    fill_parser.add_argument("--values-file", help="Path to JSON file with scalar placeholder values")
    fill_parser.add_argument("--excel", help="Path to .xlsx/.xls file for table placeholders")
    fill_parser.set_defaults(func=cmd_fill)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
