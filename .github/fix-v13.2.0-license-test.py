from pathlib import Path

path = Path('tests/architecture.test.ts')
text = path.read_text(encoding='utf-8')
needle = '  projection.rules_version="<approved rules version>";\n'
replacement = needle + (
    '  projection.metadata.attribution="Created by NixNinja in collaboration with artificial intelligence assistants. Special thanks to various muses, great and small.";\n'
    '  projection.metadata.license="Original Kinetic Vanguard material may be used, copied, modified, and redistributed for non-commercial purposes with credit to NixNinja. Commercial use requires prior written permission. System Reference Document-derived rules text and references are separately governed by the Creative Commons Attribution 4.0 International License.";\n'
)
if needle not in text:
    raise SystemExit('Expected authority-projection normalization point was not found')
path.write_text(text.replace(needle, replacement, 1), encoding='utf-8')
