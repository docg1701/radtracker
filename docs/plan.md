# Plano: Modalidades Dinâmicas + LLM Configurável

**Data:** 2026-05-02
**Escopo:** Substituir 3 modalidades hardcoded (RM/TC/RX) por 11 dinâmicas + permitir escolha do modelo OpenRouter via slug.

---

## 1. Schema do Banco (migração v1 → v2)

### Novas tabelas

**`modalities`** — catálogo de modalidades:
```sql
CREATE TABLE IF NOT EXISTS modalities (
    slug            TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    price           REAL NOT NULL DEFAULT 0.0,
    exams_per_hour  REAL NOT NULL DEFAULT 0.0,
    active          INTEGER NOT NULL DEFAULT 0,  -- 0=inativo, 1=ativo
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

**`daily_production_items`** — produção normalizada:
```sql
CREATE TABLE IF NOT EXISTS daily_production_items (
    date            TEXT NOT NULL,
    modality_slug   TEXT NOT NULL,
    count           INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (date, modality_slug),
    FOREIGN KEY (modality_slug) REFERENCES modalities(slug)
);
```

**Nova setting:** `llm_model` em `user_settings` (default: `"openai/gpt-oss-120b:free"`)

### Seed inicial (11 modalidades, todas inativas com price=0)

| slug | label | sort_order |
|------|-------|------------|
| tc_abdome_total | TC de Abdome Total | 1 |
| tc_geral | TC Geral | 2 |
| angiotomografia | Angiotomografia | 3 |
| ressonancia_magnetica | Ressonância Magnética | 4 |
| ultrassonografia | Ultrassonografia | 5 |
| dopplervelocimetria | Dopplervelocimetria | 6 |
| mamografia | Mamografia | 7 |
| radiografia | Radiografia | 8 |
| radiografia_contrastada | Radiografia Contrastada | 9 |
| ultrassom_morfologico | Ultrassom Morfológico | 10 |
| densitometria | Densitometria | 11 |

### Migração de dados v1

- Se `daily_production` tem dados e `daily_production_items` está vazio:
  - RM → `ressonancia_magnetica`
  - TC → `tc_geral`
  - RX → `radiografia`
- Copiar preços do `exam_prices` mais recente para as 3 modalidades migradas
- Marcar as 3 como `active=1`

---

## 2. Arquivos a modificar (ordem de dependência)

### Fase 1 — Fundação (DB + Cores)
1. **`src/chart_colors.py`** — 3 → 13 cores (11 modalidades + primary + muted)
2. **`src/db.py`** — novas tabelas, seed, migração, CRUD para `modalities` e `daily_production_items`

### Fase 2 — Lógica de negócio
3. **`src/calculations.py`** — funções genéricas aceitando lista de modalidades
4. **`src/formatting.py`** — sem mudanças (já é genérico)
5. **`src/llm_client.py`** — `model` vindo de `st.session_state.llm_model` em vez de constante

### Fase 3 — Charts
6. **`src/charts.py`** — donut/sparkline/gauge dinâmicos
7. **`src/charts_analysis.py`** — MA/WoW/mix/bar dinâmicos
8. **`src/insights_rules.py`** — análise dinâmica por modalidade

### Fase 4 — UI
9. **`src/ui/settings.py`** — config de modalidades (preço + exams/hora) + campo slug LLM
10. **`src/ui/sidebar.py`** — inputs dinâmicos baseados em modalidades ativas
11. **`src/ui/today.py`** — KPIs dinâmicos
12. **`src/ui/month.py`** — visão mensal dinâmica
13. **`src/ui/analysis.py`** — análise dinâmica

### Fase 5 — Testes
14. **`tests/conftest.py`** — novas fixtures
15. **`tests/test_db.py`** — testes para modalities + daily_production_items
16. **`tests/test_calculations.py`** — atualizar para API dinâmica
17. **Demais tests** — atualizar conforme necessário

---

## 3. Regra de visibilidade

Uma modalidade aparece na **sidebar** e nos **dashboards** se e somente se:
- `active = 1` E
- `price > 0` E
- `exams_per_hour > 0`

Na aba **Configuração**, TODAS as 11 modalidades sempre aparecem (para configurar).

---

## 4. LLM Model

- Novo campo na aba Configuração: `"Modelo OpenRouter"` (text input)
- Placeholder: `openai/gpt-oss-120b:free`
- Salvo em `user_settings` com key `llm_model`
- `LLMClient` usa `st.session_state.llm_model` em vez da constante `_MODEL`

---

## 5. Validação

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run mypy src/
```
