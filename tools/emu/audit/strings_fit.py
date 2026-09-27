"""Fit-check every string in assets/strings.js against the line/page limits
the game's text writer actually enforces.

tools/strings2c reimplements the wrap by hand and checks only the 90-char
total; it never counts lines per page, so a string that wraps past 4 lines
compiles cleanly and silently costs the player an extra, unplanned page
turn. This is that missing check, run against the same algorithm: tokens
are words, `%name` parameters, `:icon:` substitutions and `\n`/`\f`; a word
longer than 18 characters is split with a trailing hyphen; a line wraps
when the next token would pass 18 characters; `...` becomes the ellipsis
tile first. A line breaks only at a space, so a symbol or parameter written
against a word moves down with that word, and a space the break falls on is
dropped. Ported from strings2c's encodeString(), including its one quirk: an
explicit `\f` does not reset the column count used for the next wrap
decision (only a literal source `\n` does), which matters only for a string
that uses `\f`.

The wrap never lets a line pass 18 columns, so what this reports is pages
that run past 4 lines, hyphenated word splits, and strings within 5
characters of the 90-character limit.
"""
import os
import re
from shared import load_namespaces

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)) + os.sep

MAX_LINE = 18
MAX_TOKEN = 18
MAX_PAGE_LINES = 4
MAX_STRING = MAX_LINE * 5  # 90; matches strings2c's own maxStringLength

# token -> (encoded format code, assumed max width). Mirrors strings2c's `params`.
PARAMS = {
    '%damage': ('%u', 4),
    '%aspect': ('%s', 5),
    '%monster': ('%s', 15),
    '%c': ('%c', 1),
    '%exp': ('%u', 3),
    '%level': ('%u', 2),
    '%1u': ('%u', 1),
}

DIRECT_SUBS = {
    ':elipsis:', ':regen:', ':atk:', ':gil:', ':soulcoin:', ':arrow:', ':lquo:', ':rquo:',
}

TOKEN_RE = re.compile(r'([ ]+)|([%][a-z]+)|(:[a-z-]+:)|([\n\f])|([^\s]+)')
SUB_RE = re.compile(r'(:[a-z-]+:)')
PARAM_RE = re.compile(r'([%][a-z]+)')


def _tokenize(s):
    tokens = [next(g for g in m if g) for m in TOKEN_RE.findall(s)]

    def expand(toks, pattern):
        result = []
        for t in toks:
            parts = [p for p in pattern.split(t) if p != '']
            result.extend(parts)
        return result

    tokens = expand(tokens, SUB_RE)
    tokens = expand(tokens, PARAM_RE)
    return tokens


class FitError(Exception):
    pass


def build_imr(ns, key, s, param_widths=None):
    """Token list -> intermediate reps: {type, token, encoded, length}."""
    widths = {k: v[1] for k, v in PARAMS.items()}
    if param_widths:
        widths.update(param_widths)

    s = s.replace('...', ':elipsis:')
    imr = []
    for tok in _tokenize(s):
        if tok.startswith('%'):
            if tok not in PARAMS:
                raise FitError(f"{ns}.{key}: unknown parameter {tok!r}")
            code, _ = PARAMS[tok]
            imr.append({'type': 'param', 'token': tok, 'encoded': code, 'length': widths[tok]})
            continue
        if SUB_RE.fullmatch(tok) and tok in DIRECT_SUBS:
            imr.append({'type': 'sub', 'token': tok, 'encoded': tok, 'length': 1})
            continue
        if tok == '\n':
            imr.append({'type': 'control', 'token': tok, 'encoded': '\\n', 'length': 1})
            continue
        if tok == '\f':
            imr.append({'type': 'control', 'token': tok, 'encoded': '\\f', 'length': 1})
            continue
        while len(tok) > MAX_TOKEN:
            left = tok[:MAX_TOKEN - 1] + '-'
            imr.append({'type': 'text', 'token': left, 'encoded': left, 'length': len(left), 'hyphenated': True})
            tok = tok[MAX_TOKEN - 1:]
        if len(tok) > 0:
            imr.append({'type': 'text', 'token': tok, 'encoded': tok, 'length': len(tok)})
    return imr


