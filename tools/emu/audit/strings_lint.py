"""Grammar and consistency lint over every string in assets/strings.js.

A finder, not a judge -- every list below needs a human pass, because
English has more exceptions than a regex. Checks: a/an against the next
word's first letter; a plural noun after "a"/"an"; doubled spaces; a space
before punctuation; a namespace where most strings end in terminal
punctuation and a few don't; a string that names the SP or MP pool
directly (the pool's label is class-dependent, see map.menu.c's
is_magic_class()); ALL CAPS
mixed with sentence case in the same namespace; British spellings; and a
literal Unicode ellipsis character, which (unlike three ASCII dots) the
string compiler does not turn into the ellipsis tile.
"""
import os
import re
from shared import load_namespaces

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)) + os.sep

# Words that look plural (end in s) but are not, so they don't spam the
# a/an-plural check. Not exhaustive; the check is a finder.
NOT_PLURAL = {
    'status', 'bonus', 'menace', 'darkness', 'sickness', 'this', 'gas',
    'sorceress', 'princess', 'glass', 'class', 'series', 'species', 'is',
    'was', 'has', 'his', 'yes', 'always', 'various', 'famous', 'serious',
}

# A vowel-sound exception list for the a/an check (both directions).
AN_EXCEPTIONS_TAKE_A = {'unicorn', 'unique', 'user', 'one'}
A_EXCEPTIONS_TAKE_AN = {'hour', 'honest', 'heir'}

BRITISH = {
    'colour': 'color', 'armour': 'armor', 'favour': 'favor',
    'flavour': 'flavor', 'honour': 'honor', 'neighbour': 'neighbor',
    'centre': 'center', 'theatre': 'theater', 'defence': 'defense',
    'licence': 'license', 'travelling': 'traveling', 'cancelled': 'canceled',
    'grey': 'gray', 'realise': 'realize', 'organise': 'organize',
}

UI_LABEL_KEYS = {'yes', 'no', 'save', 'quit', 'back', 'cancel', 'ok', 'exit', 'empty'}


def strip_tokens(s):
    """Drop %params and :subs: so word-boundary checks see plain prose."""
    s = re.sub(r'%[a-z]+', '', s)
    s = re.sub(r':[a-z-]+:', '', s)
    return s


def check_a_an(ns, key, value, findings):
    text = strip_tokens(value)
    for m in re.finditer(r'\b([Aa])\s+(\w+)', text):
        article, word = m.group(1), m.group(2)
        low = word.lower()
        if low in AN_EXCEPTIONS_TAKE_A:
            continue
        if low[:1] in 'aeiou':
            findings.append((ns, key, f"'{article} {word}' -- likely wants 'an'", value))
    for m in re.finditer(r'\b([Aa]n)\s+(\w+)', text):
        article, word = m.group(1), m.group(2)
        low = word.lower()
        if low in A_EXCEPTIONS_TAKE_AN:
            continue
        if low[:1] not in 'aeiou':
            findings.append((ns, key, f"'{article} {word}' -- likely wants 'a'", value))


def check_plural_after_article(ns, key, value, findings):
    text = strip_tokens(value)
    for m in re.finditer(r'\b(?:a|an)\s+(\w+s)\b', text, re.IGNORECASE):
        word = m.group(1)
        if word.lower() in NOT_PLURAL:
            continue
        if word.lower().endswith('ss') or word.lower().endswith('us'):
            continue
        findings.append((ns, key, f"'{word}' after an article -- looks plural", value))


def check_doubled_spaces(ns, key, value, findings):
    if '  ' in value:
        findings.append((ns, key, "doubled space", value))


def check_space_before_punct(ns, key, value, findings):
    if re.search(r' [.,!?;:]', value):
        findings.append((ns, key, "space before punctuation", value))


def check_unicode_ellipsis(ns, key, value, findings):
    if '…' in value:
        findings.append((ns, key, "Unicode ellipsis char (compiler only rewrites '...')", value))


def check_british(ns, key, value, findings):
    low = value.lower()
    for uk, us in BRITISH.items():
        if uk in low:
            findings.append((ns, key, f"British spelling '{uk}' (-> '{us}')", value))


