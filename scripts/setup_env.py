"""Copy defaults with a blank Gemini key; fill missing settings without replacing values."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
example = (ROOT / ".env.example").read_text(encoding="utf-8")
example, count = re.subn(r"(?m)^GEMINI_API_KEY=.*$", "GEMINI_API_KEY=", example)
if count != 1:
    raise SystemExit(".env.example must contain exactly one GEMINI_API_KEY entry.")

key_pattern = r"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*="
assignments = [line for line in example.splitlines() if re.match(key_pattern, line)]
content = "\n".join(assignments) + "\n"

try:
    with (ROOT / ".env").open("x", encoding="utf-8") as env:
        env.write(content)
except FileExistsError:
    env_path = ROOT / ".env"
    existing = env_path.read_text(encoding="utf-8")
    existing_keys = set(re.findall(key_pattern, existing, flags=re.MULTILINE))
    example_keys = set(re.findall(key_pattern, content, flags=re.MULTILINE))
    missing = example_keys - existing_keys
    if missing:
        additions = [
            line
            for line in assignments
            if re.match(key_pattern, line).group(1) in missing
        ]
        with env_path.open("a", encoding="utf-8") as env:
            if existing and not existing.endswith("\n"):
                env.write("\n")
            env.write("\n".join(additions) + "\n")
        print(f"Added {len(missing)} missing settings. Existing values preserved.")
    else:
        print("Existing .env preserved; all settings are present.")
else:
    (ROOT / ".env").chmod(0o600)
    print("Created .env. Add your GEMINI_API_KEY manually.")
