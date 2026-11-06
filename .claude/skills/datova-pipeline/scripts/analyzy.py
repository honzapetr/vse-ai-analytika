"""
Hotové analytické postupy. Každá funkce dostane vyčištěná data a config
a vrací (tabulka výsledků, komentář s předpoklady).
Název funkce = klíč v sekci `analyzy` v metriky/<dataset>.yaml.
"""
import pandas as pd


def most_gp(df, cfg):
    """Most hrubého zisku plán → skutečnost (mil. CZK).

    efekt objemu = (objem − plán objemu) × plánovaný GP/kg celkem
    efekt mixu   = Σ_kanál (Δ objem kanálu × plán GP/kg kanálu) − efekt objemu
    efekt marže  = zbytek do skutečného hrubého zisku
    """
    k = df.groupby("SalesChannelISOP").agg(
        objem=("Volume, t", "sum"), plan=("Plan, t", "sum"),
        gp=("GP, CZK", "sum"), plan_gp=("Plan GP, CZK", "sum"))
    V, P, G, PG = k.objem.sum(), k.plan.sum(), k.gp.sum(), k.plan_gp.sum()
    sazba_celkem = PG / P                      # CZK na tunu
    ef_objem = (V - P) * sazba_celkem
    ef_kanaly = ((k.objem - k.plan) * (k.plan_gp / k.plan)).sum()
    ef_mix = ef_kanaly - ef_objem
    ef_marze = (G - PG) - ef_kanaly
    radky = [
        ("Plán hrubého zisku", PG),
        ("Efekt objemu", ef_objem),
        ("Efekt kanálového mixu", ef_mix),
        ("Efekt marže", ef_marze),
        ("Skutečný hrubý zisk", G),
    ]
    out = pd.DataFrame(radky, columns=["polozka", "mil_czk"])
    out["mil_czk"] = out["mil_czk"] / 1e6
    kontrola = PG + ef_objem + ef_mix + ef_marze - G
    komentar = (f"Kontrola mostu: plán + efekty − skutečnost = {kontrola:.6f} CZK (musí být 0).\n"
                "Předpoklad: efekt objemu oceněn plánovaným GP/kg celé firmy, mix na úrovni kanálů.")
    return out, komentar


def ztraty_vypadky(df, cfg):
    """Odhad ušlé tržby a zisku kvůli poruchám a chybějícím surovinám.

    Běžný den = den stejného automatu ve stejném typu dne (pracovní/víkend)
    bez chybějící suroviny a s výpadkem pod 15 minut. Ušlá tržba dne = max(0, běžná − skutečná).
    Den s chybějící surovinou se připíše surovinám, jinak poruše.
    """
    df = df.copy()
    bezny = (df.stockout_occurred == 0) & (df.downtime_minutes < 15)
    zaklad = (df[bezny].groupby(["machine_id", "is_weekend"])
              .agg(bezna_trzba=("revenue_czk", "mean"), bezny_gp=("gross_profit_czk", "mean")))
    df = df.join(zaklad, on=["machine_id", "is_weekend"])
    zasazeno = ~bezny
    df["usla_trzba"] = ((df.bezna_trzba - df.revenue_czk).clip(lower=0)).where(zasazeno, 0)
    df["usly_gp"] = ((df.bezny_gp - df.gross_profit_czk).clip(lower=0)).where(zasazeno, 0)
    df["pricina"] = "bez ztráty"
    df.loc[zasazeno & (df.stockout_occurred == 1), "pricina"] = "chybějící surovina"
    df.loc[zasazeno & (df.stockout_occurred == 0), "pricina"] = "porucha (≥ 15 min)"

    out = (df[df.pricina != "bez ztráty"]
           .groupby(["pricina", "location_type"])
           .agg(dny=("date", "count"), usla_trzba_czk=("usla_trzba", "sum"), usly_gp_czk=("usly_gp", "sum"))
           .reset_index().sort_values("usly_gp_czk", ascending=False))
    celkem = out[["dny", "usla_trzba_czk", "usly_gp_czk"]].sum()
    out = pd.concat([out, pd.DataFrame([{"pricina": "CELKEM", "location_type": "", **celkem.to_dict()}])],
                    ignore_index=True)
    podil = celkem.usla_trzba_czk / df.revenue_czk.sum() * 100
    def czk(x):
        return f"{x:,.0f}".replace(",", " ")
    komentar = (f"Odhad ušlé tržby celkem: {czk(celkem.usla_trzba_czk)} CZK "
                f"({podil:.1f} % skutečné tržby), ušlý hrubý zisk {czk(celkem.usly_gp_czk)} CZK.\n"
                "Je to ODHAD: předpokládá, že bez výpadku by automat prodal jako v běžný den. "
                "Práh 15 minut je volba analytika – zkus jiný a porovnej citlivost.")
    return out, komentar
