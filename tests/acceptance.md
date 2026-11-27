# Acceptance test

Проверяется на чистом клоне: `git clone … && cd food-risk-almaty && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
10 проверок опубликованы заранее; 2 объявляются на Update Drill.

| # | Проверка | Как проверить | Ожидается |
|---|---|---|---|
| 1 | Одна команда собирает всё | `make update` | завершается без ошибок, последняя строка начинается с «OK: model/artifact.json» |
| 2 | Сырые данные не изменены | `git status data/raw` после `make update` | нет изменений |
| 3 | Нет утечки будущего | `python src/backtest.py` и `python src/backtest_models.py` | строка «Тест на утечку пройден» |
| 4 | Артефакт согласован с пререгистрацией | `python src/export_artifact.py` | assert не падает (ноябрь 2026 = 0,82 при данных по 2026-10) |
| 5 | Сайт читает только артефакт | `grep -n "fetch(" site/index.html` | единственный fetch — `../model/artifact.json` |
| 6 | Публичный URL открывается | ссылка в README | страница загружается, 7 блоков истории видны |
| 7 | Телефон | DevTools, ширина 360 px | нет горизонтальной прокрутки, подписи графиков читаются |
| 8 | Скорость | Lighthouse / вкладка Network | загрузка < 3 с; страница + артефакт < 100 КБ |
| 9 | Доступность | осмотр кода | у каждого графика `<title>` (alt-текст); палитра Okabe–Ito |
| 10 | Трассировка числа | взять 4,88% и 0,82% с сайта | находятся в ledger, prereg.md и outputs/*.csv |
| 11 | (объявляется на Update Drill) | | |
| 12 | (объявляется на Update Drill) | | |
