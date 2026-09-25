"""What the audits share: the repo root, a C comment stripper, and the
strings.js loader."""
import json, os, re, subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir))
STRINGS_JS = os.path.join(REPO, "assets", "strings.js")


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def strip_comments_and_strings(text):
    """Like strip_comments, but blanks string and char literals too, and
    keeps every newline in place so line numbers taken from the result still
    match the original file."""
    out, i, n = [], 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "//":
            j = text.find("\n", i); j = n if j == -1 else j
            out.append(" " * (j - i)); i = j
        elif two == "/*":
            j = text.find("*/", i + 2); j = n if j == -1 else j + 2
            out.append("".join(c if c == "\n" else " " for c in text[i:j])); i = j
        elif text[i] in ("'", '"'):
            quote = text[i]; j = i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append("".join(c if c == "\n" else " " for c in text[i:j])); i = j
        else:
            out.append(text[i]); i += 1
    return "".join(out)


def load_namespaces():
    """assets/strings.js as Python data, evaluated by node the way the build does."""
    out = subprocess.run(
        ["node", "-e", "console.log(JSON.stringify(require(process.argv[1])))", STRINGS_JS],
        cwd=REPO, capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)
