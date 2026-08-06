from pathlib import Path

path = Path('src/render.ts')
text = path.read_text(encoding='utf-8')
needle = '.versions,footer{color:var(--muted)}'
replacement = '.versions,footer{color:var(--muted)}footer{overflow-wrap:anywhere}'
if needle not in text:
    raise SystemExit('Expected footer style anchor was not found')
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')
