# check_requirements_drift.py -- verifies every package requirements.in lists
# directly still appears somewhere in the compiled requirements.txt. Does NOT
# check version numbers or transitive extras -- pip-compile re-runs
# legitimately shift those on nearly every run as upstream packages release
# new versions, which is normal churn, not drift. This only catches the real
# Phase 15 incident shape: a package requirements.in names (e.g.
# python-dotenv) silently missing or renamed (e.g. dotenv) in the compiled
# output.
import re
import sys

def normalize(name: str) -> str:
    return name.lower().replace('_', '-')

def direct_packages(requirements_in_path: str) -> set[str]:
    names = set()
    with open(requirements_in_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # package name is everything before the first version/extras marker
            match = re.match(r'^([A-Za-z0-9_.-]+)', line)
            if match:
                names.add(normalize(match.group(1)))
    return names

def compiled_packages(requirements_txt_path: str) -> set[str]:
    names = set()
    with open(requirements_txt_path, encoding='utf-8') as f:
        for line in f:
            # a top-level pinned entry starts at column 0, e.g. "numpy==2.5.3"
            # or "httpx[brotli,http2,socks]==0.28.1" -- comment/"via" lines
            # are indented and skipped here
            match = re.match(r'^([A-Za-z0-9_.-]+)(\[[^\]]*\])?==', line)
            if match:
                names.add(normalize(match.group(1)))
    return names

if __name__ == '__main__':
    req_in_path = sys.argv[1] if len(sys.argv) > 1 else 'requirements.in'
    required = direct_packages(req_in_path)
    compiled = compiled_packages('requirements.txt')
    missing = sorted(required - compiled)

    if missing:
        print(f'DRIFT: {len(missing)} package(s) in requirements.in are missing from requirements.txt:')
        for name in missing:
            print(f'  - {name}')
        sys.exit(1)

    print(f'OK: all {len(required)} direct dependencies from requirements.in are present in requirements.txt.')
    sys.exit(0)