def wrap(imr):
    """Mirrors strings2c's line-wrap pass. Returns (encoded, total_len,
    page_line_counts, line_widths):

    - page_line_counts is the *uncapped* line count per \\f-delimited
      section (always one section unless \\f is used) -- the runtime
      auto-pages every 4 lines regardless, so a section reported here
      above 4 means the string will turn an extra, unplanned page.
    - line_widths is every line's column width, in the same not-reset-
      after-\\f accounting strings2c itself uses for wrap decisions (see
      the module docstring); harmless while no string uses \\f.
    """
    result = []
    current_line_len = 0
    total_len = 0
    pages = [1]  # line count of the section since the last \f (or start)
    line_widths = []
    word_start = 0  # index in result of the current word's first piece
    word_length = 0  # columns that word takes on the current line
    after_break = True

    for rep in imr:
        if rep['encoded'] == '\\n':
            line_widths.append(current_line_len)
            current_line_len = 0
            result.append('\\n')
            total_len += 1
            pages[-1] += 1
            after_break = True
            continue
        is_space = rep['type'] == 'text' and rep['token'].strip(' ') == ''
        is_break = is_space or rep['type'] == 'control'
        joins_word = not is_break and not after_break
        if current_line_len + rep['length'] > MAX_LINE:
            if (joins_word and word_length < current_line_len
                    and word_length + rep['length'] <= MAX_LINE):
                line_widths.append(current_line_len - word_length)
                result.insert(word_start, '\\n')
                word_start += 1
                current_line_len = word_length
            else:
                line_widths.append(current_line_len)
                result.append('\\n')
                current_line_len = 0
                word_start = len(result)
                word_length = 0
            total_len += 1
            pages[-1] += 1
            if is_space and current_line_len == 0:
                after_break = True
                continue
        if not joins_word:
            word_start = len(result)
            word_length = 0
        current_line_len += rep['length']
        total_len += rep['length']
        result.append(rep['encoded'])
        word_length += rep['length']
        after_break = is_break
        if rep['encoded'] == '\\f':
            pages.append(1)

    line_widths.append(current_line_len)
    return ''.join(result), total_len, pages, line_widths


def check_string(ns, key, value, param_widths=None):
    imr = build_imr(ns, key, value, param_widths)
    encoded, total_len, pages, widths = wrap(imr)
    hyphenated = [e['token'] for e in imr if e.get('hyphenated')]
    return {
        'ns': ns, 'key': key, 'value': value,
        'encoded': encoded, 'total_len': total_len, 'pages': pages,
        'widths': widths, 'hyphenated': hyphenated,
        'max_page_lines': max(pages) if pages else 0,
    }


# ---------------------------------------------------------------------------
# Self-test: six fixtures with hand-computed expected output.
# ---------------------------------------------------------------------------

