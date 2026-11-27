"""
Шаг 11. Кандидаты моделей роста цен на продукты в Алматы (рост за месяц, %).

Три кандидата (выбраны по ACF/PACF из шага 10: AR(1) + сезонность):

  1. ar1_seasonal  — регрессия: рост_t = сезонная поправка месяца + φ · рост_{t-1}.
                     Это climatology (сезонность) плюс «память» прошлого месяца.
  2. sarima        — SARIMA(1,0,0)(1,0,0)₁₂ с константой: та же идея в классической
                     форме ARIMA (сезонная память через лаг 12).
  3. ar1_drivers   — ar1_seasonal + рост FAO в тенге и курсов USD, RUB с лагом 1 и 2 месяца.
                     Лаг — потому что значение драйвера за месяц прогноза в реальности
                     ещё не известно (FAO выходит в начале следующего месяца).

Как прогнозируем дальше 1 месяца: рекурсивно (прогноз месяца t+1 подставляем
как «прошлый рост» для t+2). Будущие значения драйверов неизвестны, поэтому
для них берём 0 (рост курса и FAO = 0, т. е. «останутся на текущем уровне»).
Это честное допущение без подглядывания в будущее; оно записано в model card.

Каждая функция получает данные ТОЛЬКО до origin включительно.

AI-assisted: see AI_USE entry A09; reviewed and tested by [имена].
"""

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")  # SARIMAX пишет предупреждения о сходимости на коротких окнах

TARGET = "food_almaty"
DRIVERS = ["fao_g", "usd_g", "rub_g"]


def add_driver_growth(df):
    """Рост драйверов за месяц, %. Уровни нестационарны (шаг 10), поэтому берём рост."""
    out = df.copy()
    out["fao_g"] = out["fao_food_kzt"].pct_change() * 100
    out["usd_g"] = out["usd_kzt"].pct_change() * 100
    out["rub_g"] = out["rub_kzt"].pct_change() * 100
    return out


def _future_months(origin, h):
    return pd.date_range(origin + pd.offsets.MonthBegin(1), periods=h, freq="MS")


def _design(df, with_drivers):
    """Матрица признаков: 12 месячных дамми (без общей константы), лаг роста, лаги драйверов."""
    X = pd.get_dummies(df.index.month, prefix="m").astype(float)
    X.index = df.index
    X["y_lag1"] = df[TARGET].shift(1)
    if with_drivers:
        for d in DRIVERS:
            X[f"{d}_lag1"] = df[d].shift(1)
            X[f"{d}_lag2"] = df[d].shift(2)
    return X


def _ar_forecast(df, origin, h, with_drivers):
    hist = df[:origin]
    X = _design(hist, with_drivers)
    data = pd.concat([hist[TARGET], X], axis=1).dropna()
    model = sm.OLS(data[TARGET], data.drop(columns=TARGET)).fit()

    # Рекурсивный прогноз
    ext = hist.copy()
    preds = {}
    for m in _future_months(origin, h):
        row = {f"m_{k}": 0.0 for k in range(1, 13)}
        row[f"m_{m.month}"] = 1.0
        row["y_lag1"] = ext[TARGET].iloc[-1]
        if with_drivers:
            for d in DRIVERS:
                row[f"{d}_lag1"] = ext[d].iloc[-1]
                row[f"{d}_lag2"] = ext[d].iloc[-2]
        x = pd.DataFrame([row])[model.params.index]
        yhat = float(model.predict(x)[0])
        preds[m] = yhat
        new = {TARGET: yhat, **{d: 0.0 for d in DRIVERS}}  # будущее драйверов неизвестно -> 0
        ext = pd.concat([ext, pd.DataFrame([new], index=[m])])
    return pd.Series(preds)


def ar1_seasonal(df, origin, h):
    return _ar_forecast(df, origin, h, with_drivers=False)


def ar1_drivers(df, origin, h):
    return _ar_forecast(df, origin, h, with_drivers=True)


def sarima(df, origin, h):
    y = df[TARGET][:origin].asfreq("MS")
    fit = SARIMAX(y, order=(1, 0, 0), seasonal_order=(1, 0, 0, 12), trend="c").fit(disp=False)
    fc = fit.forecast(h)
    fc.index = _future_months(origin, h)
    return fc


MODELS = {
    "ar1_seasonal": ar1_seasonal,
    "sarima": sarima,
    "ar1_drivers": ar1_drivers,
}


def fit_summary(df):
    """Коэффициенты на всей выборке — для понимания и model card (не для бэктеста)."""
    out = {}
    for with_drivers, name in [(False, "ar1_seasonal"), (True, "ar1_drivers")]:
        X = _design(df, with_drivers)
        data = pd.concat([df[TARGET], X], axis=1).dropna()
        out[name] = sm.OLS(data[TARGET], data.drop(columns=TARGET)).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    y = df[TARGET].asfreq("MS")
    out["sarima"] = SARIMAX(y, order=(1, 0, 0), seasonal_order=(1, 0, 0, 12), trend="c").fit(disp=False)
    return out
