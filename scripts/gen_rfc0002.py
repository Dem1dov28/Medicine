"""One-off generator for RFC-0002 as a .docx (matches RFC-0000/0001 format)."""

from docx import Document
from docx.shared import Pt


def add_kv_table(doc, rows):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for k, v in rows:
        cells = table.add_row().cells
        cells[0].text = k
        cells[1].text = v
    doc.add_paragraph("")


def add_grid_table(doc, header, rows):
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    for i, h in enumerate(header):
        table.rows[0].cells[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = val
    doc.add_paragraph("")


doc = Document()

doc.add_heading("RFC-0002 — Autonomous LLM Verification", level=0)

add_kv_table(doc, [
    ("Статус", "Draft"),
    ("Автор", "[заполнить]"),
    ("Версия", "0.1"),
    ("Обновлено", "2 июля 2026"),
    ("Ссылается на", "RFC-0000 (Philosophy), RFC-0001 (Technical Spec v0)"),
    ("Заменяет", "RFC-0001 §5 (Human verification gate)"),
])

doc.add_heading("Abstract", level=1)
doc.add_paragraph(
    "Этот документ заменяет ручную проверку Claims (RFC-0001 §5) на автономную "
    "верификацию ансамблем LLM через OpenRouter. Человек исключается из цикла для "
    "happy-path. Ключевая идея: LLM заменяет не «авторитета по медицинской истине», "
    "а QA извлечения — узкую, проверяемую задачу сверки извлечённого Claim с текстом "
    "источника. Уровень доказательности по-прежнему вычисляет Evidence Engine по "
    "правилам, а не LLM. Так сохраняется первый принцип RFC-0000 «LLM is a "
    "probabilistic extractor, not an authority»."
)

doc.add_heading("Motivation", level=1)
doc.add_paragraph(
    "В RFC-0001 §5 верификация человеком объявлена намеренным бутылочным горлышком: "
    "скорость извлечения ограничена скоростью ручной проверки. Это блокирует "
    "масштабирование даже на узком срезе v0. Работа проверяющего сводится к двум "
    "проверяемым задачам, ни одна из которых не требует «медицинского авторитета»:"
)
doc.add_paragraph("Faithfulness-check — соответствует ли извлечённый Claim тексту статьи "
                  "(дозировка, выборка, направление и величина эффекта).", style="List Number")
doc.add_paragraph("Предложение downgrade-флагов (малая выборка, высокая гетерогенность).",
                  style="List Number")
doc.add_paragraph(
    "Обе задачи — это контроль качества извлечения, а не установление истины. "
    "Поэтому их можно делегировать LLM при условии строгих гардрейлов ниже."
)

doc.add_heading("Принцип и его сохранение", level=1)
doc.add_paragraph(
    "Разрешение противоречия с RFC-0000: чёткая граница между тем, что LLM может и "
    "не может решать."
)
add_grid_table(doc, ["LLM решает (verifier)", "LLM НЕ решает"], [
    ["Подтверждается ли каждое поле Claim дословной цитатой из источника",
     "Уровень доказательности (evidence_level) — только Evidence Engine по правилам"],
    ["Предлагает downgrade-флаги (малая выборка, гетерогенность)",
     "Применение downgrade-флагов — только Evidence Engine"],
    ["Общий вердикт pass / hold / reject для черновика",
     "Формулу consensus_confidence — только Consensus Engine"],
])

doc.add_heading("Decision", level=1)
doc.add_paragraph(
    "Принято: полностью автономная верификация без человека в цикле, ансамблем из "
    "2–3 разных моделей через OpenRouter, с голосованием. Спорные и неуверенные "
    "случаи не эскалируются человеку (его нет), а автоматически переводятся в "
    "held/rejected и не публикуются."
)

doc.add_heading("Гардрейлы", level=1)
for item in [
    "Extractor ≠ Verifier. Claim проверяет модель(и), отличная от извлекавшей. "
    "Само-проверка одной моделью запрещена.",
    "Grounded verification. По каждому проверяемому полю — дословная цитата-спан из "
    "источника. Нет цитаты → поле не прошло. Цитаты сохраняются как provenance.",
    "Ансамбль и голосование. 2–3 разные модели; итог по правилу голосования.",
    "Пороги уверенности. Публикуются только Claims выше порога; остальные held/rejected.",
    "Evidence Engine владеет уровнем. LLM только предлагает downgrade-флаги.",
    "Полная аудируемость. Запись verification: модели, вердикты, цитаты, флаги, "
    "версии, время.",
]:
    doc.add_paragraph(item, style="List Number")

doc.add_heading("Правило голосования (v0)", level=1)
doc.add_paragraph(
    "Каждая модель возвращает вердикт по Claim: pass, fail или uncertain, плюс "
    "per-field цитаты и confidence 0.0–1.0."
)
add_grid_table(doc, ["Условие", "Итоговый статус"], [
    ["Все модели pass И средний confidence ≥ 0.75", "auto_verified → published"],
    ["Есть хотя бы один fail (найдено противоречие источнику)", "rejected"],
    ["Смешанные pass/uncertain, confidence < 0.75, или нет цитат по CORE-полям",
     "held (не публикуется, ждёт перепрогона)"],
])
doc.add_paragraph(
    "Примечание о reconcile: итоговый вердикт модели приводится к правилу "
    "core-only — если все оценённые CORE-поля подтверждены, 'uncertain' "
    "повышается до 'pass' (модель, вероятно, придралась к context-детали); "
    "'fail' (противоречие) никогда не повышается."
)
doc.add_paragraph(
    "Поля разделены на два уровня (уточнено после первой калибровки): "
    "CORE (subject, outcome, effect.direction) — обязаны быть подтверждены "
    "цитатой, иначе Claim не публикуется; CONTEXT (population, intervention, "
    "comparator) — цитируются при наличии, но отсутствие детали (например, точной "
    "дозы) само по себе не блокирует. Прямое ПРОТИВОРЕЧИЕ источнику в любом поле "
    "(core или context) даёт fail."
)

doc.add_heading("Статусная модель", level=1)
doc.add_paragraph("Расширение RFC-0001: draft → auto_verified → published, плюс "
                  "терминальные ветки held и rejected.")
add_grid_table(doc, ["Статус", "Значение"], [
    ["draft", "Извлечён, не проверен"],
    ["auto_verified", "Ансамбль подтвердил выше порога"],
    ["published", "Виден в /ask и /summary"],
    ["held", "Ансамбль не уверен; не публикуется; можно перепрогнать"],
    ["rejected", "Найдено противоречие источнику; не публикуется"],
])
doc.add_paragraph(
    "Поле verified_by становится структурным: значение вида llm:ensemble с "
    "прикреплённой записью verification. Значение human:<id> остаётся допустимым "
    "для будущего ручного override, но в happy-path не используется."
)

doc.add_heading("Запись Verification (provenance проверки)", level=1)
doc.add_paragraph("К каждому проверенному Claim прикрепляется объект verification:")
for item in [
    "models: список {name, version/id провайдера}",
    "per_model_verdicts: {model, verdict, confidence, field_quotes, proposed_downgrades, notes}",
    "decision: итоговый статус и применённое правило голосования",
    "source_ref: ссылка на сохранённый исходный текст",
    "created_at",
]:
    doc.add_paragraph(item, style="List Bullet")

doc.add_heading("Персист исходного текста", level=1)
doc.add_paragraph(
    "Верификация невозможна без текста источника, поэтому исходный текст статьи "
    "(или релевантные спаны) сохраняется вместе с draft Claim. Это усиливает "
    "принцип RFC-0000 «Evidence has Provenance»."
)

doc.add_heading("Калибровка перед доверием", level=1)
doc.add_paragraph("Порог авто-публикации (0.75 — стартовое значение) нельзя "
                  "принимать вслепую. До включения полной автономии:")
for item in [
    "Собрать gold-set: 10–20 Claims, размеченных человеком (pass/fail).",
    "Прогнать ансамбль, измерить precision/recall вердиктов против человека.",
    "Поднимать порог только по результатам замера. Целевая метрика v0: precision "
    "«reject» высок (не пропускаем неверные Claims), recall может быть ниже "
    "(лишний held безопаснее ложного published).",
]:
    doc.add_paragraph(item, style="List Number")
doc.add_paragraph("Это заодно закрывает часть Definition of Done RFC-0001 §9.")

doc.add_heading("OpenRouter — интеграция", level=1)
for item in [
    "OpenAI-совместимый API: base_url https://openrouter.ai/api/v1, эндпоинт chat/completions.",
    "Конфиг: MKI_OPENROUTER_API_KEY, MKI_VERIFIER_MODELS (список слугов), MKI_VERIFY_THRESHOLD.",
    "Структурный вывод: строгий JSON-контракт + валидация Pydantic + ретрай при "
    "ошибке парсинга; не полагаться на native JSON-mode всех моделей.",
    "Стоимость/латентность: верификация пригодна для фонового выполнения; в v0 "
    "допускается синхронный вызов в отдельном сервисном слое.",
    "Fallback: если ключ не задан — stub-режим (детерминированный), как у extractor.",
]:
    doc.add_paragraph(item, style="List Bullet")

doc.add_heading("Архитектура (модули)", level=1)
code = doc.add_paragraph()
run = code.add_run(
    "app/\n"
    "├── llm/\n"
    "│   └── openrouter.py     # тонкий OpenAI-совместимый клиент к OpenRouter\n"
    "├── verification/\n"
    "│   ├── schemas.py        # VerificationResult, ModelVerdict, FieldQuote\n"
    "│   ├── verifier.py       # оркестратор ансамбля + правило голосования\n"
    "│   └── prompt.py         # промпт grounded-проверки"
)
run.font.name = "Courier New"
run.font.size = Pt(9)
doc.add_paragraph(
    "Точки интеграции: extractor сохраняет source_text с draft; сервис "
    "verify_claim_llm(claim, source_text) → VerificationResult → обновление статуса; "
    "Evidence Engine принимает proposed_downgrades из вердикта."
)

doc.add_heading("Риски и меры", level=1)
add_grid_table(doc, ["Риск", "Мера"], [
    ["Согласованная галлюцинация всех моделей", "Обязательные дословные цитаты; провал при отсутствии спана"],
    ["Систематический сдвиг одной модели", "Ансамбль из разных семейств моделей"],
    ["Дрейф качества провайдера", "Периодический прогон gold-set как регресс-теста"],
    ["Ложный published", "Асимметричные пороги: сомнение → held, а не publish"],
    ["Стоимость", "Ансамбль только на верификации; extractor — одна модель"],
])

doc.add_heading("Definition of Done (для этого изменения)", level=1)
for item in [
    "OpenRouter-клиент со stub-fallback; ключ и модели в конфиге.",
    "Исходный текст персистится с draft Claim.",
    "Grounded ансамблевая верификация с обязательными цитатами и голосованием.",
    "Статусы held/rejected реализованы; published только через auto_verified.",
    "Запись verification прикреплена к Claim и доступна в API (provenance).",
    "Gold-set из ≥10 Claims и скрипт замера precision/recall.",
    "Тесты: правило голосования, парсинг вердикта, stub-путь e2e.",
]:
    doc.add_paragraph(item, style="List Bullet")

doc.add_paragraph(
    "Ссылается на RFC-0000 и RFC-0001. Заменяет решение §5 RFC-0001 о ручной "
    "проверке; остальные разделы RFC-0001 остаются в силе."
)

doc.save("RFC-0002-LLM-Verification.docx")
print("saved RFC-0002-LLM-Verification.docx")
