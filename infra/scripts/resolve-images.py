#!/usr/bin/env python3
"""Resolve explicitly selected public image tags to immutable manifest digests.

No login credentials are used. The registry's anonymous read token stays in memory.
"""
import concurrent.futures
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

IMAGES = {
    "PYTHON_IMAGE": ("library/python", "3.14.10-slim-bookworm"),
    "NODE_IMAGE": ("library/node", "24.22.2-bookworm-slim"),
    "POSTGRES_IMAGE": ("library/postgres", "18.6-bookworm"),
    "AUTHELIA_IMAGE": ("authelia/authelia", "4.39.28"),
    "CADDY_IMAGE": ("library/caddy", "2.11.9-alpine"),
}


def resolve(item: tuple[str, tuple[str, str]]) -> tuple[str, str]:
    name, (repository, tag) = item
    params = urlencode({
        "service": "registry.docker.io",
        "scope": f"repository:{repository}:pull",
    })
    with urlopen(f"https://auth.docker.io/token?{params}", timeout=30) as response:
        token = json.load(response)["token"]
    request = Request(
        f"https://registry-1.docker.io/v2/{repository}/manifests/{tag}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": (
                "application/vnd.oci.image.index.v1+json,"
                "application/vnd.docker.distribution.manifest.list.v2+json,"
                "application/vnd.oci.image.manifest.v1+json,"
                "application/vnd.docker.distribution.manifest.v2+json"
            ),
        },
    )
    with urlopen(request, timeout=30) as response:
        digest = response.headers["Docker-Content-Digest"]
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError(f"Invalid manifest digest for {name}")
    image = repository.removeprefix("library/")
    return name, f"{image}:{tag}@{digest}"


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(resolve, IMAGES.items()))
    destination = Path(__file__).resolve().parents[1] / "images.env"
    contents = (
        "# Verified public runtime tags and immutable manifest digests.\n"
        "# Re-resolve intentionally when updating the pinned runtime set.\n"
        + "".join(f"{name}={reference}\n" for name, reference in results)
    )
    destination.write_text(contents)
    print(contents, end="")


if __name__ == "__main__":
    main()
