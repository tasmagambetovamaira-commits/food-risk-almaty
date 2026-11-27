"""
Шаг 11 (продолжение). Бэктест моделей-кандидатов против бенчмарков — по тем же правилам,
что и шаг 9: rolling origin, только данные до origin, интервалы из прошлых ошибок,
асимметричная потеря 3:1, тест на утечку.

Две проверки под решение:
  B1. Прогноз из ОКТЯБРЯ на январь–апрель следующего года (как стабфонд планирует закуп).
  B2. Обновление в ЯНВАРЕ: январь уже известен, прогнозируем февраль–апрель и считаем
      накопленный рост за январь–апрель (можно ли поймать плохой сезон раньше, чем он пройдёт).

Запуск: python src/backtest_models.py   (около 1–2 минут: SARIMA переоценивается на каждом origin)
AI-assisted: see AI_USE entry A10; reviewed and tested by [имена].
"""

from pathlib import Path

import numpy as np
import pandas as pd

from backtest import asym_loss, FIRST_ORIGIN, MIN_PAST_ERRORS
from benchmarks import BENCHMARKS, cumulative
from models import MODELS, TARGET, add_driver_growth

DATA = Path("data/processed/monthly.csv")
OUT = Path("outputs")
H = 6

# Бенчмарки работают с рядом, модели — с таблицей; приводим к одному виду f(df, origin, h)
ALL = {name: (lambda f: (lambda df, o, h: f(df[TARGET], o, h)))(f) for name, f in BENCHMARKS.items()}
ALL.update(MODELS)


def leakage_test(df):
    origin = pd.Timestamp("2018-06-01")
    spoiled = df.copy()
    spoiled.loc[spoiled.index > origin, :] = 999.0
    for name, f in MODELS.items():
        assert np.allclose(f(df, origin, H).values, f(spoiled, origin, H).values), f"УТЕЧКА в {name}!"
    print("Тест на утечку пройден для всех моделей.")


def monthly_backtest(df):
    y = df[TARGET]
    rows = []
    origins = y.index[(y.index >= FIRST_ORIGIN) & (y.index < y.index.max())]
    for origin in origins:
        for name, f in ALL.items():
            fc = f(df, origin, H)
            for step, (month, value) in enumerate(fc.items(), start=1):
                if month in y.index:
                    rows.append({"origin": origin, "model": name, "h": step, "month": month,
                                 "forecast": value, "actual": y[month]})
    bt = pd.DataFrame(rows)
    bt["error"] = bt["actual"] - bt["forecast"]
    lo, hi = [], []
    for _, r in bt.iterrows():
        past = bt[(bt["model"] == r["model"]) & (bt["h"] == r["h"]) & (bt["month"] <= r["origin"])]["error"]
        ok = len(past) >= MIN_PAST_ERRORS
        lo.append(r["forecast"] + past.quantile(0.10) if ok else np.nan)
        hi.append(r["forecast"] + past.quantile(0.90) if ok else np.nan)
    bt["lo80"], bt["hi80"] = lo, hi
    bt["covered"] = np.where(bt["lo80"].notna(), (bt["actual"] >= bt["lo80"]) & (bt["actual"] <= bt["hi80"]), np.nan)
    bt["loss"] = asym_loss(bt["actual"], bt["forecast"])
    return bt


def decision_backtest(df, origin_month):
    """origin_month=10: прогноз из октября; origin_month=1: обновление в январе."""
    y = df[TARGET]
    rows = []
    for season in range(FIRST_ORIGIN.year + 1, y.index.max().year + 1):
        months = pd.date_range(f"{season}-01-01", periods=4, freq="MS")
        if not all(m in y.index for m in months):
            continue
        origin = pd.Timestamp(f"{season - 1}-10-01") if origin_month == 10 else pd.Timestamp(f"{season}-01-01")
        actual = cumulative(y[months])
        past = [cumulative(y[f"{yy}-01":f"{yy}-04"]) for yy in range(y.index.min().year, season)]
        threshold = np.quantile(past, 0.75)
        for name, f in ALL.items():
            fc = f(df, origin, 7)
            known = y[months[months <= origin]]          # уже известные месяцы сезона
            future = fc[months[months > origin]]
            forecast = cumulative(pd.concat([known, future]))
            rows.append({"season": season, "model": name, "forecast": forecast, "actual": actual,
                         "threshold": threshold, "signal": forecast > threshold,
                         "bad_season": actual > threshold})
    d = pd.DataFrame(rows)
    d["error"] = d["actual"] - d["forecast"]
    d["loss"] = asym_loss(d["actual"], d["forecast"])
    d["decision_right"] = d["signal"] == d["bad_season"]
    return d


def summarize_decision(d):
    return d.groupby("model").apply(lambda g: pd.Series({
        "MAE": g["error"].abs().mean(),
        "asym_loss": g["loss"].mean(),
        "caught": int((g["signal"] & g["bad_season"]).sum()),
        "bad_total": int(g["bad_season"].sum()),
        "false_alarms": int((g["signal"] & ~g["bad_season"]).sum()),
    }), include_groups=False).round(3)


def main():
    OUT.mkdir(exist_ok=True)
    df = add_driver_growth(pd.read_csv(DATA, index_col="month", parse_dates=True))
    leakage_test(df)

    bt = monthly_backtest(df)
    bt.to_csv(OUT / "model_backtest_monthly_detail.csv", index=False)
    g = bt.groupby(["model", "h"])
    summary = pd.DataFrame({
        "n": g.size(),
        "MAE": g["error"].apply(lambda e: e.abs().mean()),
        "RMSE": g["error"].apply(lambda e: np.sqrt((e ** 2).mean())),
        "asym_loss": g["loss"].mean(),
        "coverage80": g["covered"].mean(),
    }).round(3)
    summary.to_csv(OUT / "model_backtest_monthly_summary.csv")

    oct_ = decision_backtest(df, 10)
    jan_ = decision_backtest(df, 1)
    oct_.round(3).to_csv(OUT / "model_backtest_decision_oct.csv", index=False)
    jan_.round(3).to_csv(OUT / "model_backtest_decision_jan.csv", index=False)

    pd.set_option("display.width", 200)
    print("\nA. Помесячно, горизонт 1 месяц:")
    print(summary.xs(1, level="h").sort_values("MAE").to_string())
    print("\nA. Горизонт 3 месяца:")
    print(summary.xs(3, level="h").sort_values("MAE").to_string())
    print("\nB1. Сезон январь–апрель, прогноз из октября:")
    print(summarize_decision(oct_).sort_values("asym_loss").to_string())
    print("\nB2. Сезон январь–апрель, обновление в январе (январь уже известен):")
    print(summarize_decision(jan_).sort_values("asym_loss").to_string())


if __name__ == "__main__":
    main()
