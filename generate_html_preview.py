import os
import re
from pathlib import Path
import markdown

BASE_DIR = Path(__file__).resolve().parent
md_file = BASE_DIR / "PLAN" / "Lo_trinh_chi_tiet_tung_module_kiem_soat.md"
html_file = BASE_DIR / "PLAN" / "Lo_trinh_chi_tiet_tung_module_kiem_soat.html"

raw_content = md_file.read_text(encoding="utf-8")

# Tách phần <style>...</style> ở đầu nếu có
style_match = re.search(r'(<style>.*?</style>)', raw_content, re.DOTALL)
if style_match:
    style_block = style_match.group(1)
    body_markdown = raw_content[style_match.end():]
else:
    style_block = ""
    body_markdown = raw_content

# Render Markdown sang HTML với các extension chuẩn
html_body = markdown.markdown(
    body_markdown,
    extensions=['tables', 'fenced_code', 'sane_lists']
)

# Ghép thành tệp HTML hoàn chỉnh
full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BOSOL AI - Lộ Trình Chi Tiết Từng Module Kiểm Soát</title>
    {style_block}
</head>
<body>
{html_body}
</body>
</html>"""

html_file.write_text(full_html, encoding="utf-8")
print(f"Xuat thanh cong file HTML hoan chinh: {html_file.resolve()} ({html_file.stat().st_size / 1024:.1f} KB)")
