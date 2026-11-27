"""
Шаг 12. Прогноз для Reality Check, который замораживается в пререгистрации.

Что считает (данные по октябрь 2026 включительно):
  - основной ряд: рост цен на продукты, г. Алматы, ноябрь 2026, % к октябрю;
  - запасной ряд: то же по Республике Казахстан;
  - для каждой модели и бенчмарка: точечный прогноз и 80%-интервал
    (10-й и 90-й процентили прошлых ошибок на горизонте 1 месяц из бэктеста);
  - прогноз накопленного роста за январь–апрель 2027 (для решения стабфонда).

Результат: prereg/reality_check_forecast.csv — эти числа переносятся в prereg/prereg.md.

Запуск: python src/reality_check.py
AI-assisted: see AI_USE entry A11; reviewed and tested by Майра, Айтуар.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import models
from benchmarks import BENCHMARKS, cumulative
from models import MODELS, add_driver_growth

DATA = Path("data/processed/monthly.csv")
OUT = Path("prereg")
CANDIDATES = ["ar1_seasonal", "sarima", "climatology", "seasonal_naive"]


def past_errors(df, target, name, origin):
    """Ошибки прогноза на 1 месяц вперёд с января 2014 по origin (rolling origin)."""
    f = MODELS.get(name) or (lambda d, o, h, g=BENCHMARKS[name]: g(d[target], o, h))
    errs = []
    for o in df.index[(df.index >= "2014-01-01") & (df.index < origin)]:
        m = o + pd.offsets.MonthBegin(1)
        errs.append(df.loc[m, target] - f(df, o, 1).iloc[0])
    return np.array(errs)


def main():
    OUT.mkdir(exist_ok=True)
    base = add_driver_growth(pd.read_csv(DATA, index_col="month", parse_dates=True))
    origin = base.index.max()  # октябрь 2026
    rows = []
    for region, target in [("almaty", "food_almaty"), ("rk", "food_rk")]:
        models.TARGET = target          # модели читают целевой ряд из models.TARGET
        df = base
        for name in CANDIDATES:
            f = MODELS.get(name) or (lambda d, o, h, g=BENCHMARKS[name]: g(d[target], o, h))
            fc = f(df, origin, 6)
            e = past_errors(df, target, name, origin)
            nov = fc.iloc[0]
            janapr = cumulative(fc.loc["2027-01":"2027-04"])
            rows.append({"region": region, "model": name, "nov2026_point": round(nov, 2),
                         "nov2026_lo80": round(nov + np.quantile(e, 0.10), 2),
                         "nov2026_hi80": round(nov + np.quantile(e, 0.90), 2),
                         "janapr2027_point": round(janapr, 2), "n_past_errors": len(e)})
    models.TARGET = "food_almaty"
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "reality_check_forecast.csv", index=False)
    print(f"Данные по {origin:%Y-%m}. Прогноз на ноябрь 2026 (рост за месяц, %) и январь–апрель 2027:")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
