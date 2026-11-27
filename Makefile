# Одна команда от сырых данных до сайта: make update
PY ?= .venv/bin/python

update:
	$(PY) src/prepare.py
	$(PY) src/explore.py
	$(PY) src/stationarity.py
	$(PY) src/backtest.py
	$(PY) src/backtest_models.py
	$(PY) src/diagnostics.py
	$(PY) src/export_artifact.py
	@echo "Готово. Локальный просмотр: make serve -> http://localhost:8000/site/"

# Быстрое обновление без бэктеста (если не менялись данные прошлых лет)
artifact:
	$(PY) src/export_artifact.py

serve:
	$(PY) -m http.server 8000

.PHONY: update artifact serve
