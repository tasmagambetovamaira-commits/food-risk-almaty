"""
Шаг 14. Диагностика остатков кандидатов — по пререгистрации (§6, §7).

Идея: если модель забрала из данных всю закономерность, её остатки — «белый шум»:
нет автокорреляции, нет сезонного хвоста. Если закономерность осталась — модель недоописала ряд.

Тесты (на всей выборке, 2011–2026):
  Ljung–Box (лаги 3 и 12): H0 — нет автокорреляции остатков до лага k. p > 0,05 = хорошо.
  Breusch–Godfrey (лаги 3 и 12, только OLS): то же, но корректно при лаге зависимой переменной в регрессии.
  Jarque–Bera: H0 — остатки нормальны. Ожидаем отказ из-за шоков (2022) — поэтому интервалы
               строим по эмпирическим процентилям ошибок, а не по нормальному распределению.
  ARCH LM (лаг 12): H0 — разброс остатков постоянный (нет кластеров волатильности).

Правило выбора (пререгистрация §6): из моделей с Ljung–Box(12) p > 0,05 — минимальная асимметричная
потеря на горизонте 1 мес.; при разнице < 5% — более простая модель.

Запуск: python src/diagnostics.py
AI-assisted: see AI_USE entry A15; reviewed and tested by Майра, Айтуар.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, acorr_ljungbox, het_arch
from statsmodels.stats.stattools import jarque_bera
from statsmodels.graphics.tsaplots import plot_acf

import models
from models import add_driver_growth, fit_summary

DATA = Path("data/processed/monthly.csv")
OUT = Path("outputs")
PARAMS = {"ar1_seasonal": 14, "sarima": 4, "ar1_drivers": 19}  # число оценённых параметров
SIMPLER_FIRST = ["ar1_seasonal", "sarima", "ar1_drivers"]       # порядок по сложности


def diagnose(name, fit, resid):
    lb = acorr_ljungbox(resid, lags=[3, 12], return_df=True)
    row = {"model": name, "n": len(resid),
           "lb3_p": lb.loc[3, "lb_pvalue"], "lb12_p": lb.loc[12, "lb_pvalue"]}
    if name != "sarima":
        row["bg3_p"] = acorr_breusch_godfrey(fit, nlags=3)[1]
        row["bg12_p"] = acorr_breusch_godfrey(fit, nlags=12)[1]
    row["jb_p"] = jarque_bera(resid)[1]
    row["arch12_p"] = het_arch(resid, nlags=12)[1]
    row["passes_lb12"] = row["lb12_p"] > 0.05
    return row


def main():
    df = add_driver_growth(pd.read_csv(DATA, index_col="month", parse_dates=True))
    models.TARGET = "food_almaty"
    fits = fit_summary(df)

    rows, resids = [], {}
    for name, fit in fits.items():
        r = fit.resid.dropna()
        if name == "sarima":
            r = r.iloc[13:]  # первые месяцы SARIMA — разогрев фильтра, не остатки
        resids[name] = r
        rows.append(diagnose(name, fit, r))
    diag = pd.DataFrame(rows).set_index("model")

    # Самые большие остатки основной модели — где модель «не поняла» месяц
    top = resids["ar1_seasonal"].abs().sort_values(ascending=False).head(6)
    print("Крупнейшие остатки ar1_seasonal:")
    print(resids["ar1_seasonal"].loc[top.index].round(2).to_string())

    # Правило выбора из пререгистрации
    loss = pd.read_csv(OUT / "model_backtest_monthly_summary.csv").query("h == 1").set_index("model")["asym_loss"]
    diag["asym_loss_h1"] = loss.reindex(diag.index)
    ok = diag[diag.passes_lb12]
    if ok.empty:
        choice = "нет модели с белым шумом — применить разрешённые доработки §7"
    else:
        best = ok.asym_loss_h1.idxmin()
        choice = best
        for simple in SIMPLER_FIRST:  # более простая модель, если хуже не более чем на 5%
            if simple in ok.index and ok.loc[simple, "asym_loss_h1"] <= 1.05 * ok.loc[best, "asym_loss_h1"]:
                choice = simple
                break

    OUT.mkdir(exist_ok=True)
    diag.round(4).to_csv(OUT / "diagnostics.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
    for ax, name in zip(axes, ["ar1_seasonal", "sarima"]):
        plot_acf(resids[name], lags=24, ax=ax, zero=False)
        ax.set_title(f"ACF остатков: {name}")
    fig.tight_layout()
    fig.savefig(OUT / "08_resid_acf.png", dpi=150)

    print("\nДиагностика остатков (p-значения; > 0,05 — гипотеза H0 не отвергается):")
    print(diag.round(3).to_string())
    print(f"\nВыбор по правилу пререгистрации: {choice}")


if __name__ == "__main__":
    main()
