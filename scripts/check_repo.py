#!/usr/bin/env python3
"""Check public source hygiene, local documentation links and syntax."""
from pathlib import Path
import ast
import json
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '__pycache__', 'build', 'dist', 'out'}
VENDORED_DOCS = ('fixes/boot-controller/limine/', 'fixes/boot-controller/reference-headers/',
                'fixes/oxp3-controller/inputplumber/reference-v0.81.0/')


def main():
    errors = []
    files = [p for p in ROOT.rglob('*') if p.is_file() and not any(part in SKIP for part in p.relative_to(ROOT).parts)]
    for path in files:
        rel = path.relative_to(ROOT)
        name = rel.as_posix()
        if any(part in {'evidence', 'local-artifacts', 'validation'} for part in rel.parts):
            errors.append(f'{name}: private capture/result directory')
        if path.suffix.lower() in {'.log', '.csv', '.bin', '.efi', '.ko', '.pyc'} or '.pkg.tar.' in path.name:
            errors.append(f'{name}: generated/captured artifact')
        if path.name.endswith('validation.json') or path.name.lower() in {'provenance.json', 'capture-summary.json'}:
            errors.append(f'{name}: raw provenance/result dump')
        try:
            text = path.read_text()
        except UnicodeError:
            errors.append(f'{name}: non-text file; review before publication')
            continue
        if '\0' in text:
            errors.append(f'{name}: binary contents')
        if re.search(r'/Users/[A-Za-z0-9_-]+/|192\.168\.\d+\.\d+|BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,}', text):
            errors.append(f'{name}: private path/address/credential pattern')
        try:
            if path.suffix == '.py':
                ast.parse(text, filename=name)
            elif path.suffix == '.json':
                json.loads(text)
            elif path.suffix == '.sh' or path.name == 'PKGBUILD':
                result = subprocess.run(['bash', '-n', str(path)], text=True, capture_output=True)
                if result.returncode:
                    errors.append(f'{name}: {result.stderr.strip()}')
        except (SyntaxError, ValueError) as exc:
            errors.append(f'{name}: {exc}')
        if path.suffix == '.md' and not name.startswith(VENDORED_DOCS):
            for match in re.finditer(r'\[[^\]]*\]\(([^\n)]+)\)', text):
                target = match.group(1).split(' "', 1)[0].strip('<>')
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                target = unquote(target.split('#', 1)[0])
                if target and not (path.parent / target).exists():
                    errors.append(f'{name}: broken local link {target}')
    for item in json.loads((ROOT / 'fixes.json').read_text()):
        if not (ROOT / item['docs']).is_file():
            errors.append(f"fixes.json: missing {item['docs']}")
    for folder in (ROOT / 'fixes').iterdir():
        if folder.is_dir():
            for name in ('README.md', 'WRITEUP.md'):
                if not (folder / name).is_file():
                    errors.append(f'{folder.relative_to(ROOT)}: missing {name}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Checked {len(files)} source/documentation files: syntax, links and public-content hygiene passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
