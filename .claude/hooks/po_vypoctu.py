#!/usr/bin/env python3
"""
Hooky pro demo v Claude Code – pravidla, která se VYNUCUJÍ (ne jen doporučují).

PreToolUse  (Bash): zablokuje `git push` do main a úpravy data/raw.
PostToolUse (Bash): po každém výpočtu pipeline (metriky/analyza/vystup) spustí validaci.
                    Když neprojde, vrátí kód 2 → Claude dostane chybu a musí ji řešit.
"""
import json
import re
import subprocess
import sys

udalost = sys.argv[1] if len(sys.argv) > 1 else ""
vstup = json.load(sys.stdin)
prikaz = (vstup.get("tool_input") or {}).get("command", "")

if udalost == "pre":
    if re.search(r"\bgit\s+push\b", prikaz):
        vetev = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
        if re.search(r"\bmain\b", prikaz) or vetev == "main":
            print("Blokováno pravidlem kurzu: do větve main se nepushuje. Pracuj ve větvi tym-<cislo>.",
                  file=sys.stderr)
            sys.exit(2)
    if re.search(r"(>|rm|mv|sed -i|cp\s+\S+)\s*\S*data/raw/", prikaz):
        print("Blokováno pravidlem kurzu: data/raw/ se nemění.", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)

if udalost == "post":
    m = re.search(r"pipeline\.py\s+(metriky|analyza|vystup)\b", prikaz)
    if not m:
        sys.exit(0)
    config = re.search(r"--config\s+(\S+)", prikaz)
    vystup = re.search(r"--vystup\s+(\S+)", prikaz)
    cmd = [sys.executable, ".claude/skills/datova-pipeline/scripts/pipeline.py", "validace",
           "--config", config.group(1) if config else "metriky/kpe.yaml"]
    if vystup:
        cmd += ["--vystup", vystup.group(1)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("Automatická validace po výpočtu NEPROŠLA:\n" + r.stdout[-2000:], file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