def self_test():
    cases = []

    # 1. No wrap needed.
    imr = build_imr('t', 'a', 'Hi there')
    enc, total, pages, widths = wrap(imr)
    cases.append(('fixture1 encoded', enc, 'Hi there'))
    cases.append(('fixture1 total_len', total, 8))
    cases.append(('fixture1 pages', pages, [1]))

    # 2. Exactly one auto-wrap at a word boundary; the space before the
    # wrap point is kept (only the runtime's hard-wrap drops a leading
    # space, not the compiler).
    imr = build_imr('t', 'b', 'AAAAAAAAAA BBBBBBBBBB')
    enc, total, pages, widths = wrap(imr)
    cases.append(('fixture2 encoded', enc, 'AAAAAAAAAA \\nBBBBBBBBBB'))
    cases.append(('fixture2 total_len', total, 22))
    cases.append(('fixture2 pages', pages, [2]))
    cases.append(('fixture2 line widths', widths, [11, 10]))

    # 3. A word over 18 chars forces a hyphenated split, followed by a
    # param whose encoded form is the %u/%s/%c format code, not the token.
    imr = build_imr('t', 'c', 'supercalifragilisticexpialidocious %exp')
    enc, total, pages, widths = wrap(imr)
    cases.append(('fixture3 encoded', enc, 'supercalifragilis-\\nticexpialidocious \\n%u'))
    cases.append(('fixture3 total_len', total, 41))
    cases.append(('fixture3 pages', pages, [3]))
    cases.append(('fixture3 hyphenated', [e['token'] for e in imr if e.get('hyphenated')], ['supercalifragilis-']))

    # 4. An ellipsis that would start a line moves down with its word.
    imr = build_imr('t', 'd', 'AAAAAAAAA BBBBBBBB...')
    enc, total, pages, widths = wrap(imr)
    cases.append(('fixture4 encoded', enc, 'AAAAAAAAA \\nBBBBBBBB:elipsis:'))
    cases.append(('fixture4 total_len', total, 20))
    cases.append(('fixture4 line widths', widths, [10, 9]))

    # 5. A line after a break holds all 18 columns.
    imr = build_imr('t', 'e', 'AAAAAAAAAA BBBBBBBBBBBBBBBB C')
    enc, total, pages, widths = wrap(imr)
    cases.append(('fixture5 encoded', enc, 'AAAAAAAAAA \\nBBBBBBBBBBBBBBBB C'))
    cases.append(('fixture5 line widths', widths, [11, 18]))

    # 6. A space the break falls on is dropped.
    imr = build_imr('t', 'f', 'AAAAAAAAAAAAAAAAAA BBB')
    enc, total, pages, widths = wrap(imr)
    cases.append(('fixture6 encoded', enc, 'AAAAAAAAAAAAAAAAAA\\nBBB'))
    cases.append(('fixture6 total_len', total, 22))
    cases.append(('fixture6 line widths', widths, [18, 3]))

    failed = [c for c in cases if c[1] != c[2]]
    if failed:
        print("self-test: FAIL")
        for name, got, want in failed:
            print(f"  {name}: got {got!r}, want {want!r}")
        return False
    print(f"self-test: PASS ({len(cases)} checks across 6 fixtures)")
    return True


def main():
    if not self_test():
        raise SystemExit(1)

    namespaces = load_namespaces()

    over_page = []
    hyphenated = []
    near_limit = []

    for ns, data in namespaces.items():
        for key, value in data['strings'].items():
            if value == '':
                continue
            r = check_string(ns, key, value)
            if r['max_page_lines'] > MAX_PAGE_LINES:
                over_page.append(r)
            if r['hyphenated']:
                hyphenated.append(r)
            if MAX_STRING - r['total_len'] <= 5:
                near_limit.append(r)

    print(f"strings checked: {sum(len(d['strings']) for d in namespaces.values())}")
    print()

    print(f"=== Pages over {MAX_PAGE_LINES} lines (informational: the writer turns the page on its own): {len(over_page)} ===")
    for r in over_page:
        print(f"  .. {r['ns']}.{r['key']} pages={r['pages']}\n       {r['value']!r}")

    print(f"\n=== Hyphenated word splits: {len(hyphenated)} ===")
    for r in hyphenated:
        print(f"  .. {r['ns']}.{r['key']} split={r['hyphenated']}\n       {r['value']!r}")

    print(f"\n=== Within 5 chars of the {MAX_STRING}-char limit: {len(near_limit)} ===")
    for r in near_limit:
        print(f"  .. {r['ns']}.{r['key']} total_len={r['total_len']}\n       {r['value']!r}")


if __name__ == '__main__':
    main()
