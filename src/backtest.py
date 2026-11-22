"""
Шаг 9. Rolling-origin бэктест бенчмарков.

Идея: «притворяемся, что живём в прошлом». Для каждой даты прогноза (origin)
берём только данные до неё, делаем прогноз, сравниваем с фактом,
сдвигаем origin на месяц вперёд и повторяем. Получаем много честных ошибок.

Две проверки:
  A. Помесячная: прогноз на 1–6 месяцев вперёд от каждого месяца с 2014 года.
     Метрики: MAE, RMSE, асимметричная потеря (3:1), покрытие 80%-интервала.
  B. Под решение: каждый октябрь прогнозируем накопленный рост за январь–апрель
     следующего года и проверяем, верно ли было бы решение стабфонда
     (порог = 75-й процентиль прошлых сезонов, посчитанный ТОЛЬКО по прошлому).

Плюс тест на утечку: портим будущие данные и проверяем, что прогноз не изменился.

Данные пересмотренные (старых версий релизов нет), поэтому это revised-data backtest.

Запуск: python src/backtest.py
AI-assisted: see AI_USE entry A07; reviewed and tested by [имена].
"""

from pathlib import Path

import numpy as np
import pandas as pd

from benchmarks import BENCHMARKS, cumulative

DATA = Path("data/processed/monthly.csv")
OUT = Path("outputs")
TARGET = "food_almaty"
FIRST_ORIGIN = pd.Timestamp("2014-01-01")  # нужно ≥3 лет истории для seasonal_mean3
H = 6                                      # горизонт: до 6 месяцев вперёд
UNDER, OVER = 3.0, 1.0                     # недооценка в 3 раза дороже переоценки
MIN_PAST_ERRORS = 24                       # сколько прошлых ошибок нужно для интервала


def asym_loss(actual, forecast):
    """Асимметричная потеря: 3·|e| при недооценке, 1·|e| при переоценке."""
    e = actual - forecast
    return np.where(e > 0, UNDER * e, OVER * (-e))


def leakage_test(y):
    """Портим всё после origin: прогноз бенчмарка не должен измениться."""
    origin = pd.Timestamp("2018-06-01")
    spoiled = y.copy()
    spoiled[spoiled.index > origin] = 999.0
    for name, f in BENCHMARKS.items():
        clean = f(y, origin, H)
        dirty = f(spoiled, origin, H)
        assert np.allclose(clean.values, dirty.values), f"УТЕЧКА в {name}!"
    print("Тест на утечку пройден: прогнозы не видят будущего.")


def monthly_backtest(y):
    """A. Прогнозы от каждого origin на 1..H месяцев вперёд."""
    rows = []
    origins = y.index[(y.index >= FIRST_ORIGIN) & (y.index <= y.index.max() - pd.DateOffset(months=1))]
    for origin in origins:
        for name, f in BENCHMARKS.items():
            fc = f(y, origin, H)
            for step, (month, value) in enumerate(fc.items(), start=1):
                if month in y.index:  # факт уже известен
                    rows.append({"origin": origin, "model": name, "h": step,
                                 "month": month, "forecast": value, "actual": y[month]})
    bt = pd.DataFrame(rows)
    bt["error"] = bt["actual"] - bt["forecast"]

    # 80%-интервал из ПРОШЛЫХ ошибок той же модели и горизонта (без утечки):
    # берём ошибки, факт по которым был известен к моменту origin.
    lo, hi = [], []
    for _, r in bt.iterrows():
        past = bt[(bt["model"] == r["model"]) & (bt["h"] == r["h"]) & (bt["month"] <= r["origin"])]["error"]
        if len(past) >= MIN_PAST_ERRORS:
            lo.append(r["forecast"] + past.quantile(0.10))
            hi.append(r["forecast"] + past.quantile(0.90))
        else:
            lo.append(np.nan)
            hi.append(np.nan)
    bt["lo80"], bt["hi80"] = lo, hi
    bt["covered"] = np.where(bt["lo80"].notna(),
                             (bt["actual"] >= bt["lo80"]) & (bt["actual"] <= bt["hi80"]), np.nan)
    bt["loss"] = asym_loss(bt["actual"], bt["forecast"])
    return bt


def summarize_monthly(bt):
    g = bt.groupby(["model", "h"])
    table = pd.DataFrame({
        "n": g.size(),
        "MAE": g["error"].apply(lambda e: e.abs().mean()),
        "RMSE": g["error"].apply(lambda e: np.sqrt((e ** 2).mean())),
        "asym_loss": g["loss"].mean(),
        "coverage80": g["covered"].mean(),
    })
    return table.round(3)


def decision_backtest(y):
    """B. Каждый октябрь: прогноз январь–апрель следующего года и верность решения."""
    rows = []
    for year in range(FIRST_ORIGIN.year, y.index.max().year):
        origin = pd.Timestamp(f"{year}-10-01")
        target_months = pd.date_range(f"{year + 1}-01-01", periods=4, freq="MS")
        if not all(m in y.index for m in target_months):
            continue
        actual = cumulative(y[target_months])
        # Порог — только по сезонам, которые были известны к origin
        past = [cumulative(y[f"{yy}-01":f"{yy}-04"]) for yy in range(y.index.min().year, year + 1)]
        threshold = np.quantile(past, 0.75)
        for name, f in BENCHMARKS.items():
            fc = f(y, origin, 7)  # ноябрь..май; берём январь–апрель
            forecast = cumulative(fc[target_months])
            rows.append({"season": year + 1, "model": name, "forecast": forecast,
                         "actual": actual, "threshold": threshold,
                         "signal": forecast > threshold, "bad_season": actual > threshold})
    d = pd.DataFrame(rows)
    d["error"] = d["actual"] - d["forecast"]
    d["loss"] = asym_loss(d["actual"], d["forecast"])
    d["decision_right"] = d["signal"] == d["bad_season"]
    return d


def main():
    OUT.mkdir(exist_ok=True)
    y = pd.read_csv(DATA, index_col="month", parse_dates=True)[TARGET]

    leakage_test(y)

    bt = monthly_backtest(y)
    summary = summarize_monthly(bt)
    bt.to_csv(OUT / "backtest_monthly_detail.csv", index=False)
    summary.to_csv(OUT / "backtest_monthly_summary.csv")

    dec = decision_backtest(y)
    dec.round(3).to_csv(OUT / "backtest_decision.csv", index=False)
    dec_summary = dec.groupby("model").agg(
        seasons=("season", "size"),
        MAE=("error", lambda e: e.abs().mean()),
        RMSE=("error", lambda e: np.sqrt((e ** 2).mean())),
        asym_loss=("loss", "mean"),
        decision_right=("decision_right", "mean"),
        bad_seasons_caught=("signal", lambda s: s[dec.loc[s.index, "bad_season"]].sum()),
        bad_seasons_total=("bad_season", "sum"),
    ).round(3)
    dec_summary.to_csv(OUT / "backtest_decision_summary.csv")

    print("\nA. Помесячный бэктест, горизонт 1 месяц:")
    print(summary.xs(1, level="h"))
    print("\nA. Горизонт 6 месяцев:")
    print(summary.xs(6, level="h"))
    print("\nB. Под решение (январь–апрель, прогноз из октября):")
    print(dec_summary)


if __name__ == "__main__":
    main()
