"""
Шаг 10. Стационарность и ACF/PACF.

Вопросы шага:
  1. Стационарен ли ряд, который будем моделировать? (ADF и KPSS)
     Проверяем три варианта: уровень цен (индекс), рост за месяц,
     рост за месяц после сезонной разности.
  2. Какая память у ряда? (ACF и PACF) — отсюда порядки SARIMA (p, d, q)(P, D, Q).
  3. Стационарны ли драйверы: рост FAO в тенге и рост курсов.

Результаты: outputs/stationarity_tests.csv, outputs/06_acf_pacf.png,
            outputs/07_level_vs_growth.png
Запуск: python src/stationarity.py

AI-assisted: see AI_USE entry A08; reviewed and tested by [имена].
"""

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller, kpss

warnings.filterwarnings("ignore", category=InterpolationWarning)  # KPSS: p-value за пределами таблицы
warnings.filterwarnings("ignore", category=FutureWarning)         # будущая смена формата результатов ADF/KPSS

DATA = Path("data/processed/monthly.csv")
OUT = Path("outputs")
BLUE, GREY = "#0072B2", "#999999"


def adf_kpss(series, name):
    """ADF: H0 = есть единичный корень (нестационарен).
       KPSS: H0 = стационарен.
       Вывод «стационарен», если ADF отвергает H0, а KPSS — нет."""
    s = series.dropna()
    adf_stat, adf_p, *_ = adfuller(s, autolag="AIC", regression="c")
    kpss_stat, kpss_p, *_ = kpss(s, regression="c", nlags="auto")
    if adf_p < 0.05 and kpss_p > 0.05:
        verdict = "стационарен"
    elif adf_p >= 0.05 and kpss_p <= 0.05:
        verdict = "нестационарен"
    else:
        verdict = "тесты расходятся"
    return {"ряд": name, "n": len(s),
            "ADF_stat": round(adf_stat, 3), "ADF_p": round(adf_p, 4),
            "KPSS_stat": round(kpss_stat, 3), "KPSS_p": round(kpss_p, 4),
            "вывод": verdict}


def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(DATA, index_col="month", parse_dates=True)
    growth = df["food_almaty"]                               # рост за месяц, %
    level = 100 * np.cumprod(1 + growth / 100)               # уровень цен, январь 2011 ≈ 100
    seasonal_diff = growth.diff(12)                          # рост минус рост год назад
    fao_growth = df["fao_food_kzt"].pct_change() * 100       # рост FAO в тенге, %
    usd_growth = df["usd_kzt"].pct_change() * 100
    rub_growth = df["rub_kzt"].pct_change() * 100

    tests = pd.DataFrame([
        adf_kpss(level, "уровень цен (индекс)"),
        adf_kpss(growth, "рост за месяц (целевой)"),
        adf_kpss(seasonal_diff, "рост за месяц, сезонная разность"),
        adf_kpss(df["fao_food_kzt"], "FAO в тенге, уровень"),
        adf_kpss(fao_growth, "FAO в тенге, рост за месяц"),
        adf_kpss(usd_growth, "USD/KZT, рост за месяц"),
        adf_kpss(rub_growth, "RUB/KZT, рост за месяц"),
    ])
    tests.to_csv(OUT / "stationarity_tests.csv", index=False)

    # Уровень против роста: почему моделируем рост
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axes[0].plot(level.index, level, color=BLUE)
    axes[0].set_title("Уровень цен на продукты в Алматы (янв 2011 = 100): растёт всё время — нестационарен")
    axes[1].plot(growth.index, growth, color=BLUE)
    axes[1].axhline(growth.mean(), color=GREY, ls="--")
    axes[1].set_title("Рост за месяц, %: колеблется вокруг постоянного среднего — стационарен")
    fig.tight_layout()
    fig.savefig(OUT / "07_level_vs_growth.png", dpi=150)
    plt.close(fig)

    # ACF и PACF целевого ряда
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    plot_acf(growth, lags=36, ax=axes[0], color=BLUE)
    axes[0].set_title("ACF роста цен (Алматы): всплески на лагах 1–2 и 12, 24 — краткая память и сезонность")
    plot_pacf(growth, lags=36, ax=axes[1], method="ywm", color=BLUE)
    axes[1].set_title("PACF роста цен (Алматы): значимые лаги указывают порядок AR")
    fig.tight_layout()
    fig.savefig(OUT / "06_acf_pacf.png", dpi=150)
    plt.close(fig)

    # Числовые значения ACF/PACF на ключевых лагах
    from statsmodels.tsa.stattools import acf, pacf
    a = acf(growth, nlags=24)
    p = pacf(growth, nlags=24, method="ywm")
    bound = 1.96 / np.sqrt(len(growth))  # граница значимости ±1.96/√n
    lags = [1, 2, 3, 6, 11, 12, 13, 24]
    acf_table = pd.DataFrame({"lag": lags, "ACF": a[lags].round(3), "PACF": p[lags].round(3)})
    acf_table["граница_±"] = round(bound, 3)
    acf_table.to_csv(OUT / "acf_pacf_values.csv", index=False)

    pd.set_option("display.width", 200)
    print("Тесты стационарности:")
    print(tests.to_string(index=False))
    print(f"\nACF/PACF на ключевых лагах (значимо, если |значение| > {bound:.3f}):")
    print(acf_table.to_string(index=False))


if __name__ == "__main__":
    main()
