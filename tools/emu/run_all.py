#!/usr/bin/env python3
"""Run every suite and report the total.

Each suite boots the ROM from the title screen and plays to whatever it needs;
a full run of every suite takes about 20 minutes. Exits non-zero if any check
failed.
"""
import glob, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = sorted(glob.glob(os.path.join(HERE, "t*.py")),
                key=lambda p: int(re.match(r"t(\d+)", os.path.basename(p)).group(1)))

total = passed = 0
failures = []
for path in SUITES:
    name = os.path.basename(path)[:-3]
    r = subprocess.run([sys.executable, path], cwd=HERE, capture_output=True, text=True)
    m = re.findall(r"(\d+)/(\d+) passed", r.stdout)
    if not m:
        failures.append(name)
        print(f"{name:<28} no result ({r.returncode})")
        print("\n".join(r.stdout.strip().split("\n")[-5:]))
        continue
    p, q = (int(x) for x in m[-1])
    total += q
    passed += p
    if p != q:
        failures.append(name)
        for line in r.stdout.split("\n"):
            if line.startswith("FAIL"):
                print(f"  {line}")
    print(f"{name:<28} {p}/{q}")

print("-" * 40)
print(f"{passed}/{total} checks across {len(SUITES)} suites")
if failures:
    print("failed: " + ", ".join(failures))
sys.exit(1 if failures else 0)
