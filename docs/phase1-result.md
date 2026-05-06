# Phase 1 Result — Backend (db.py)

**Status:** ✅ completo  
**Arquivo modificado:** `src/db.py`  
**Data:** 2026-05-05

## Changes applied

### 1. `slugify(label) → str`
- Pure function using `unicodedata.normalize("NFKD", …)` + regex
- Strips accents, lowercases, replaces non-alphanumeric with underscore
- Returns `"modalidade"` if result empty
- Added `import re`, `import unicodedata` to top of file

### 2. `_MODALITY_SEED` reduzido de 11 → 5
- Ordem: angiotomografia, radiografia, ressonancia_magnetica, tc_geral, tc_abdome_total
- Cores hardcoded (não dependem mais de MODALITY_COLORS lookup no seed)

### 3. `_seed_modalities()` atualizado
- Insere com valores de produção (price, exams_per_hour, active=1) do `_PRODUCTION_DEFAULTS`
- Só roda quando a tabela está vazia (idempotente)

### 4. `add_modality(conn, slug, label, price, exams_per_hour, active, color) → bool`
- Verifica duplicata de slug → retorna False
- Calcula `sort_order = MAX(sort_order) + 1`
- INSERT em transação
- Retorna True no sucesso

### 5. `delete_modality(conn, slug) → bool`
- DELETE FROM daily_production_items WHERE modality_slug = :slug **primeiro**
- DELETE FROM modalities WHERE slug = :slug **depois**
- Tudo em uma transação
- Retorna False se slug não existia

### 6. `save_modality()` aceita `label` opcional
- Nova assinatura: `save_modality(conn, slug, price, exams_per_hour, active, label=None, color=None)`
- `label=None` (default) → não altera a coluna label
- `color=None` (default) → não altera a coluna color
- Backward compat — callers existentes não quebram

### 7. `_migrate_v1_3_to_v1_4_defaults(conn)`
- Atualiza as 5 modalidades padrão com valores de produção
- **Só age** em linhas com `price = 0 AND active = 0` (preserva configs do usuário)
- Idempotente

### 8. `init_db()` — ordem corrigida
- `_add_color_column(conn)` **antes** de `_seed_modalities(conn)` para evitar erro de coluna inexistente
- `_migrate_v1_3_to_v1_4_defaults(conn)` chamado após seed

### 9. `load_all_modalities()` — docstring corrigida
- Removida menção a "Always 11 rows"

## Test results

```
26 passed, 11 failed
```

### 11 failures esperados (serão corrigidos na Fase 2)

| Teste | Razão |
|-------|-------|
| `test_init_db_seeds_modalities` | `assert 11` → agora 5 |
| `test_returns_11_ordered` | `assert 11` → agora 5 |
| `test_empty_when_none_active` | espera 0 ativas → agora 5 |
| `test_returns_activated_modalities` | espera 1 ativa → agora 5 |
| `test_excludes_zero_price_or_eph` | espera 0 → agora 4 |
| `test_deactivate` | usa slug inexistente (`densitometria`) |
| `test_returns_active_modality_prices` | `tc_geral` esperado 25.0 → agora 30.0 |
| `test_fallback_to_defaults_when_no_active` | `tc_geral` esperado 25.0 → agora 30.0 |
| `test_v1_to_v2_migrates_data` | seed agora ativa 5 mods antes da migration |
| `test_v1_to_v2_migrates_data_without_prices` | idem |
| `test_seed_modalities_has_color` | `assert 11` → agora 5 |

### 26 testes passando (sem regressão)

Todas as funções não afetadas continuam funcionando: CRUD de daily_production_items, goals, settings, v1 legacy, color handling.

## Verificação da migration

Simulação: DB existente com 5 mods (price=0, active=0) + tc_geral configurado pelo usuário (price=50, active=1).

```
BEFORE:  angio=0.0/0  rx=0.0/0  rm=0.0/0  tc_abdome=0.0/0  tc_geral=50.0/1
AFTER:   angio=30.0/1 rx=4.0/1  rm=35.0/1 tc_abdome=60.0/1 tc_geral=50.0/1  ← preservado!
```

## Próximo passo

**Fase 2:** Atualizar `tests/test_db.py` para refletir o novo seed de 5 modalidades com valores de produção.
