"""Print the player's manual, docs/README.md, as a PDF.

    python3 tools/docs/render_manual.py OUT.pdf [--links URL]

The manual renders with python-markdown into one HTML page styled for print,
and headless Chrome prints the page to OUT.pdf. The contents' links to the
manual's own headings stay links within the PDF, and the script stops if one
names a heading that doesn't exist. A relative link to another file in docs/
means nothing in a PDF, so it points under URL, such as
https://github.com/OWNER/REPO/blob/COMMIT/docs, or becomes plain text without
--links. Chrome is the first of $CHROME, google-chrome, google-chrome-stable,
chromium, and chromium-browser on the PATH.
"""
import os, re, shutil, subprocess, sys, tempfile

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
MANUAL = os.path.join(REPO, "docs", "README.md")
CHROMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")

CSS = """
@page {
  size: letter;
  margin: 0.75in 0.8in;
  @bottom-center { content: counter(page); font: 9pt "DejaVu Sans", sans-serif; color: #6b645a; }
}
body { font: 10.5pt/1.45 "DejaVu Sans", "Liberation Sans", Arial, sans-serif; color: #1f1c19; }
h1 { font-size: 19pt; text-align: center; margin: 0 0 18pt; }
h2 { font-size: 15pt; border-bottom: 1.5pt solid #1f1c19; padding-bottom: 2pt; margin: 22pt 0 8pt; }
h3 { font-size: 12.5pt; margin: 16pt 0 6pt; }
h4 { font-size: 11pt; margin: 12pt 0 4pt; }
h1, h2, h3, h4 { break-after: avoid; }
p, li { orphans: 3; widows: 3; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 12pt; font-size: 9.5pt; }
th, td { border: 0.75pt solid #b8b0a3; padding: 3pt 6pt; text-align: left; vertical-align: top; }
th { background: #eee8dc; }
tr { break-inside: avoid; }
a { color: #1f4f8f; text-decoration: none; }
code { font: 9pt "DejaVu Sans Mono", monospace; }
"""


def chrome():
    for name in (os.environ.get("CHROME"),) + CHROMES:
        path = name and shutil.which(name)
        if path:
            return path
    sys.exit("no Chrome found: set CHROME or install " + ", ".join(CHROMES))


def page(links):
    body = markdown.markdown(open(MANUAL, encoding="utf-8").read(),
                             extensions=["tables", "toc", "sane_lists"])
    ids = set(re.findall(r' id="([^"]+)"', body))
    missing = sorted(set(re.findall(r'href="#([^"]+)"', body)) - ids)
    if missing:
        sys.exit("docs/README.md links to headings it doesn't have: " + ", ".join(missing))

    def relink(m):
        href, text = m.group(1), m.group(2)
        if re.match(r"#|[a-z]+:", href):
            return m.group(0)
        return f'<a href="{links.rstrip("/")}/{href}">{text}</a>' if links else text
    body = re.sub(r'<a href="([^"]*)">(.*?)</a>', relink, body)
    title = re.sub(r"<[^>]+>", "", re.search(r"<h1[^>]*>(.*?)</h1>", body).group(1))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f"<title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>")


def main():
    args = sys.argv[1:]
    links = None
    if "--links" in args:
        k = args.index("--links")
        if k + 1 >= len(args):
            sys.exit("--links needs a URL")
        links = args[k + 1]
        del args[k:k + 2]
    if len(args) != 1 or args[0].startswith("-"):
        sys.exit("usage: render_manual.py OUT.pdf [--links URL]")
    out = os.path.abspath(args[0])
    if os.path.exists(out):
        os.remove(out)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "manual.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(page(links))
        # --no-sandbox lets Chrome run as root and inside containers. The page
        # it prints is this script's own.
        r = subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu",
                            "--no-pdf-header-footer", f"--print-to-pdf={out}", "file://" + src],
                           capture_output=True, text=True)
    if r.returncode or not os.path.exists(out) or not os.path.getsize(out):
        sys.exit(f"Chrome didn't print {out} (exit {r.returncode}):\n{r.stderr.strip()}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
