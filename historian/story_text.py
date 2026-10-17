"""Opt-in, read-only game-localisation enrichment for named archive projects.

The player's installed Stellaris localisation describes what a scripted project
means, but DOES NOT establish which option they chose or how it ended. No game
files or full copyrighted story text are copied into Historian's patch.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os
import re
import zipfile

_LINE = re.compile(r'^\s*([^\s:#]+):\d*\s+"((?:[^"\\]|\\.)*)"\s*$', re.M)
_FORMAT = re.compile(r'§[A-Za-z0-9!]|£[A-Za-z_]+£?|\\n')
_VARIABLE = re.compile(r'\$[A-Za-z0-9_.]+\$|\[[^]]+\]|\{[^}]+\}')


def _roots() -> list[Path]:
    roots: list[Path] = []
    path_file = Path(__file__).resolve().parents[1] / 'data' / 'stellaris_game_dir.txt'
    stored = path_file.read_text(encoding='utf-8').strip() if path_file.is_file() else ''
    if stored:
        roots.append(Path(stored))
    explicit = os.environ.get('STELLARIS_GAME_DIR', '').strip()
    if explicit:
        roots.append(Path(explicit))
    for disk in ('C:', 'D:', 'E:', 'F:', 'G:'):
        for stem in ('Program Files (x86)/Steam', 'Program Files/Steam', 'Steam', 'SteamLibrary', 'Games/SteamLibrary'):
            roots.append(Path(disk) / stem / 'steamapps/common/Stellaris')
    # Consult Steam's libraryfolders.vdf for additional game libraries.
    for root in list(roots):
        steam = root.parent.parent.parent
        vdf = steam / 'config/libraryfolders.vdf'
        if vdf.is_file():
            try:
                data = vdf.read_text(encoding='utf-8', errors='replace')
                for loc in re.findall(r'"path"\s*"([^\"]+)"', data):
                    roots.append(Path(loc.replace('\\\\', '\\')) / 'steamapps/common/Stellaris')
            except OSError:
                pass
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        k = str(r).casefold()
        if k not in seen and (r / 'localisation').is_dir():
            seen.add(k)
            out.append(r)
    return out


def _take(index: dict[str,str], content: str) -> None:
    for match in _LINE.finditer(content):
        index[match.group(1)] = match.group(2).replace(r'\"', '"')


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str,str], str]:
    values: dict[str,str] = {}
    paths: list[str] = []
    for root in _roots():
        paths.append(str(root))
        for f in sorted((root/'localisation'/'english').rglob('*_l_english.yml')):
            try:
                _take(values, f.read_text(encoding='utf-8-sig', errors='replace'))
            except OSError:
                continue
        # DLC localisation is stored inside the game's installed DLC packages.
        for f in sorted((root/'dlc').glob('**/*.zip')):
            try:
                with zipfile.ZipFile(f) as z:
                    for member in z.namelist():
                        path = member.replace('\\', '/').lower()
                        if '/localisation/english/' not in '/' + path or not path.endswith('_l_english.yml'):
                            continue
                        _take(values, z.read(member).decode('utf-8-sig', errors='replace'))
            except (OSError, zipfile.BadZipFile):
                continue
    return values, ', '.join(paths)


def game_description(key: str | None) -> tuple[str | None, str]:
    """Return only readable flavour context, never a claimed campaign outcome."""
    if not key:
        return None, 'No archive project key'
    index, roots = _index()
    if not index:
        return None, ('Stellaris installation not detected; set STELLARIS_GAME_DIR to its installation folder.'
                      if not roots else 'English localisation unavailable')
    desc = None
    for candidate in (key + '_DESC', key + '_desc', key + '_description', key + '_DESCRIPTION', key):
        s = index.get(candidate)
        if not s:
            continue
        # Keep unresolved game-side substitutions out of historical prose.
        s = _FORMAT.sub(' ', s)
        s = _VARIABLE.sub('', s)
        s = re.sub(r'\s+', ' ', s).strip(' \t.,;')
        if len(s) < 45 or len(s) > 950 or s.count('§') or s.count('$') or s.count('['):
            continue
        desc = s.rstrip('.') + '.'
        break
    return desc, f'Scripted project {key}; installed Stellaris localisation'


def set_game_installation(path: str) -> str:
    value=str(path or '').strip().strip('"')
    if not value:
        raise ValueError('Provide the folder containing Stellaris.exe and localisation.')
    folder=Path(value)
    if not (folder / 'localisation' / 'english').is_dir():
        raise ValueError('Cannot find the localisation/english folder in that location.')
    config=Path(__file__).resolve().parents[1]/'data'/'stellaris_game_dir.txt'
    config.parent.mkdir(parents=True,exist_ok=True)
    config.write_text(value+'\n',encoding='utf-8')
    _index.cache_clear()
    return value


def catalogue_status() -> dict:
    idx, roots = _index()
    return {'game_installation': roots or None, 'localisation_keys': len(idx)}

