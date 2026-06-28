#!/usr/bin/env python3
"""Convert a markdown file to PDF via Chrome Headless (Markdown → HTML → PDF)."""

import sys
import os
import subprocess
import tempfile
import markdown

def md_to_pdf(md_path: str, pdf_path: str) -> None:
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "attr_list"],
    )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<style>
  body {{
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.55;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px 30px;
    color: #1a1a1a;
  }}
  h1 {{
    font-size: 20pt;
    color: #1d4e89;
    border-bottom: 3px solid #1d4e89;
    padding-bottom: 8px;
    margin-top: 0;
  }}
  h2 {{
    font-size: 15pt;
    color: #1d4e89;
    border-bottom: 1.5px solid #c5d8f0;
    padding-bottom: 4px;
    margin-top: 28px;
    break-before: page;
  }}
  h3 {{
    font-size: 13pt;
    color: #2c5f9e;
    margin-top: 18px;
  }}
  h4 {{
    font-size: 11pt;
    color: #333;
    margin-top: 12px;
    margin-bottom: 4px;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 9.5pt;
  }}
  th {{
    background: #1d4e89;
    color: white;
    padding: 6px 10px;
    text-align: left;
  }}
  td {{
    padding: 5px 10px;
    border: 1px solid #d0d0d0;
  }}
  tr:nth-child(even) td {{
    background: #f4f8fd;
  }}
  code {{
    background: #f0f0f0;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9.5pt;
    font-family: 'Courier New', monospace;
  }}
  pre {{
    background: #f5f5f5;
    border-left: 4px solid #1d4e89;
    padding: 10px 14px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.4;
  }}
  pre code {{
    background: none;
    padding: 0;
  }}
  blockquote {{
    border-left: 4px solid #1d4e89;
    margin: 8px 0;
    padding: 6px 14px;
    color: #444;
    background: #f0f5fb;
  }}
  hr {{
    border: none;
    border-top: 1px solid #ddd;
    margin: 16px 0;
  }}
  ul, ol {{
    padding-left: 22px;
    margin: 6px 0;
  }}
  li {{
    margin-bottom: 3px;
  }}
  strong {{
    color: #1d4e89;
  }}
  .page-break {{
    break-before: page;
  }}
  @media print {{
    body {{ padding: 0; }}
    h2 {{ break-before: page; }}
  }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tmp:
        tmp.write(html)
        tmp_path = tmp.name

    try:
        chrome_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        chrome = next((c for c in chrome_candidates if os.path.exists(c)), None)
        if not chrome:
            raise RuntimeError("Chrome/Chromium not found")

        subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--print-to-pdf=" + os.path.abspath(pdf_path),
                "--print-to-pdf-no-header",
                "--no-margins",
                "file://" + os.path.abspath(tmp_path),
            ],
            check=True,
            capture_output=True,
        )
        print(f"PDF gespeichert: {pdf_path}")
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python md_to_pdf.py <input.md> <output.pdf>")
        sys.exit(1)
    md_to_pdf(sys.argv[1], sys.argv[2])