def check_mp_sp(ns, key, value, findings):
    if re.search(r'\bMP\b', value) or re.search(r'\bSP\b', value):
        findings.append((ns, key, "names the SP/MP pool directly", value))


def terminal_punct_report(namespaces):
    """Per namespace: strings ending in terminal punctuation vs not, over
    prose-shaped strings only (skip empty, pure-UI-label, or single-token
    values, which are not sentences)."""
    out = []
    for ns, data in namespaces.items():
        with_punct, without = [], []
        for key, value in data['strings'].items():
            if not value or key in UI_LABEL_KEYS:
                continue
            text = strip_tokens(value).rstrip()
            if not text or ' ' not in text.strip():
                continue  # not sentence-shaped
            if text[-1:] in '.!?':
                with_punct.append(key)
            else:
                without.append(key)
        if with_punct and without and len(with_punct) >= 2 * len(without):
            out.append((ns, with_punct, without))
    return out


def caps_mix_report(namespaces):
    """Per namespace: keys whose value is pure UI-style ALL CAPS prose
    alongside keys that are sentence case, over letters-only content."""
    out = []
    for ns, data in namespaces.items():
        caps, sentence = [], []
        for key, value in data['strings'].items():
            text = strip_tokens(value)
            letters = re.sub(r'[^A-Za-z]', '', text)
            if len(letters) < 4:
                continue
            if letters.isupper():
                caps.append(key)
            elif letters[:1].isupper() or letters[:1].islower():
                sentence.append(key)
        if caps and sentence:
            out.append((ns, caps, sentence))
    return out


def self_test():
    findings = []
    check_a_an('t', 'k1', 'a elixir and an cube', findings)
    check_plural_after_article('t', 'k2', 'a potions', findings)
    check_doubled_spaces('t', 'k3', 'two  spaces', findings)
    check_space_before_punct('t', 'k4', 'oops , comma', findings)
    check_unicode_ellipsis('t', 'k5', 'wait…', findings)
    check_british('t', 'k6', 'nice armour', findings)
    check_mp_sp('t', 'k7', 'restores SP', findings)
    got = {(f[0], f[1]) for f in findings}
    want = {('t', k) for k in ('k1', 'k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7')}
    # k1 fires twice (a->an on 'elixir', an->a on 'cube'); dedupe key check only.
    if want - got:
        print("self-test: FAIL")
        print(f"  missing: {want - got}")
        print(f"  findings: {findings}")
        return False
    print(f"self-test: PASS ({len(findings)} findings across 7 fixtures, one fires twice)")
    return True


def main():
    if not self_test():
        raise SystemExit(1)

    namespaces = load_namespaces()
    findings = []
    for ns, data in namespaces.items():
        for key, value in data['strings'].items():
            if not value:
                continue
            check_a_an(ns, key, value, findings)
            check_plural_after_article(ns, key, value, findings)
            check_doubled_spaces(ns, key, value, findings)
            check_space_before_punct(ns, key, value, findings)
            check_unicode_ellipsis(ns, key, value, findings)
            check_british(ns, key, value, findings)
            check_mp_sp(ns, key, value, findings)

    print(f"strings checked: {sum(len(d['strings']) for d in namespaces.values())}")
    print(f"\n=== Regex findings (a/an, plural, spacing, ellipsis, British, MP/SP): {len(findings)} ===")
    for ns, key, why, value in findings:
        print(f"  .. {ns}.{key}: {why}\n       {value!r}")

    punct = terminal_punct_report(namespaces)
    print(f"\n=== Namespaces with inconsistent terminal punctuation: {len(punct)} ===")
    for ns, with_p, without in punct:
        print(f"  .. {ns}: {len(with_p)} end with punctuation, {len(without)} don't -> {without}")

    caps = caps_mix_report(namespaces)
    print(f"\n=== Namespaces mixing ALL CAPS and sentence case: {len(caps)} ===")
    for ns, c, s in caps:
        print(f"  .. {ns}: CAPS={c}\n       sentence={s}")


if __name__ == '__main__':
    main()
