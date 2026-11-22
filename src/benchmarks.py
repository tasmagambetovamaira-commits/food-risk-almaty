"""
Шаг 8. Бенчмарки: простые прогнозы, которые модель потом должна обыграть.

Три бенчмарка роста цен на продукты за месяц (Алматы):
  1. seasonal_naive  — «как в этом же месяце прошлого года».
                       Это и есть то, как стабфонд планирует сейчас («по прошлому году»).
  2. seasonal_mean3  — среднее этого же месяца за последние 3 года.
                       Сглаживает случайность одного года.
  3. climatology     — медиана этого же месяца за всю доступную историю.
                       «Обычный год» в чистом виде.

Каждая функция получает историю ТОЛЬКО до даты прогноза (origin)
и не видит ничего после неё — это защита от утечки будущего.

Запуск: python src/benchmarks.py
(печатает прогнозы на ноябрь 2026 – апрель 2027 и накопленный рост за январь–апрель 2027)

AI-assisted: see AI_USE entry A06; reviewed and tested by [имена].
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("data/processed/monthly.csv")
OUT = Path("outputs")
TARGET = "food_almaty"


def _future_months(origin, h):
    """Месяцы, на которые делаем прогноз: следующие h месяцев после origin."""
    return pd.date_range(origin + pd.offsets.MonthBegin(1), periods=h, freq="MS")


def seasonal_naive(history, origin, h):
    """Прогноз = значение того же месяца год назад."""
    hist = history[:origin]
    months = _future_months(origin, h)
    return pd.Series([hist[m - pd.DateOffset(years=1)] for m in months], index=months)


def seasonal_mean3(history, origin, h):
    """Прогноз = среднее того же месяца за последние 3 года."""
    hist = history[:origin]
    months = _future_months(origin, h)
    values = [np.mean([hist[m - pd.DateOffset(years=k)] for k in (1, 2, 3)]) for m in months]
    return pd.Series(values, index=months)


def climatology(history, origin, h):
    """Прогноз = медиана того же месяца за всю историю до origin."""
    hist = history[:origin]
    by_month = hist.groupby(hist.index.month).median()
    months = _future_months(origin, h)
    return pd.Series([by_month[m.month] for m in months], index=months)


BENCHMARKS = {
    "seasonal_naive": seasonal_naive,
    "seasonal_mean3": seasonal_mean3,
    "climatology": climatology,
}


def cumulative(growth_pct):
    """Накопленный рост за несколько месяцев (перемножение)."""
    return (np.prod(1 + np.asarray(growth_pct) / 100) - 1) * 100


def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(DATA, index_col="month", parse_dates=True)
    y = df[TARGET]
    origin = y.index.max()  # последний известный месяц: октябрь 2026
    h = 6                   # ноябрь 2026 – апрель 2027

    table = pd.DataFrame({name: f(y, origin, h) for name, f in BENCHMARKS.items()})
    janapr = table.loc["2027-01":"2027-04"].apply(cumulative)

    table.round(2).to_csv(OUT / "benchmarks_forecast.csv")
    janapr.round(2).to_csv(OUT / "benchmarks_janapr2027.csv", header=["janapr_growth_pct"])

    print(f"Прогнозы роста цен на продукты в Алматы за месяц, % (данные до {origin:%Y-%m}):")
    print(table.round(2))
    print("\nНакопленный рост за январь–апрель 2027, %:")
    print(janapr.round(2))


if __name__ == "__main__":
    main()
