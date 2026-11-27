"""
Шаг 17. Собирает model/artifact.json — ЕДИНСТВЕННЫЙ файл, который читает сайт.

Правило брифа (раздел 4): estimation отделено от serving.
Код оценки (src/) пишет артефакт; сайт (site/) только читает его и ничего не считает,
кроме интерактивного сценария (та же формула AR(1) с коэффициентами из артефакта).

Источники внутри артефакта (каждое число трассируется):
  data/processed/monthly.csv              -> ряд, сезонный профиль
  outputs/eda_summary.csv                 -> рост товаров за январь–апрель
  outputs/jan_apr_by_year.csv             -> сезоны по годам
  outputs/model_backtest_monthly_summary.csv, outputs/backtest_monthly_summary.csv -> качество
  outputs/model_backtest_decision_*.csv   -> решения в прошлом
  prereg/reality_check_forecast.csv       -> замороженный прогноз
  оценка ar1_seasonal на всей выборке     -> коэффициенты для сценария

Запуск: python src/export_artifact.py
AI-assisted: see AI_USE entry A14; reviewed and tested by Майра, Айтуар.
"""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import models
from benchmarks import cumulative
from models import add_driver_growth, ar1_seasonal, fit_summary

DATA = Path("data/processed/monthly.csv")
OUTD = Path("outputs")
OUT = Path("model/artifact.json")

THRESHOLD = 4.88      # 75-й процентиль сезонов январь–апрель (пререгистрация §5)
MEDIAN = 3.96
ITEMS = {"cabbage": "Капуста", "potato": "Картофель", "onion": "Лук", "carrot": "Морковь",
         "sugar": "Сахар", "eggs": "Яйца", "flour": "Мука", "beef": "Говядина",
         "chicken": "Окорочка", "milk": "Молочные", "oil": "Подсолн. масло"}


def r(x, n=2):
    return None if pd.isna(x) else round(float(x), n)


def main():
    df = add_driver_growth(pd.read_csv(DATA, index_col="month", parse_dates=True))
    models.TARGET = "food_almaty"
    origin = df.index.max()

    # 1. Сезоны январь–апрель по годам
    ja = pd.read_csv(OUTD / "jan_apr_by_year.csv", index_col=0)["janapr_growth_pct"]
    seasons = [{"year": int(y), "growth": r(v)} for y, v in ja.items()]

    # 2. Сезонный профиль: медиана роста по месяцам без шоковых лет (из шага 7, explore.py)
    eda = pd.read_csv(OUTD / "eda_summary.csv", index_col=0)["value"]
    profile = [{"month": k, "median": r(eda[f"seasonal_median_month_{k:02d}"])} for k in range(1, 13)]

    # 3. Товары: медианный накопленный рост январь–апрель без шоковых лет (из шага 7, explore.py)
    items = [{"item": label, "janapr_median": r(eda[f"janapr_median_{key}"])} for key, label in ITEMS.items()]
    items.sort(key=lambda d: -d["janapr_median"])

    # 4. Прогноз на 6 месяцев и коэффициенты для сценария
    fc = ar1_seasonal(df, origin, 6)
    fit = fit_summary(df)["ar1_seasonal"]
    m = [r(fit.params[f"m_{k}"], 6) for k in range(1, 13)]
    phi = r(fit.params["y_lag1"], 6)

    # 5. Качество (горизонт 1 месяц)
    a =pd.read_csv(OUTD / "model_backtest_monthly_summary.csv")
    b = pd.read_csv(OUTD / "backtest_monthly_summary.csv")
    allm = pd.concat([a, b[~b.model.isin(a.model)]])
    h1 = allm[allm.h == 1]
    quality = [{"model": row.model, "mae": r(row.MAE, 3), "asym_loss": r(row.asym_loss, 3),
                "coverage80": r(row.coverage80, 3)} for row in h1.itertuples()]

    # 6. Решения в прошлом (ar1_seasonal, обновление в январе)
    dec = pd.read_csv(OUTD / "model_backtest_decision_jan.csv")
    dec = dec[dec.model == "ar1_seasonal"]
    record = [{"season": int(d.season), "forecast": r(d.forecast), "actual": r(d.actual),
               "threshold": r(d.threshold), "signal": bool(d.signal), "bad": bool(d.bad_season)}
              for d in dec.itertuples()]

    # 7. Пререгистрация
    rc = pd.read_csv("prereg/reality_check_forecast.csv")
    prereg = [{k: (r(v) if isinstance(v, float) else v) for k, v in row.items()} for row in rc.to_dict("records")]

    art = {
        "meta": {"built": date.today().isoformat(), "data_through": origin.strftime("%Y-%m"),
                 "target": "Рост цен на продовольственные товары, г. Алматы, % к предыдущему месяцу",
                 "source": "БНС АСПиР РК, «Талдау»; FAO; НБК"},
        "decision": {"threshold": THRESHOLD, "median": MEDIAN, "loss_under": 3, "loss_over": 1,
                     "janapr_forecast": r(cumulative(fc.loc["2027-01":"2027-04"])),
                     "signal": bool(cumulative(fc.loc["2027-01":"2027-04"]) > THRESHOLD)},
        "series": [{"month": i.strftime("%Y-%m"), "growth": r(v)} for i, v in df["food_almaty"].items()],
        "seasons": seasons, "profile": profile, "items": items,
        "forecast": [{"month": i.strftime("%Y-%m"), "point": r(v, 4)} for i, v in fc.items()],
        "model": {"name": "ar1_seasonal", "m": m, "phi": phi,
                  "last_growth": r(df["food_almaty"].iloc[-1]), "last_month": origin.month},
        "quality_h1": quality, "decision_record": record, "prereg": prereg,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    # Копия для сайта: работает и при открытии index.html двойным кликом (file://)
    Path("site/artifact.js").write_text(
        "window.ARTIFACT = " + json.dumps(art, ensure_ascii=False) + ";\n", encoding="utf-8")

    # Проверки: артефакт согласован с пререгистрацией
    frozen = rc[(rc.region == "almaty") & (rc.model == "ar1_seasonal")].iloc[0]
    assert abs(fc.iloc[0] - frozen.nov2026_point) < 0.01 or origin.strftime("%Y-%m") != "2026-10", \
        "Прогноз на ноябрь расходится с пререгистрацией"
    print(f"OK: {OUT} ({OUT.stat().st_size // 1024} КБ), данные по {art['meta']['data_through']}, "
          f"январь–апрель 2027 = {art['decision']['janapr_forecast']}%, сигнал = {art['decision']['signal']}")


if __name__ == "__main__":
    main()
