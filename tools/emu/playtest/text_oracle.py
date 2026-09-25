"""The text oracle: compare a textbox actually seen in play against what
assets/strings.js says it should show, so a wrong string, a bad wrap, or a
wrong live value fails rather than passing on the tilemap read alone.
Needs node to load strings.js.

Reuses strings_fit.py's tokenizer so the wrap logic has one implementation,
not two that can drift apart -- but renders each %param as its actual live
value (a real monster name, a real damage roll) rather than modeling the
compiler's assumed column width, since the point here is "does this exact
screen match this exact string", not "could any value ever overflow".
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "audit"))
from strings_fit import _tokenize, DIRECT_SUBS, MAX_LINE  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from drive import log  # noqa: E402

import json
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)) + os.sep
STRINGS_JS = ROOT + "assets/strings.js"

_namespaces = None


def namespaces():
    global _namespaces
    if _namespaces is None:
        out = subprocess.run(
            ["node", "-e", "console.log(JSON.stringify(require(process.argv[1])))", STRINGS_JS],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        _namespaces = json.loads(out.stdout)
    return _namespaces


# tile id -> what window_text()/bg_text() show for it, for every direct
# substitution the compiler recognizes (encodeString's DirectSubstitutions
# in tools/strings2c: delta = tile - 0x80, and the harness's own decode is
# chr((tile - 0x80) & 0xFF)) -- both start from the same tile id, so they
# always agree.
_SUB_TILE = {
    ':elipsis:': 0xE0, ':regen:': 0xFB, ':atk:': 0xDD, ':gil:': 0xA4,
    ':soulcoin:': 0xA5, ':arrow:': 0xA6, ':lquo:': 0xA2, ':rquo:': 0xA3,
}
SUB_CHAR = {k: (chr((v - 0x80) & 0xFF) if 32 <= ((v - 0x80) & 0xFF) < 127 else '?')
            for k, v in _SUB_TILE.items()}


def expected_pages(ns, key, params=None):
    """The exact text window_text()/bg_text() should show for strings.js's
    ns.key, given real values for any %params it contains (e.g.
    monster='Bugbear', damage=7). Returns a list of page strings, each
    already wrapped to <=4 lines and joined the same way read_textbox()
    joins OCR'd lines (a single space), so the two are directly comparable."""
    params = params or {}
    value = namespaces()[ns]['strings'][key]
    value = value.replace('...', ':elipsis:')

    line, lines, pages = '', [], []

    def flush_line():
        nonlocal line
        lines.append(line)
        line = ''

    def flush_page():
        flush_line()
        nonlocal lines
        pages.append(' '.join(l for l in lines if l).strip())
        lines = []

    col = 0
    for tok in _tokenize(value):
        if tok.startswith('%'):
            name = tok[1:]
            if name not in params:
                raise KeyError(f"{ns}.{key} needs a live value for {tok} -- pass params={{'{name}': ...}}")
            text = str(params[name])
        elif tok in DIRECT_SUBS:
            text = SUB_CHAR.get(tok, '?')
        elif tok == '\n':
            flush_line()
            col = 0
            continue
        elif tok == '\f':
            flush_page()
            col = 0
            continue
        else:
            text = tok
            while len(text) > MAX_LINE:
                left, text = text[:MAX_LINE - 1] + '-', text[MAX_LINE - 1:]
                if col + len(left) > MAX_LINE:
                    flush_line(); col = 0
                line += left; col += len(left)
                if len(lines) == 4:
                    flush_page(); col = 0

        if col + len(text) > MAX_LINE:
            flush_line()
            col = 0
            if len(lines) == 4:
                flush_page()
        line += text
        col += len(text)

    flush_page()
    return [p for p in pages if p]


def normalize(text):
    """Collapse the whitespace differences between an OCR join and a
    wrap-then-join (trailing spaces on a wrapped line, doubled spaces at a
    join) without touching the words themselves."""
    return ' '.join(text.split())


def check_textbox(ns, key, seen_pages, params=None, note=""):
    """Compare read_textbox()'s OCR'd pages against ns.key's expected text.
    Logs a PASS/FAIL line and returns True/False. `note` is context for the log line (where this was seen)."""
    try:
        expected = [normalize(p) for p in expected_pages(ns, key, params)]
    except KeyError as e:
        log(f"  !! TEXT ORACLE {ns}.{key} ({note}): {e}")
        return False
    seen = [normalize(p) for p in seen_pages]
    ok = seen == expected
    if ok:
        log(f"  TEXT ORACLE OK {ns}.{key} ({note}): {seen!r}")
    else:
        log(f"  !! TEXT ORACLE MISMATCH {ns}.{key} ({note})\n"
            f"       expected: {expected!r}\n"
            f"       seen:     {seen!r}")
    return ok
