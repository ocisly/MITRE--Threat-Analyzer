import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

STIX_URLS: dict[str, str] = {
    "enterprise-attack": (
        "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
        "/master/enterprise-attack/enterprise-attack.json"
    ),
    "mobile-attack": (
        "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
        "/master/mobile-attack/mobile-attack.json"
    ),
    "ics-attack": (
        "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
        "/master/ics-attack/ics-attack.json"
    ),
}


async def download_stix(domain: str, output_dir: Path) -> Path:
    """Download STIX JSON for a domain, using ETag to skip unchanged files.

    Returns the local file path (whether newly downloaded or cached).
    Raises ValueError for unknown domains, httpx.HTTPError on network failure.
    """
    if domain not in STIX_URLS:
        raise ValueError(f"Unknown MITRE domain: {domain}. Valid: {list(STIX_URLS)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{domain}.json"
    etag_file = output_dir / f"{domain}.etag"

    headers: dict[str, str] = {}
    if etag_file.exists() and output_file.exists():
        headers["If-None-Match"] = etag_file.read_text().strip()

    url = STIX_URLS[domain]
    logger.info("Downloading %s from %s", domain, url)

    async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)

        if response.status_code == 304:
            logger.info("%s STIX data unchanged (ETag match), using cached file", domain)
            return output_file

        response.raise_for_status()

        output_file.write_bytes(response.content)
        logger.info("Downloaded %s (%.1f MB)", domain, len(response.content) / 1_048_576)

        if etag := response.headers.get("ETag"):
            etag_file.write_text(etag)

    return output_file
