# AI analytika – workshop VŠE

Projekt pro analýzu dat s Claude. Claude tu má pravidla, hotové výpočty a kontroly,
takže všichni počítáte stejné metriky stejně – a vy se soustředíte na otázky a závěry.

## Jak začít
1. Otevři projekt v aplikaci Claude a založ nové vlákno.
2. Napiš např.: *„Jsem tým 3, chci analyzovat kávomaty. Zajímá mě, které lokality se nevyplatí.“*
3. Claude tě provede kroky: **kontrola dat → čištění → metriky → analýza → výstup → validace**.
4. Když se Claude zeptá na rozhodnutí (co s chybějícími daty apod.), rozhodni a řekni proč.
5. Výsledný Excel si stáhni, dashboard dodělej v Excelu / Power BI.
6. Před odevzdáním napiš *„zkontroluj můj výstup“*. Když chceš práci uložit, napiš *„ulož to“*.

## Co tu je
| Složka | Co obsahuje |
|---|---|
| `data/raw/` | Původní data (KPE prodeje 2021, kávomaty Praha) – nemění se |
| `metriky/` | Definice metrik a čištění – „slovník“, podle kterého se počítá |
| `docs/` | Zadání, vzorový slide, harmonogram |
| `vystupy/` | Vaše výsledky (každý tým ve své větvi) |
| `.claude/` | Pravidla a dovednosti pro Clauda (spravuje lektor) |

## Datasety
- **KPE** – prodeje mléčných výrobků 2021, skutečnost vs. plán (`metriky/kpe.yaml`)
- **Kávomaty** – roční provoz 36 automatů v Praze (`metriky/kavomaty.yaml`, zadání v `docs/zadani_kavomaty.md`)

## Pro lektora
- Pravidla: `CLAUDE.md` · postup výpočtů: `.claude/skills/datova-pipeline/SKILL.md`
- Hooky (`.claude/settings.json`) vynucují validaci po výpočtu a zákaz pushe do `main` – demo pro Claude Code.
- Ruční běh: `python .claude/skills/datova-pipeline/scripts/pipeline.py kontrola --config metriky/kpe.yaml`
- Závislosti: `pip install -r requirements.txt`
