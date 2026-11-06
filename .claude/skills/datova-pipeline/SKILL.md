---
name: datova-pipeline
description: Postup analýzy dat v kurzu VŠE – kontrola, čištění, metriky, analýzy, výstup a validace nad daty KPE nebo kávomatů. Použij vždy, když student nahraje data, chce cokoliv spočítat, vyčistit, porovnat, udělat dashboard nebo podklad pro prezentaci.
---

# Datová pipeline

Čísla se počítají **jen skripty** z této složky. Ty (Claude) skripty spouštíš,
vysvětluješ výsledky a ptáš se studenta na rozhodnutí. Sám nic nedopočítáváš.

Skript: `python .claude/skills/datova-pipeline/scripts/pipeline.py <krok> --config metriky/<dataset>.yaml`
(spouštěj z kořene repozitáře). Datasety: `metriky/kpe.yaml`, `metriky/kavomaty.yaml`.
Vlastní soubor studenta: přidej `--vstup <cesta>`.

## Kroky – vždy v tomto pořadí

1. **kontrola** – ukaž studentovi, co v datech je (řádky, chybějící hodnoty, rozsahy).
   Nic se nemění. Zeptej se: *Co chceš z dat zjistit a pro koho výstup je?*
   Bez odpovědi nepokračuj – hypotéza a adresát určují, co budeme počítat.

2. **cisteni** – spusť bez rozhodnutí. Když skript skončí kódem 3, čeká na studenta:
   - Přepiš studentovi otázku vlastními slovy včetně dopadu (kolik řádků, kolik tun / Kč).
   - Nedoporučuj automaticky. Nech ho vybrat a **zdůvodnit** jednou větou.
   - Pak spusť znovu s `--rozhodnuti id=volba` a zdůvodnění zapiš do jeho poznámek.

3. **metriky** – `--podle <dimenze>` pro členění, `--filtr "<výraz>"` pro výběr.
   Dostupné dimenze a metriky jsou v YAML configu. Metriku, která v configu není,
   **nevymýšlej** – navrhni studentovi doplnění do YAML (název, vzorec, jednotka) a počkej na souhlas.

4. **analyza** – hotové postupy (`--nazev most_gp` pro KPE, `--nazev ztraty_vypadky` pro kávomaty).
   Vždy studentovi přečti předpoklady z komentáře – je to odhad, ne fakt.

5. **vystup** – Excel `vystupy/<dataset>/<dataset>_vystup.xlsx` se všemi tabulkami,
   definicemi metrik, logem čištění a vyčištěnými daty. Ten student otevře v Excelu / Power BI.

6. **validace** – povinně před předáním čehokoliv. Když neprojde, výstup nepředávej
   a vysvětli, co nesedí.

## Pravidla

- Každé číslo v odpovědi musí pocházet z výstupu skriptu. U čísla uveď, odkud je (krok, soubor).
- Nikdy neupravuj `data_clean.csv` ručně ani vlastním kódem – jen přes krok `cisteni`.
- Podíly a průměry vždy ze součtů (viz pole `pozor` v YAML).
- Když skript skončí chybou, ukaž chybu a navrhni opravu; neobcházej ho vlastním výpočtem.

## Rozšíření

- Nová metrika → přidat do sekce `metriky` v YAML (vzorec nad názvy z `agregace`).
- Nový krok čištění → sekce `cisteni` (akce: `odstranit_prazdne`, `odstranit_kde`,
  `odstranit_duplicity`, `chybejici_hodnota`, `nekonzistence`, `text_na_cislo`, `jen_nahlasit`).
- Nová analýza → funkce v `scripts/analyzy.py` + popis v sekci `analyzy` v YAML.
