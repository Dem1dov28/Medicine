# Medical Knowledge Infrastructure (MKI) — v0

Инфраструктура доказательных медицинских знаний. Мы храним не статьи, а
**атомарные утверждения (Claims)** о здоровье — с явной силой доказательств,
происхождением (provenance) и историей изменения консенсуса.

Модель: **Claim → Evidence → Consensus → Knowledge**.

Документы-основания: `RFC-0000` (философия), `RFC-0001` (техническая спецификация
v0), `RFC-0002` (автономная LLM-верификация).

## Принципы v0

- Намеренно узкий scope: 10–20 веществ, только мета-анализы/систематические обзоры/качественные RCT.
- LLM — вероятностный извлекатель, **не источник истины**: `evidence_level` и
  `consensus_confidence` вычисляют движки (Evidence/Consensus), не модель.
- Верификация автономна (RFC-0002): ансамбль LLM через OpenRouter проверяет
  faithfulness извлечения по дословным цитатам и голосует. Человека в цикле нет;
  спорные Claims уходят в `held`/`rejected`, а не публикуются.
- Противоречия показываются, а не скрываются.

## Стек

Python 3.11+ · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · PostgreSQL (JSONB) /
SQLite для локального запуска.

## Быстрый старт (локально, без Postgres)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# По умолчанию используется SQLite (см. .env.example), внешние сервисы не нужны.
uvicorn app.main:app --reload
```

Открыть документацию API: http://localhost:8000/docs

## Запуск через Docker (с Postgres)

```bash
docker compose up --build
```

## Тесты

```bash
pytest
```

## API (v0)

| Метод и путь | Назначение |
|---|---|
| `POST /internal/extract` | Текст статьи → draft Claim (сохраняет source text) |
| `GET /claims?subject=creatine` | Список Claims по веществу |
| `GET /claims/{id}` | Один Claim с provenance |
| `POST /claims/{id}/verify` | Автономная верификация ансамблем LLM → published/held/rejected |
| `GET /substances/{name}/summary` | Агрегированный консенсус по published Claims |
| `GET /ask?q=...` | Вопрос → релевантные Claims → ответ со ссылками |

Статусы Claim: `draft → auto_verified → published`, плюс терминальные
`held` (ансамбль не уверен) и `rejected` (найдено противоречие источнику).

## Структура

```
app/
├── extraction/   # текст статьи → draft Claim (LLM/stub)
├── evidence/     # GRADE-lite: расчёт evidence_level
├── consensus/    # агрегация консенсуса, обработка конфликтов
├── llm/          # тонкий OpenRouter-клиент (OpenAI-совместимый)
├── verification/ # ансамблевая верификация + правило голосования (RFC-0002)
├── storage/      # SQLAlchemy модели, репозиторий (Claim как JSON-документ + source text)
├── reasoning/    # /ask: вопрос → Claims → ответ
├── api/          # FastAPI роуты
├── services.py   # оркестрация движков и хранилища
├── schemas.py    # Pydantic-контракт Claim (источник истины)
└── main.py
data/goldset.json # размеченный gold-set для калибровки верификатора
scripts/          # gen_rfc0002.py, eval_verifier.py
tests/
```

## Калибровка верификатора

```bash
python scripts/eval_verifier.py         # precision/recall против gold-set
```

Без `MKI_OPENROUTER_API_KEY` измеряется детерминированный stub. С ключом и
`MKI_VERIFIER_MODELS` — реальные модели. Ключевая метрика: **ноль false publish**
(неверный Claim не должен публиковаться).

## Definition of Done (v0)

См. `RFC-0001` §9. Кратко: 10–20 веществ, у каждого ≥3 published Claims;
каждый Claim прошёл верификацию; хотя бы один конфликт показан явно;
3–5 целевых пользователей дали фидбек; все тесты проходят.
