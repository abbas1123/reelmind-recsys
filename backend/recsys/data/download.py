"""One-time download of the MovieLens archives with MD5 verification.

Archives are stored in ``data/raw/`` and only the files we need are extracted.
Re-running is cheap: a verified archive is never downloaded twice.
"""

from __future__ import annotations

import hashlib
import logging
import ssl
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://files.grouplens.org/datasets/movielens"


@dataclass(frozen=True)
class Archive:
    name: str  # e.g. "ml-1m"
    members: tuple[str, ...]  # files to extract (paths inside the zip)

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.name}.zip"

    @property
    def md5_url(self) -> str:
        return f"{self.url}.md5"


ML_1M = Archive("ml-1m", ("ml-1m/ratings.dat", "ml-1m/movies.dat", "ml-1m/users.dat", "ml-1m/README"))
ML_32M = Archive("ml-32m", ("ml-32m/links.csv", "ml-32m/tags.csv", "ml-32m/movies.csv", "ml-32m/README.txt"))


def _md5(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def _expected_md5(client: httpx.Client, archive: Archive) -> str:
    resp = client.get(archive.md5_url)
    resp.raise_for_status()
    # Format: "<md5>  ml-1m.zip" (some files use "MD5 (file) = <md5>")
    text = resp.text.strip()
    token = text.split("=")[-1].strip() if "=" in text else text.split()[0]
    if len(token) != 32:
        raise ValueError(f"Unexpected md5 file content for {archive.name}: {text!r}")
    return token.lower()


def _stream_to(client: httpx.Client, url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done, next_report = 0, 0.0
        with tmp.open("wb") as fh:
            for block in resp.iter_bytes(1 << 20):
                fh.write(block)
                done += len(block)
                if total and done / total >= next_report:
                    log.info("  %s: %5.1f%% of %.1f MB", dest.name, 100 * done / total, total / 1e6)
                    next_report += 0.2
    tmp.replace(dest)


def _safe_extract(zip_path: Path, members: tuple[str, ...], out_dir: Path) -> list[Path]:
    """Extract only the listed members, refusing absolute or parent-relative paths."""
    extracted = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        for member in members:
            if member not in names:
                raise FileNotFoundError(f"{member} not found inside {zip_path.name}")
            pure = PurePosixPath(member)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError(f"Unsafe path in archive: {member}")
            target = out_dir.joinpath(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                while block := src.read(1 << 20):
                    dst.write(block)
            extracted.append(target)
    return extracted


def _ssl_context() -> ssl.SSLContext:
    """Verify TLS against the operating system trust store.

    Corporate proxies often re-sign TLS traffic with a root that exists in the Windows/macOS
    store but not in certifi's bundle. ``truststore`` keeps verification on and uses the OS store.
    """
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:  # pragma: no cover - truststore is a declared dependency
        return ssl.create_default_context()


def fetch(archive: Archive, raw_dir: Path, force: bool = False) -> Path:
    """Download (if needed), verify and extract ``archive``. Returns the extraction folder."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / f"{archive.name}.zip"
    timeout = httpx.Timeout(60.0, read=300.0)
    with httpx.Client(timeout=timeout, follow_redirects=True, verify=_ssl_context()) as client:
        expected = _expected_md5(client, archive)
        if zip_path.exists() and not force and _md5(zip_path) == expected:
            log.info("%s already downloaded and verified (md5 %s)", zip_path.name, expected)
        else:
            log.info("Downloading %s", archive.url)
            _stream_to(client, archive.url, zip_path)
            actual = _md5(zip_path)
            if actual != expected:
                zip_path.unlink(missing_ok=True)
                raise RuntimeError(f"MD5 mismatch for {zip_path.name}: expected {expected}, got {actual}")
            log.info("Verified %s (md5 %s)", zip_path.name, actual)
    files = _safe_extract(zip_path, archive.members, raw_dir)
    log.info("Extracted %d files from %s", len(files), zip_path.name)
    return raw_dir / archive.name


def download_all(raw_dir: Path, enrich: bool = True, force: bool = False) -> dict[str, Path]:
    out = {"ml-1m": fetch(ML_1M, raw_dir, force)}
    if enrich:
        out["ml-32m"] = fetch(ML_32M, raw_dir, force)
    return out
