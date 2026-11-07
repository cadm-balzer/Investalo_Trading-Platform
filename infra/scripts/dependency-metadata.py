#!/usr/bin/env python3
"""Read public package metadata for the selected application dependency set.

The result is a temporary build aid; this never installs packages or replaces
the application locks. Every resolved version must subsequently be pinned.
"""
import concurrent.futures
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

PYPI = ("fastapi", "pydantic", "pydantic-core", "psycopg", "psycopg-binary", "uvicorn",
        "pytest", "httpx")
NPM = ("next", "react", "react-dom", "typescript", "@types/react",
       "@types/react-dom", "@types/node", "jose", "server-only")


def fetch(item: tuple[str, str]) -> tuple[str, dict]:
    registry, package = item
    url = (f"https://pypi.org/pypi/{package}/json" if registry == "pypi"
           else f"https://registry.npmjs.org/{quote(package, safe='')}/latest")
    with urlopen(url, timeout=30) as response:
        data = json.load(response)
    if registry == "pypi":
        info = data["info"]
        result = {"version": info["version"], "requires_python": info["requires_python"],
                  "urls": data["urls"], "requires_dist": info["requires_dist"]}
    else:
        result = {key: data.get(key) for key in
                  ("version", "engines", "dist", "dependencies", "license")}
    return f"{registry}:{package}", result


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        data = dict(pool.map(fetch, [("pypi", p) for p in PYPI] +
                             [("npm", p) for p in NPM]))
    destination = Path("/tmp/investalo-bootstrap/dependency-metadata.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, indent=2) + "\n")
    for name, result in data.items():
        print(name, result["version"],
              result.get("requires_python") or result.get("engines") or "")
