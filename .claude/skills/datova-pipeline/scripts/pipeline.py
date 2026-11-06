#!/usr/bin/env python3
"""
Datová pipeline pro workshop VŠE.

Kroky (spouštějí se z kořene repozitáře):
  python .claude/skills/datova-pipeline/scripts/pipeline.py kontrola --config metriky/kpe.yaml
  python .claude/skills/datova-pipeline/scripts/pipeline.py cisteni  --config metriky/kpe.yaml [--rozhodnuti id=volba ...]
  python .claude/skills/datova-pipeline/scripts/pipeline.py metriky  --config metriky/kpe.yaml [--podle sloupec[,sloupec]] [--filtr "vyraz"]
  python .claude/skills/datova-pipeline/scripts/pipeline.py analyza  --config metriky/kpe.yaml --nazev most_gp
  python .claude/skills/datova-pipeline/scripts/pipeline.py vystup   --config metriky/kpe.yaml
  python .claude/skills/datova-pipeline/scripts/pipeline.py validace --config metriky/kpe.yaml

Všechny výstupy jdou do vystupy/<dataset>/ (nebo --vystup <slozka>).
Návratové kódy: 0 = OK, 1 = chyba/validace neprošla, 3 = čeká se na rozhodnutí studenta.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyzy  # noqa: E402

KOD_CEKA_NA_ROZHODNUTI = 3


# ----------------------------------------------------------------- pomocné
def nacti_config(cesta):
    with open(cesta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def slozka_vystupu(cfg, args):
    d = Path(args.vystup) if args.vystup else Path("vystupy") / cfg["dataset"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def nacti_raw(cfg, args):
    soubor = args.vstup or cfg["zdroj"]["soubor"]
    if str(soubor).lower().endswith(".csv"):
        return pd.read_csv(soubor), soubor
    return pd.read_excel(soubor, sheet_name=cfg["zdroj"].get("list", 0)), soubor


def nacti_stav(d):
    p = d / "stav.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def uloz_stav(d, stav):
    (d / "stav.json").write_text(json.dumps(stav, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def numericke_soucty(df, cfg):
    out = {}
    for a in cfg["agregace"].values():
        s = a["sloupec"]
        if a["funkce"] == "sum" and s in df.columns:
            out[s] = float(pd.to_numeric(df[s], errors="coerce").sum())
    return out


def tabulka(df, max_radku=40):
    with pd.option_context("display.max_rows", max_radku, "display.width", 200,
                           "display.float_format", lambda x: f"{x:,.2f}".replace(",", " ")):
        return df.to_string()


# ----------------------------------------------------------------- 1. kontrola
def krok_kontrola(cfg, args):
    df, soubor = nacti_raw(cfg, args)
    print(f"# KONTROLA – {cfg['nazev']}\nSoubor: {soubor}\nŘádků: {len(df)}, sloupců: {len(df.columns)}\n")
    chybi = [s for s in cfg["sloupce_povinne"] if s not in df.columns]
    if chybi:
        print("CHYBA – chybí povinné sloupce:", ", ".join(chybi))
        return 1
    print("Povinné sloupce: OK")
    print("\nChybějící hodnoty (jen sloupce, kde nějaké jsou):")
    na = df.isna().sum()
    print(tabulka(na[na > 0].to_frame("chybí")) if (na > 0).any() else "  žádné")
    print("\nČísla – rozsah:")
    num = df.select_dtypes("number")
    print(tabulka(num.describe().T[["min", "max"]]))
    print("\nDimenze – počet různých hodnot:")
    for s in cfg.get("dimenze", {}):
        if s in df.columns:
            print(f"  {s}: {df[s].nunique()}")
    print("\nKontrola nic nemění. Další krok: cisteni.")
    return 0


# ----------------------------------------------------------------- 2. čištění
def dopad(df, maska, cfg):
    """Co by znamenalo vyřazení řádků v masce."""
    soucty = numericke_soucty(df[maska], cfg)
    cisla = "; ".join(f"{k} = " + f"{v:,.1f}".replace(",", " ") for k, v in soucty.items())
    return f"{int(maska.sum())} řádků; {cisla}"


def krok_cisteni(cfg, args):
    d = slozka_vystupu(cfg, args)
    df, soubor = nacti_raw(cfg, args)
    rozhodnuti = dict(r.split("=", 1) for r in (args.rozhodnuti or []))
    stav = {"dataset": cfg["dataset"], "zdroj": str(soubor), "cas": datetime.now().isoformat(timespec="seconds"),
            "radku_raw": len(df), "soucty_raw": numericke_soucty(df, cfg),
            "rozhodnuti": {}, "odstraneno": []}
    log = [f"# Log čištění – {cfg['nazev']}", f"Zdroj: `{soubor}` · {stav['cas']}", f"Řádků na vstupu: {len(df)}", ""]
    chybi_rozhodnuti = []

    for krok in cfg.get("cisteni", []):
        kid, akce = krok["id"], krok["akce"]
        pred = len(df)
        maska = None

        if akce == "odstranit_prazdne":
            maska = df.isna().all(axis=1)
        elif akce == "odstranit_kde":
            maska = df.eval(krok["podminka"], engine="python").fillna(False).astype(bool)
        elif akce == "odstranit_duplicity":
            maska = df.duplicated(subset=krok["klic"], keep="first")
        elif akce in ("chybejici_hodnota", "nekonzistence"):
            if akce == "chybejici_hodnota":
                maska = df[krok["sloupec"]].isna()
            else:
                maska = df.eval(krok["podminka"], engine="python").fillna(False).astype(bool)
            if maska.sum() == 0:
                log.append(f"- **{kid}**: žádné řádky, nic se nemění.")
                continue
            volba = rozhodnuti.get(kid)
            if volba not in krok["moznosti"]:
                chybi_rozhodnuti.append((krok, dopad(df, maska, cfg)))
                maska = None
                continue
            stav["rozhodnuti"][kid] = volba
            if volba == "oznacit":
                df.loc[maska, krok["sloupec"]] = "Neuvedeno"
                log.append(f"- **{kid}**: {int(maska.sum())} řádků označeno jako „Neuvedeno“ (rozhodnutí: {volba}).")
                continue
            if volba == "prepocitat":
                p = krok["prepocet"]
                df.loc[maska, p["sloupec"]] = df.loc[maska].eval(p["vzorec"])
                log.append(f"- **{kid}**: u {int(maska.sum())} řádků přepočten `{p['sloupec']}` = `{p['vzorec']}`.")
                continue
            if volba == "ponechat":
                log.append(f"- **{kid}**: {int(maska.sum())} řádků ponecháno beze změny (rozhodnutí: ponechat).")
                continue
            # vyradit → spadne do společného odstranění níže
        elif akce == "text_na_cislo":
            df[krok["novy_sloupec"]] = pd.to_numeric(
                df[krok["sloupec"]].astype(str).str.extract(r"([-+]?\d*[.,]?\d+)")[0].str.replace(",", "."),
                errors="coerce")
            nepreved = int(df[krok["novy_sloupec"]].isna().sum() - df[krok["sloupec"]].isna().sum())
            log.append(f"- **{kid}**: vytvořen sloupec `{krok['novy_sloupec']}`; nepřevedeno: {nepreved}.")
            continue
        elif akce == "jen_nahlasit":
            m = df.eval(krok["podminka"], engine="python").fillna(False).astype(bool)
            log.append(f"- **{kid}** (jen informace, nic se nemění): {dopad(df, m, cfg)}.")
            continue
        else:
            print(f"Neznámá akce '{akce}' v kroku {kid}")
            return 1

        if maska is not None and maska.sum() > 0:
            stav["odstraneno"].append({"krok": kid, "radku": int(maska.sum()),
                                       "soucty": numericke_soucty(df[maska], cfg)})
            log.append(f"- **{kid}**: odstraněno {dopad(df, maska, cfg)}.")
            df = df[~maska]
        elif maska is not None:
            log.append(f"- **{kid}**: žádné řádky, nic se nemění.")
        assert len(df) <= pred

    if chybi_rozhodnuti:
        print("ČEKÁ SE NA ROZHODNUTÍ STUDENTA – čištění nebylo dokončeno.\n")
        for krok, dop in chybi_rozhodnuti:
            print(f"[{krok['id']}] {krok['popis'].strip()}\n  Týká se: {dop}\n  Možnosti:")
            for k, v in krok["moznosti"].items():
                print(f"    {k}: {v}")
            print()
        print("Spusť znovu s např.: --rozhodnuti " + " ".join(f"{k['id']}=<volba>" for k, _ in chybi_rozhodnuti))
        return KOD_CEKA_NA_ROZHODNUTI

    stav["radku_clean"] = len(df)
    stav["soucty_clean"] = numericke_soucty(df, cfg)
    df.to_csv(d / "data_clean.csv", index=False)
    log += ["", f"Řádků na výstupu: {len(df)}", f"Uloženo: `{d / 'data_clean.csv'}`"]
    (d / "cisteni_log.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    uloz_stav(d, stav)
    print("\n".join(log))
    return 0


# ----------------------------------------------------------------- 3. metriky
def nacti_clean(d):
    p = d / "data_clean.csv"
    if not p.exists():
        raise SystemExit("Chybí vyčištěná data – nejdřív spusť krok 'cisteni'.")
    return pd.read_csv(p)


def spocitej_metriky(df, cfg, podle=None):
    agg = {k: (a["sloupec"], a["funkce"]) for k, a in cfg["agregace"].items()}
    if podle:
        g = df.groupby(podle, dropna=False).agg(**agg)
    else:
        g = pd.DataFrame([{k: getattr(df[a["sloupec"]], a["funkce"])()
                           for k, a in cfg["agregace"].items()}], index=["CELKEM"])
    out = pd.DataFrame(index=g.index)
    for mid, m in cfg["metriky"].items():
        out[mid] = g.eval(m["vzorec"]).astype(float)
    return g, out


def krok_metriky(cfg, args):
    d = slozka_vystupu(cfg, args)
    df = nacti_clean(d)
    if args.filtr:
        df = df.query(args.filtr, engine="python")
    podle = [p.strip() for p in args.podle.split(",")] if args.podle else None
    _, out = spocitej_metriky(df, cfg, podle)
    nazev = "metriky_" + ("_".join(podle) if podle else "celkem")
    if args.filtr:
        nazev += "__" + re.sub(r"[^0-9A-Za-z]+", "_", args.filtr).strip("_")
    out.round(4).to_csv(d / f"{nazev}.csv")
    hlavicka = {k: f"{m['nazev']} [{m['jednotka']}]" for k, m in cfg["metriky"].items()}
    print(f"# METRIKY – {cfg['nazev']}" + (f" · podle {', '.join(podle)}" if podle else " · celkem")
          + (f" · filtr: {args.filtr}" if args.filtr else ""))
    print(tabulka(out.rename(columns=hlavicka).round(2).T if not podle else out.rename(columns=hlavicka).round(2)))
    print(f"\nUloženo: {d / (nazev + '.csv')}")
    return 0


# ----------------------------------------------------------------- 4. analýza
def krok_analyza(cfg, args):
    d = slozka_vystupu(cfg, args)
    if args.nazev not in cfg.get("analyzy", {}):
        print("Dostupné analýzy:", ", ".join(cfg.get("analyzy", {})) or "žádné")
        return 1
    df = nacti_clean(d)
    vysledek, komentar = getattr(analyzy, args.nazev)(df, cfg)
    vysledek.to_csv(d / f"analyza_{args.nazev}.csv", index=False)
    print(f"# ANALÝZA {args.nazev}\n{cfg['analyzy'][args.nazev].strip()}\n")
    print(tabulka(vysledek.round(2)))
    print("\n" + komentar)
    print(f"\nUloženo: {d / ('analyza_' + args.nazev + '.csv')}")
    return 0


# ----------------------------------------------------------------- 5. výstup
def krok_vystup(cfg, args):
    d = slozka_vystupu(cfg, args)
    soubor = d / f"{cfg['dataset']}_vystup.xlsx"
    definice = pd.DataFrame([{"metrika": k, "název": m["nazev"], "vzorec": m["vzorec"],
                              "jednotka": m["jednotka"], "pozor": m.get("pozor", "")}
                             for k, m in cfg["metriky"].items()])
    log = (d / "cisteni_log.md").read_text(encoding="utf-8").splitlines() if (d / "cisteni_log.md").exists() else []
    with pd.ExcelWriter(soubor, engine="openpyxl") as xw:
        for p in sorted(d.glob("metriky_*.csv")) + sorted(d.glob("analyza_*.csv")):
            jmeno = p.stem.replace("metriky_", "M_").replace("analyza_", "A_")[:31]
            pd.read_csv(p).to_excel(xw, sheet_name=jmeno, index=False)
        definice.to_excel(xw, sheet_name="Definice metrik", index=False)
        pd.DataFrame({"log čištění": log}).to_excel(xw, sheet_name="Log čištění", index=False)
        nacti_clean(d).to_excel(xw, sheet_name="Data clean", index=False)
    print(f"Uloženo: {soubor}")
    return 0


# ----------------------------------------------------------------- 6. validace
def krok_validace(cfg, args):
    d = slozka_vystupu(cfg, args)
    stav = nacti_stav(d)
    chyby, ok = [], []
    if not stav:
        print("VALIDACE NEPROŠLA: chybí stav.json – nejdřív spusť 'cisteni'.")
        return 1
    df = nacti_clean(d)

    # 1) řádky: raw − odstraněné = clean
    odstr = sum(o["radku"] for o in stav["odstraneno"])
    if stav["radku_raw"] - odstr == len(df):
        ok.append(f"Řádky sedí: {stav['radku_raw']} − {odstr} odstraněných = {len(df)}")
    else:
        chyby.append(f"Řádky nesedí: {stav['radku_raw']} − {odstr} ≠ {len(df)}")

    # 2) součty: raw − odstraněné = clean (u přepočtených sloupců jen informace)
    prepocteno = {k["prepocet"]["sloupec"] for k in cfg["cisteni"]
                  if stav["rozhodnuti"].get(k["id"]) == "prepocitat"}
    for s, v_raw in stav["soucty_raw"].items():
        ocek = v_raw - sum(o["soucty"].get(s, 0) for o in stav["odstraneno"])
        skut = float(df[s].sum())
        if s in prepocteno:
            ok.append(f"Součet {s}: změněn přepočtem o {skut - ocek:,.2f} (záměrně)")
        elif abs(ocek - skut) <= max(1e-6 * abs(ocek), 0.01):
            ok.append(f"Součet {s} sedí na raw data")
        else:
            chyby.append(f"Součet {s} nesedí: očekáváno {ocek:,.2f}, je {skut:,.2f}")

    # 3) metriky celkem v povoleném rozsahu
    _, celk = spocitej_metriky(df, cfg)
    for mid, m in cfg["metriky"].items():
        if "rozsah" in m:
            v = celk.loc["CELKEM", mid]
            lo, hi = m["rozsah"]
            (ok if lo <= v <= hi else chyby).append(f"{m['nazev']} = {v:.2f} {m['jednotka']} (rozsah {lo}–{hi})")

    # 4) kontrolní hodnoty
    plati = cfg.get("kontrolni_hodnoty_plati_pro", {})
    jine = {k: v for k, v in plati.items() if stav["rozhodnuti"].get(k) != v}
    if cfg.get("kontrolni_hodnoty") and jine:
        ok.append(f"Kontrolní hodnoty přeskočeny – platí jen pro rozhodnutí {plati}")
    else:
        for k in cfg.get("kontrolni_hodnoty", []):
            v = celk.loc["CELKEM", k["metrika"]]
            txt = f"Kontrolní hodnota {k['metrika']}: {v:.3f} vs. {k['hodnota']} (±{k['tolerance']})"
            (ok if abs(v - k["hodnota"]) <= k["tolerance"] else chyby).append(txt)

    # 5) uložené tabulky metrik: součty skupin = celek
    for p in d.glob("metriky_*.csv"):
        if "__" in p.stem or p.stem == "metriky_celkem":
            continue
        t = pd.read_csv(p)
        for mid in ("objem_t", "trzba_tis_czk", "gp_tis_czk", "gp_mil_czk"):
            if mid in t.columns:
                if abs(t[mid].sum() - celk.loc["CELKEM", mid]) > 0.01 * max(1, abs(celk.loc["CELKEM", mid])) / 100:
                    chyby.append(f"{p.name}: součet {mid} za skupiny nesedí na celek")
                else:
                    ok.append(f"{p.name}: součet {mid} za skupiny = celek")

    for t in ok:
        print("  ✓", t)
    for t in chyby:
        print("  ✗", t)
    print("\nVALIDACE PROŠLA" if not chyby else f"\nVALIDACE NEPROŠLA ({len(chyby)} chyb) – výstup nepředávat.")
    return 0 if not chyby else 1


# ----------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="Datová pipeline VŠE")
    ap.add_argument("krok", choices=["kontrola", "cisteni", "metriky", "analyza", "vystup", "validace"])
    ap.add_argument("--config", required=True, help="např. metriky/kpe.yaml")
    ap.add_argument("--vstup", help="jiný vstupní soubor než v configu (xlsx/csv)")
    ap.add_argument("--vystup", help="složka pro výstupy (výchozí vystupy/<dataset>)")
    ap.add_argument("--rozhodnuti", nargs="*", help="id=volba pro kroky čištění, které vyžadují rozhodnutí")
    ap.add_argument("--podle", help="dimenze pro seskupení, čárkou oddělené")
    ap.add_argument("--filtr", help="pandas výraz, např. \"location_type == 'Office'\"")
    ap.add_argument("--nazev", help="název analýzy")
    args = ap.parse_args()
    cfg = nacti_config(args.config)
    krok = globals()[f"krok_{args.krok}"]
    sys.exit(krok(cfg, args))


if __name__ == "__main__":
    main()
