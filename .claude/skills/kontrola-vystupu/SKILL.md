---
name: kontrola-vystupu
description: Kontrola studentského výstupu (dashboard, slide, doporučení) před odevzdáním – čísla proti validovaným výpočtům, logika příběhu a srozumitelnost pro adresáta. Použij, když student řekne, že má hotovo, chce zpětnou vazbu nebo chce odevzdat.
---

# Kontrola výstupu před odevzdáním

Postupuj v pořadí. Výsledek shrň jako krátkou tabulku: kontrola · stav (OK / opravit) · co konkrétně.

## 1. Čísla
1. Spusť `pipeline.py validace` pro daný dataset. Když neprojde, dál nepokračuj.
2. Projdi každé číslo ve studentově výstupu (dashboard, slide, text) a dohledej ho
   v `vystupy/<dataset>/*.csv`. Číslo, které tam není, označ jako **neověřené**.
3. Zkontroluj jednotky a zaokrouhlení (t vs. kg, tis. vs. mil. Kč, % vs. procentní body).

## 2. Příběh (storytelling)
- Nadpis = hlavní sdělení celou větou, ne téma („Objem nad plánem, zisk zaostal“, ne „Výsledky 2021“).
- Každé tvrzení má pod sebou číslo, každý graf odpovídá na jednu otázku.
- Doporučení jsou konkrétní (kdo, co, o kolik) a vyplývají z dat, ne z obecných rad.
- Je jasné, pro koho výstup je a jaké rozhodnutí má podpořit?

## 3. Poctivost
- Předpoklady a odhady (např. ušlá tržba kvůli výpadkům) jsou označené jako odhad.
- Rozhodnutí z čištění (co bylo vyřazeno/doplněno a proč) jsou uvedená v poznámce nebo zdroji.

Nepiš za studenta nový výstup. Pojmenuj problém a zeptej se, jak ho chce opravit.
