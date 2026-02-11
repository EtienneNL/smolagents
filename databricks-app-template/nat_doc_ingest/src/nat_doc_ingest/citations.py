from __future__ import annotations

from html import escape


def build_sources_accordion(
    results: list[dict],
    *,
    title_key: str = "source",
    page_key: str = "page_number",
    content_key: str = "content",
    heading: str = "Sources",
) -> str:
    if not results:
        return ""

    lines = ["<details>", f"<summary>{escape(heading)}</summary>", ""]
    for idx, item in enumerate(results, start=1):
        title = str(item.get(title_key) or f"Source {idx}")
        page = item.get(page_key)
        header = f"{title} — Page {page}" if page is not None else title
        content = str(item.get(content_key) or "").strip()
        if not content:
            continue
        lines.append("<details>")
        lines.append(f"<summary>{escape(header)}</summary>")
        lines.append("<pre>")
        lines.append(escape(content))
        lines.append("</pre>")
        lines.append("</details>")
        lines.append("")

    lines.append("</details>")
    return "\n".join(lines)
