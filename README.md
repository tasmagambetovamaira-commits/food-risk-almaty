# food-risk-almaty
Food price risk in the off-season: forecast for Almaty stabilization fund
# Food price risk in the off-season (Almaty)

Прогноз роста цен на продукты в январе–апреле 2027 года
для решения стабфонда СПК «Алматы» о закупках и выпуске запасов.

Сайт: (появится на шаге 17)

## Как запустить
(появится по мере работы)

## Команда
- Майра и Айтуар
## Сайт

**Публичный URL:** https://tasmagambetovamaira-commits.github.io/food-risk-almaty/site/

Архитектура: код в `src/` пишет `model/artifact.json`; сайт `site/index.html` читает только его.

```bash
make update   # сырые данные -> обработка -> бэктест -> model/artifact.json
make serve    # открыть http://localhost:8000/site/
```