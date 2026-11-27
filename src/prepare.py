"""

Что делает:
  1. Читает 12 рядов ИПЦ из «Талдау» (продукты + 11 товаров), берёт строки
     «Республика Казахстан» и «г. Алматы», переводит индексы в проценты роста.
  2. Читает индекс FAO (номинальный, месячный): общий + 5 подиндексов.
  3. Читает дневные курсы USD и RUB, оставляет только рабочие дни (пн–пт)
     и считает средний курс за месяц.
  4. Переводит индекс FAO в тенге (FAO в долларах * курс доллара).
  5. Склеивает всё по месяцам и сохраняет data/processed/monthly.csv.

Сырые файлы НЕ изменяются: скрипт только читает их.

Запуск из корня репозитория:
    python src/prepare.py

"""

from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
DATE_TAG = "2026-11-22"  # дата выгрузки сырых файлов (из ledger)

# Ряды «Талдау»: короткое имя -> часть имени файла
TALDAU = {
    "food": "food",
    "potato": "potato",
    "cabbage": "cabbage",
    "onion": "onion",
    "carrot": "carrot",
    "sugar": "sugar",
    "beef": "beef",
    "chicken": "chicken_legs",
    "eggs": "eggs",
    "flour": "flour",
    "milk": "milk",
    "oil": "sunflower_oil",
}
REGIONS = {"РЕСПУБЛИКА КАЗАХСТАН": "rk", "Г.АЛМАТЫ": "almaty"}

MONTHS_RU = {
    "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4, "Май": 5, "Июнь": 6,
    "Июль": 7, "Август": 8, "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12,
}


def parse_month(label):
    """'Январь 2011 г.' -> Timestamp('2011-01-01')."""
    parts = str(label).split()
    return pd.Timestamp(year=int(parts[1]), month=MONTHS_RU[parts[0]], day=1)


def to_number(x):
    """'101,2' -> 101.2; пусто или 'х' (конфиденциально) -> NaN."""
    s = str(x).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def read_taldau(name, file_part):
    """Один файл «Талдау» -> таблица: месяц, {name}_rk, {name}_almaty (рост за месяц, %)."""
    path = RAW / f"taldau_cpi_{file_part}_monthly_{DATE_TAG}.xls"
    raw = pd.read_excel(path, header=None, engine="calamine")

    # Строка с заголовками: первая ячейка «Регион», дальше месяцы
    header_row = raw.index[raw.iloc[:, 0].astype(
        str).str.strip() == "Регион"][0]
    months = [parse_month(m) for m in raw.iloc[header_row, 1:].dropna()]

    result = pd.DataFrame(index=pd.DatetimeIndex(months, name="month"))
    for i in range(header_row + 1, len(raw)):
        region = str(raw.iloc[i, 0]).strip()
        if region in REGIONS:
            values = [to_number(v) for v in raw.iloc[i, 1:len(months) + 1]]
            # Индекс к предыдущему месяцу (101,2) -> рост за месяц в % (1,2)
            result[f"{name}_{REGIONS[region]}"] = np.array(values) - 100
    return result


def read_fao():
    """Индекс FAO, номинальный, месячный: общий и 5 подиндексов (в долларах)."""
    path = RAW / f"fao_food_price_index_monthly_{DATE_TAG}.xlsx"
    raw = pd.read_excel(path, sheet_name="Indices_Monthly",
                        header=None, engine="calamine")
    header_row = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Date"][0]
    df = raw.iloc[header_row + 1:, :7]
    df.columns = ["month", "fao_food", "fao_meat", "fao_dairy",
                  "fao_cereals", "fao_oils", "fao_sugar"]
    df = df.dropna(subset=["month"])
    df["month"] = pd.to_datetime(
        df["month"]).dt.to_period("M").dt.to_timestamp()
    return df.set_index("month").astype(float)


def read_rates():
    """Дневные курсы -> среднемесячные, только по рабочим дням (пн–пт)."""
    path = RAW / f"nbk_usd_rub_kzt_daily_{DATE_TAG}.xlsx"
    df = pd.read_excel(path, engine="calamine")
    df["Date"] = pd.to_datetime(df["Date"], format="%d.%m.%Y")
    # Курс за 1 единицу валюты (на случай, если quant не 1)
    df["usd_kzt"] = df["USD"] / df["USD_quant"]
    df["rub_kzt"] = df["RUB"] / df["RUB_quant"]
    # В выходные Нацбанк курс не устанавливает, там повтор пятницы -> убираем
    df = df[df["Date"].dt.day_of_week < 5]
    monthly = df.set_index(
        "Date")[["usd_kzt", "rub_kzt"]].resample("MS").mean()
    monthly.index.name = "month"
    return monthly


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    parts = [read_taldau(name, file_part)
             for name, file_part in TALDAU.items()]
    cpi = pd.concat(parts, axis=1)

    fao = read_fao()
    rates = read_rates()

    # Склейка по месяцам. Период: от начала ИПЦ (январь 2011) до последнего
    # полного месяца курсов, чтобы не взять неполный ноябрь 2026.
    df = cpi.join(fao, how="left").join(rates, how="left")

    # FAO в тенге: индекс в долларах * курс доллара (масштаб не важен, важна динамика)
    df["fao_food_kzt"] = df["fao_food"] * df["usd_kzt"]
    df["fao_sugar_kzt"] = df["fao_sugar"] * df["usd_kzt"]

    # Проверки: скрипт остановится с понятной ошибкой, если что-то не так
    assert df.index.min() == pd.Timestamp(
        "2011-01-01"), "ИПЦ должен начинаться с января 2011"
    assert df["food_almaty"].notna().all(
    ), "в целевом ряду (продукты, Алматы) есть пропуски"
    assert df[["fao_food", "usd_kzt", "rub_kzt"]
              ].notna().all().all(), "пропуски в FAO или курсах"
    assert df["usd_kzt"].between(100, 1000).all(
    ), "курс доллара вне разумных пределов"
    assert df["rub_kzt"].between(
        1, 20).all(), "курс рубля вне разумных пределов"

    out_path = OUT / "monthly.csv"
    df.round(4).to_csv(out_path)
    print(f"Готово: {out_path}")
    print(
        f"Месяцев: {len(df)} ({df.index.min():%Y-%m} – {df.index.max():%Y-%m}), столбцов: {df.shape[1]}")
    print(df[["food_almaty", "food_rk", "fao_food", "usd_kzt", "rub_kzt"]].tail(3))


if __name__ == "__main__":
    main()
