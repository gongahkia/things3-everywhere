"""Local documentation/hygiene checks. Never read ignored personal files."""

from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root, text=True
).splitlines()
errors = []
checked = 0
for name in sorted(set(names)):
    path = root / name
    if not path.is_file():
        continue
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        errors.append(f"{name}: real environment file is publishable")
    if path.suffix not in (".md", ".py", ".toml", ".example", ".applescript") and name != ".gitignore":
        continue
    text = path.read_text()
    if re.search(r"\b[0-9]{5,16}:[A-Za-z0-9_-]{30,100}\b", text):
        errors.append(f"{name}: possible literal bot token")
    if path.suffix == ".md":
        checked += 1
        if text.count(chr(96) * 3) % 2:
            errors.append(f"{name}: unbalanced fenced code")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            target = unquote(target.split("#", 1)[0])
            if target and not (path.parent / target).exists():
                errors.append(f"{name}: broken relative link {target}")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"Checked {checked} Markdown files: relative links, fences, publishable env files, literal bot-token pattern.")
