"""Germany's shift to battery-electric cars, and where BMW Group stands. All figures come from the SQL below over
data/clean/*.csv (KBA FZ 8.2 and FZ 8.6). Output: outputs/results.json and outputs/*.csv.

Definitions
  BEV share      battery-electric registrations / all passenger-car registrations
  BEV index      a brand's share of the BEV market / its share of the total market (1.0 = average; below 1 = behind)
  YTD            January to the latest month available, compared with the same months a year earlier
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
GROUPS = {"BMW Group": ["BMW", "MINI", "ROLLS ROYCE"], "Mercedes-Benz": ["MERCEDES", "SMART"],
          "Volkswagen Group": ["VW", "AUDI", "SKODA", "SEAT", "CUPRA", "PORSCHE"], "Tesla": ["TESLA"],
          "BYD": ["BYD"], "Hyundai-Kia": ["HYUNDAI", "KIA"], "Stellantis": ["OPEL", "PEUGEOT", "CITROEN", "FIAT", "JEEP", "DS", "ALFA ROMEO", "LANCIA"],
          "Volvo-Polestar": ["VOLVO", "POLESTAR"], "Renault": ["RENAULT", "DACIA", "ALPINE"], "Ford": ["FORD"],
          "Toyota-Lexus": ["TOYOTA", "LEXUS"], "MG (SAIC)": ["MG ROEWE"]}  # KBA lists Cupra under SEAT


def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute(f"CREATE TABLE b AS SELECT * FROM read_csv_auto('{ROOT}/data/clean/brand_month.csv')")
    c.execute(f"CREATE TABLE s AS SELECT * FROM read_csv_auto('{ROOT}/data/clean/state_month.csv')")
    rows = [(brand, group) for group, brands in GROUPS.items() for brand in brands]
    c.execute("CREATE TABLE grp(brand VARCHAR, grp VARCHAR)")
    c.executemany("INSERT INTO grp VALUES (?, ?)", rows)
    return c


def main() -> None:
    c = con()
    last = c.execute("SELECT max(month) FROM b").fetchone()[0]
    yr, mo = int(last[:4]), int(last[5:7])
    ytd = lambda y: f"month BETWEEN '{y}-01' AND '{y}-{mo:02d}'"  # noqa: E731

    market = c.execute("""SELECT month, total, bev, phev, round(100.0*bev/total,1) AS bev_share, round(100.0*phev/total,1) AS phev_share
                          FROM b WHERE is_total ORDER BY month""").df()
    market.to_csv(ROOT / "outputs" / "market_month.csv", index=False)

    group_sql = """
      WITH g AS (SELECT coalesce(grp.grp, 'Other') AS grp, sum(b.total) total, sum(b.bev) bev, sum(b.phev) phev
                 FROM b LEFT JOIN grp ON upper(b.name)=grp.brand WHERE NOT b.is_total AND {w} GROUP BY 1),
           t AS (SELECT sum(total) total, sum(bev) bev FROM g)
      SELECT g.grp, g.total, g.bev, g.phev,
             round(100.0*g.bev/g.total,1) AS bev_share_own,
             round(100.0*g.total/t.total,2) AS share_total_market,
             round(100.0*g.bev/t.bev,2) AS share_bev_market,
             round((1.0*g.bev/t.bev)/(1.0*g.total/t.total),2) AS bev_index
      FROM g, t ORDER BY g.total DESC"""
    now = c.execute(group_sql.format(w=ytd(yr))).df()
    prev = c.execute(group_sql.format(w=ytd(yr - 1))).df()
    now.to_csv(ROOT / "outputs" / f"groups_ytd_{yr}.csv", index=False)
    prev.to_csv(ROOT / "outputs" / f"groups_ytd_{yr-1}.csv", index=False)
    swing = now.merge(prev, on="grp", suffixes=("", "_prev"))
    swing["bev_market_share_change_pp"] = (swing.share_bev_market - swing.share_bev_market_prev).round(2)
    swing["bev_growth_pct"] = (100 * (swing.bev / swing.bev_prev - 1)).round(1)

    brands_sql = f"""SELECT name, sum(total) total, sum(bev) bev, round(100.0*sum(bev)/sum(total),1) bev_share_own
                     FROM b WHERE NOT is_total AND {ytd(yr)} GROUP BY 1 HAVING sum(total) >= 5000 ORDER BY bev_share_own DESC"""
    brands = c.execute(brands_sql).df()

    bmw_month = c.execute("""SELECT b.month, round(100.0*sum(b.bev)/sum(b.total),1) AS bmw_group_bev_share, any_value(m.bev_share) AS market_bev_share
                             FROM b JOIN grp ON upper(b.name)=grp.brand AND grp.grp='BMW Group'
                             JOIN (SELECT month, round(100.0*bev/total,1) bev_share FROM b WHERE is_total) m USING(month)
                             GROUP BY 1 ORDER BY 1""").df()
    bmw_month.to_csv(ROOT / "outputs" / "bmw_group_month.csv", index=False)

    states = c.execute(f"""SELECT name, {yr} AS year, round(100.0*sum(bev)/sum(total),1) bev_share FROM s WHERE {ytd(yr)} GROUP BY 1
                           UNION ALL SELECT name, {yr-1}, round(100.0*sum(bev)/sum(total),1) FROM s WHERE {ytd(yr-1)} GROUP BY 1""").df()

    res = {
        "source": "Kraftfahrt-Bundesamt (KBA), FZ 8, monthly new passenger-car registrations; Datenlizenz Deutschland – Namensnennung – Version 2.0",
        "months": [market.month.min(), market.month.max()], "ytd_window": f"January–{last[5:]} {yr} vs {yr-1}",
        "market_ytd": {str(y): c.execute(f"SELECT sum(total) total, sum(bev) bev, round(100.0*sum(bev)/sum(total),1) bev_share FROM b WHERE is_total AND {ytd(y)}").df().to_dict("records")[0] for y in (yr - 1, yr)},
        "groups_ytd": now.to_dict("records"), "groups_prev_ytd": prev.to_dict("records"),
        "swing": swing[["grp", "share_bev_market_prev", "share_bev_market", "bev_market_share_change_pp", "bev_growth_pct"]].sort_values("bev_market_share_change_pp").to_dict("records"),
        "brands_bev_share_ytd": brands.to_dict("records"),
        "bavaria_vs_germany": states[states.name.isin(["Bayern", "Deutschland"])].to_dict("records"),
    }
    (ROOT / "outputs" / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("months", "market_ytd")}, default=str))
    print(now[["grp", "share_total_market", "share_bev_market", "bev_index", "bev_share_own"]].to_string(index=False))


if __name__ == "__main__":
    main()
