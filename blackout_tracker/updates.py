"""GitHub release discovery and verified portable payload preparation (no installation)."""
import hashlib
import json
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from blackout_tracker.version import VERSION

REPOSITORY = 'akoval29/BlackoutTracker'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
PAYLOAD_NAMES = {'Blackout tracker.exe', '_internal', 'Updater.exe', 'portable.flag', 'README.txt', 'licenses'}
MAX_DOWNLOAD = 512 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)(\.(0|[1-9]\d*))?', value):
        raise ValueError('Версія має формат v1.2.3 (або v1.2).')
    parts = tuple(int(part) for part in value.removeprefix('v').split('.'))
    return parts + (0,) * (3 - len(parts))


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    digest: str
    size: int
    notes: str


def parse_release(value, current=VERSION):
    if value.get('draft') or value.get('prerelease'):
        return None
    tag = value['tag_name']
    if version_tuple(tag) <= version_tuple(current):
        return None
    version = tag.removeprefix('v')
    name = f'BlackoutTracker-{version}-win-x64.zip'
    assets = [a for a in value.get('assets', []) if a.get('name') == name and a.get('state') == 'uploaded']
    if len(assets) != 1:
        raise ValueError(f'Реліз не містить готового файлу {name}.')
    asset = assets[0]
    url = asset.get('browser_download_url', '')
    if url != f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}':
        raise ValueError('Неочікувана адреса файлу оновлення.')
    digest = asset.get('digest') or ''
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
        raise ValueError('GitHub ще не надав SHA-256 файлу. Спробуйте пізніше.')
    size = asset.get('size')
    if type(size) is not int or not 0 < size <= MAX_DOWNLOAD:
        raise ValueError('Некоректний розмір оновлення.')
    return Release(version, url, digest[7:].lower(), size, str(value.get('body') or '')[:4000])


def request(url):
    return urllib.request.Request(url, headers={'User-Agent': f'BlackoutTracker/{VERSION}', 'Accept': 'application/vnd.github+json' if url == API_URL else 'application/octet-stream'})


def check_release():
    try:
        with urllib.request.urlopen(request(API_URL), timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError('Завелика відповідь GitHub.')
            return parse_release(json.loads(raw))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def extract_payload(archive, destination):
    """Validate every member before writing; never accept user data or path escapes."""
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > 20000 or sum(m.file_size for m in members) > MAX_UNPACKED:
            raise ValueError('Архів перевищує дозволений розмір.')
        seen = set()
        for member in members:
            path = PurePosixPath(member.filename)
            parts = path.parts
            key = member.filename.rstrip('/').casefold()
            if (not parts or parts[0] != 'BlackoutTracker' or path.is_absolute()
                    or '\\' in member.filename or any(p in ('.', '..') or ':' in p or p.endswith((' ', '.')) for p in parts)
                    or (len(parts) > 1 and parts[1] not in PAYLOAD_NAMES)
                    or stat.S_ISLNK(member.external_attr >> 16) or key in seen):
                raise ValueError('Небезпечна або несумісна структура ZIP.')
            seen.add(key)
        bundle.extractall(destination)
    payload = destination / 'BlackoutTracker'
    for name in ('Blackout tracker.exe', 'Updater.exe', 'portable.flag'):
        if not (payload / name).is_file():
            raise ValueError(f'У збірці немає {name}.')
    if not (payload / '_internal').is_dir():
        raise ValueError('У збірці немає _internal.')
    return payload


def prepare_update(release, base, progress=lambda value: None, cancelled=lambda: False):
    """Only called after the user's explicit update click. Stage on the same volume."""
    workspace = Path(tempfile.mkdtemp(prefix='.blackout-update-', dir=base))
    try:
        archive = workspace / 'update.zip'
        digest = hashlib.sha256()
        downloaded = 0
        deadline = time.monotonic() + 600
        with urllib.request.urlopen(request(release.url), timeout=20) as response, archive.open('wb') as output:
            while True:
                if cancelled():
                    raise ValueError('Завантаження скасовано.')
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > release.size or time.monotonic() > deadline:
                    raise ValueError('Перевищено розмір або час завантаження.')
                digest.update(chunk)
                output.write(chunk)
                progress(int(downloaded * 100 / release.size))
        if downloaded != release.size or digest.hexdigest() != release.digest:
            raise ValueError('Перевірка цілісності оновлення не пройдена.')
        if cancelled():
            raise ValueError('Завантаження скасовано.')
        extract_payload(archive, workspace / 'payload')
        # Run the currently installed, trusted helper outside the files being replaced.
        shutil.copy2(base / 'Updater.exe', workspace / 'Updater.exe')
        archive.unlink()
        return workspace
    except Exception:
        shutil.rmtree(workspace)
        raise
