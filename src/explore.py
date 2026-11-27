"""
Шаг 7. Разведочный анализ: что происходит с ценами на продукты в Алматы.

Читает data/processed/monthly.csv и делает:
  1. График ряда: рост цен за месяц, Алматы и РК.
  2. Сезонный профиль: типичный рост цен в каждом месяце года.
  3. STL-декомпозицию: тренд + сезонность + остаток.
  4. «Обычный сезон»: накопленный рост за январь–апрель по годам,
     медиана и 75-й процентиль (это порог стабфонда).
  5. Проверку гипотезы про НДС: были ли декабрь 2025 – февраль 2026 необычными.
  6. Вклад товаров: какие продукты сильнее всего дорожают в межсезонье.

Результаты: графики в outputs/, цифры в outputs/eda_summary.csv.
Запуск: python src/explore.py

AI-assisted: see AI_USE entry A05; reviewed and tested by [имена].
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # рисуем в файлы, без окна
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

DATA = Path("data/processed/monthly.csv")
OUT = Path("outputs")
SHOCK_YEARS = [2015, 2016, 2022]  # девальвация 2015–2016, шок 2022
ITEMS = ["potato", "cabbage", "onion", "carrot", "sugar", "beef",
         "chicken", "eggs", "flour", "milk", "oil"]

# Палитра, различимая при дальтонизме (Okabe–Ito)
BLUE, ORANGE, GREY = "#0072B2", "#E69F00", "#999999"


def cumulative(growth_pct):
    """Накопленный рост за несколько месяцев: перемножаем, а не складываем."""
    return (np.prod(1 + growth_pct / 100) - 1) * 100


def jan_apr_by_year(series):
    """Накопленный рост за январь–апрель для каждого года."""
    years = sorted(set(series.index.year))
    return pd.Series({y: cumulative(series[f"{y}-01":f"{y}-04"]) for y in years
                      if len(series[f"{y}-01":f"{y}-04"]) == 4})


def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(DATA, index_col="month", parse_dates=True)
    almaty, rk = df["food_almaty"], df["food_rk"]
    summary = {}

    # 1. Ряд целиком
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(almaty.index, almaty, color=BLUE, lw=1.4, label="Алматы")
    ax.plot(rk.index, rk, color=GREY, lw=1, label="Казахстан")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title("Рост цен на продукты за месяц, %: всплески в 2015–2016 и 2022, в остальное время 0–2%")
    ax.set_ylabel("% к предыдущему месяцу")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "01_series.png", dpi=150)
    plt.close(fig)

    # 2. Сезонный профиль: медиана по каждому месяцу года (без шоковых лет)
    calm = almaty[~almaty.index.year.isin(SHOCK_YEARS)]
    profile = calm.groupby(calm.index.month).median()
    months = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = [ORANGE if m in (12, 1, 2, 3, 4) else BLUE for m in profile.index]
    ax.bar(months, profile.values, color=colors)
    ax.set_title("Типичный рост цен на продукты в Алматы по месяцам: максимум с декабря по апрель")
    ax.set_ylabel("медиана, % за месяц")
    fig.tight_layout()
    fig.savefig(OUT / "02_seasonal_profile.png", dpi=150)
    plt.close(fig)
    for m, v in profile.items():
        summary[f"seasonal_median_month_{m:02d}"] = v

    # 3. STL-декомпозиция: тренд, сезонность, остаток
    stl = STL(almaty, period=12, robust=True).fit()
    fig = stl.plot()
    fig.set_size_inches(10, 7)
    fig.suptitle("STL-декомпозиция: рост цен на продукты, Алматы", y=1.0)
    fig.tight_layout()
    fig.savefig(OUT / "03_stl.png", dpi=150)
    plt.close(fig)
    summary["stl_seasonal_strength"] = max(
        0, 1 - stl.resid.var() / (stl.seasonal + stl.resid).var())

    # 4. Обычный сезон: январь–апрель по годам
    ja = jan_apr_by_year(almaty)
    ja_calm = ja.drop(SHOCK_YEARS, errors="ignore")
    summary["janapr_median_calm"] = ja_calm.median()
    summary["janapr_p75_calm"] = ja_calm.quantile(0.75)
    summary["janapr_median_all"] = ja.median()
    summary["janapr_p75_all"] = ja.quantile(0.75)
    fig, ax = plt.subplots(figsize=(10, 4))
    colors = [ORANGE if y in SHOCK_YEARS else BLUE for y in ja.index]
    ax.bar(ja.index.astype(str), ja.values, color=colors)
    ax.axhline(summary["janapr_median_calm"], color="black", ls="--", lw=1,
               label=f"обычный сезон (медиана) = {summary['janapr_median_calm']:.1f}%")
    ax.axhline(summary["janapr_p75_calm"], color="black", ls=":", lw=1,
               label=f"хуже 3 из 4 лет (75-й процентиль) = {summary['janapr_p75_calm']:.1f}%")
    ax.set_title("Рост цен на продукты в Алматы за январь–апрель: обычно около 4%, в 2022 году — 12%")
    ax.set_ylabel("% за 4 месяца")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "04_jan_apr.png", dpi=150)
    plt.close(fig)

    # 5. Гипотеза про НДС: декабрь 2025 – февраль 2026 против обычного
    for label, month in [("dec2025", "2025-12-01"), ("jan2026", "2026-01-01"), ("feb2026", "2026-02-01")]:
        m = pd.Timestamp(month).month
        summary[f"vat_{label}_almaty"] = almaty[month]
        summary[f"vat_{label}_rk"] = rk[month]
        summary[f"vat_{label}_typical_almaty"] = profile[m]

    # 6. Вклад товаров: средний рост за январь–апрель (без шоковых лет), Алматы
    item_season = {}
    for item in ITEMS:
        s = jan_apr_by_year(df[f"{item}_almaty"]).drop(SHOCK_YEARS, errors="ignore")
        item_season[item] = s.median()
    item_season = pd.Series(item_season).sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(item_season.index, item_season.values, color=BLUE)
    ax.set_title("Что дорожает в межсезонье: медианный рост за январь–апрель, Алматы")
    ax.set_xlabel("% за 4 месяца")
    fig.tight_layout()
    fig.savefig(OUT / "05_items.png", dpi=150)
    plt.close(fig)
    for item, v in item_season.items():
        summary[f"janapr_median_{item}"] = v

    # Сохраняем цифры и таблицу сезонов по годам
    pd.Series(summary).round(3).to_csv(OUT / "eda_summary.csv", header=["value"])
    ja.round(2).to_csv(OUT / "jan_apr_by_year.csv", header=["janapr_growth_pct"])

    print("Графики и таблицы сохранены в outputs/")
    print(f"Обычный сезон (янв–апр, без шоков): медиана {summary['janapr_median_calm']:.2f}%, "
          f"75-й процентиль {summary['janapr_p75_calm']:.2f}%")
    print(f"НДС, Алматы: дек 2025 {summary['vat_dec2025_almaty']:.1f}% (обычно {profile[12]:.2f}), "
          f"янв 2026 {summary['vat_jan2026_almaty']:.1f}% (обычно {profile[1]:.2f}), "
          f"фев 2026 {summary['vat_feb2026_almaty']:.1f}% (обычно {profile[2]:.2f})")
    print("Товары (медиана янв–апр, %):", item_season.round(1).to_dict())


if __name__ == "__main__":
    main()
