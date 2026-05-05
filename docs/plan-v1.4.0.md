# plan-v1.4.0.md — Modalidades totalmente configuráveis

**Status:** aprovado — correções aplicadas  
**Release alvo:** v1.4.0  
**Base:** v1.3.0  
**Review:** issues resolvidos (save_modality com label, delete_modality com transação explícita, migration para bancos existentes, backward compat de cores e testes)

---

## Objetivo

Tornar as modalidades 100% configuráveis pelo usuário: nome editável, adicionar novas,
remover existentes. Substituir o seed fixo de 11 modalidades por 5 padrões com valores
reais do ambiente de produção.

---

## Escopo

### O que entra

| # | Funcionalidade | Descrição |
|---|---------------|-----------|
| 1 | Label editável | Campo de texto no grid de modalidades (hoje `st.write` estático) |
| 2 | Adicionar modalidade | Botão "+" ao fim da grid → nova linha com defaults |
| 3 | Remover modalidade | Botão 🗑️ por linha com confirmação inline |
| 4 | Slug automático | Gerado do label (slugify minúsculo, underscore, sem acentos) |
| 5 | Novo seed padrão | 5 modalidades: angiotomografia, radiografia, ressonancia_magnetica, tc_geral, tc_abdome_total |
| 6 | Valores padrão do seed | Preços e exames/h conforme servidor de produção (10.10.10.209) |

### O que NÃO entra (→ v1.5.0)

- Chat com IA / RAG
- Histórico de conversa
- Streaming de respostas
- Interface de chat interativa

---

## Arquivos afetados

| Arquivo | Mudança |
|---------|---------|
| `src/db.py` | Novo seed (5 mods), `add_modality()`, `delete_modality()`, `slugify()` |
| `src/ui/settings.py` | Grid: label → `st.text_input`, botões add/remove, UX de confirmação |
| `tests/test_db.py` | Testes para `add_modality`, `delete_modality`, `slugify` |
| `tests/test_settings.py` | Testes de UI para adicionar/remover/renomear (se viável) |
| `src/chart_colors.py` | NÃO remover cores — manter paleta de 11 para backward compat; seed encolhe, cores ficam |

### Arquivos NÃO afetados

- `app.py` — sem mudanças
- `src/calculations.py` — já é dinâmico
- `src/charts.py` e `src/charts_analysis.py` — já aceitam `modalities` como parâmetro
- `src/formatting.py` — sem mudanças
- `src/insights_rules.py` — já é dinâmico
- `src/llm_client.py` — sem mudanças
- `src/ui/sidebar.py`, `src/ui/today.py`, `src/ui/month.py` — já dinâmicos

---

## Design detalhado

### 1. Seed padrão (v1.4.0)

Substituir `_MODALITY_SEED` de 11 para 5 entradas:

```python
_MODALITY_SEED: list[dict[str, Any]] = [
    {"slug": "angiotomografia",         "label": "Angiotomografia",       "sort_order": 1, "color": "#0D9488"},
    {"slug": "radiografia",             "label": "Radiografia",           "sort_order": 2, "color": "#2563EB"},
    {"slug": "ressonancia_magnetica",   "label": "Ressonância Magnética", "sort_order": 3, "color": "#7C3AED"},
    {"slug": "tc_geral",                "label": "TC Geral",              "sort_order": 4, "color": "#6366F1"},
    {"slug": "tc_abdome_total",         "label": "TC de Abdome Total",    "sort_order": 5, "color": "#0891B2"},
]
```

Valores padrão (inseridos via `_seed_modalities` com price=0.0, active=0, mas
ativados com valores de produção por migration ou seed inicial):

| slug | price | exams_per_hour | active |
|------|-------|---------------|--------|
| angiotomografia | 30.00 | 4.0 | 1 |
| radiografia | 4.00 | 80.0 | 1 |
| ressonancia_magnetica | 35.00 | 8.0 | 1 |
| tc_geral | 30.00 | 10.0 | 1 |
| tc_abdome_total | 60.00 | 5.0 | 1 |

### 2. slugify() helper

```python
import re
import unicodedata

def slugify(label: str) -> str:
    """Converter 'Ressonância Magnética' → 'ressonancia_magnetica'."""
    value = unicodedata.normalize("NFKD", label.lower()).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "modalidade"
```

### 3. save_modality() atualizado — aceitar label

Assinatura atual (db.py:143): `save_modality(conn, slug, price, exams_per_hour, active, color=None)`

Nova assinatura:
```python
def save_modality(
    conn, slug, price, exams_per_hour, active,
    label=None, color=None,
):
    """Update modality fields. label e color são opcionais (None = não altera)."""
```

Quando `label` for fornecido, adiciona `label = :label` ao SET da query.

### 4. add_modality() — db.py

```python
def add_modality(conn, slug, label, price, exams_per_hour, active, color="#64748B"):
    """INSERT nova modalidade. Gera sort_order como MAX+1.

    Retorna True se inseriu, False se slug já existe.
    """
    # 1. Verifica se slug existe (SELECT COUNT(*))
    # 2. Se existir, retorna False
    # 3. Calcula sort_order = MAX(sort_order) + 1
    # 4. INSERT com os campos fornecidos
```

### 5. delete_modality() — db.py

```python
def delete_modality(conn, slug):
    """DELETE modality + seus daily_production_items.

    ATENÇÃO: O schema NÃO tem ON DELETE CASCADE e o SQLite NÃO
    habilita PRAGMA foreign_keys por padrão. Portanto:
    1. Primeiro: DELETE FROM daily_production_items WHERE modality_slug = :slug
    2. Depois:  DELETE FROM modalities WHERE slug = :slug
    3. Tudo em uma transação explícita

    Retorna True se deletou, False se slug não existia.
    """
```

### 6. Estratégia de migração para bancos existentes

**Problema:** Usuários que fazem upgrade da v1.3.0 → v1.4.0 têm 11 modalidades com
`price=0, active=0`. O seed NÃO roda em tabelas com dados. Eles precisam receber
os 5 defaults de produção automaticamente.

**Solução: migration `_migrate_v1_3_to_v1_4_defaults()`**

```python
def _migrate_v1_3_to_v1_4_defaults(conn) -> None:
    """One-shot: atualiza as 5 modalidades padrão para valores de produção.

    Só age sobre modalidades que já existem com price=0 e active=0.
    Modalidades que o usuário já configurou (price>0 ou active=1) são preservadas.
    As 6 modalidades extras (ultrassonografia, mamografia, etc.) permanecem inalteradas.
    """
    _PRODUCTION_DEFAULTS = {
        "angiotomografia":       ("Angiotomografia",       30.00, 4.0),
        "radiografia":           ("Radiografia",            4.00, 80.0),
        "ressonancia_magnetica": ("Ressonância Magnética", 35.00, 8.0),
        "tc_geral":              ("TC Geral",              30.00, 10.0),
        "tc_abdome_total":       ("TC de Abdome Total",    60.00, 5.0),
    }
    for slug, (label, price, eph) in _PRODUCTION_DEFAULTS.items():
        # UPDATE somente se price=0 e active=0 (não configurado pelo usuário)
        # Define label, price, exams_per_hour, active=1
```

A migration é chamada em `init_db()` logo após `_seed_modalities()` e antes de
`_migrate_v1_to_v2()`. É idempotente: só altera linhas com `price=0 AND active=0`.

### 7. Grid de modalidades — settings.py

Mudanças no `_render_modality_grid()`:

- **Label:** trocar `st.write(label)` por `st.text_input(f"Nome {slug}", value=label, key=f"mod_label_{slug}", label_visibility="collapsed")`
- **Botão +:** `st.button("➕ Adicionar modalidade")` no fim da grid → callback que adiciona linha temporária ao session_state
- **Botão 🗑️:** `st.button("🗑️", key=f"mod_del_{slug}")` por linha → callback com `st.warning` de confirmação inline
- **Linha nova:** após clicar "+", aparece uma linha extra com campos vazios + botão "Salvar" e "Cancelar"
- **Slug automático:** ao digitar o label da nova modalidade, o slug é gerado automaticamente
- **Caption:** cada linha mostra `Slug: {slug}` abaixo do label para deixar claro que o slug é imutável

### 8. Fluxo de adição

```
Usuário clica "+" 
  → session_state.new_modality_pending = True
  → Aparece linha no fim da grid: [text_input label] [number_input preço] [number_input eph] [color_picker] [Salvar] [Cancelar]
  → Ao digitar label, slug é gerado automaticamente (mostrado abaixo como caption)
  → Salvar: add_modality(conn, slug, label, price, eph, active=1, color)
  → Cancelar: session_state.new_modality_pending = False
  → Recarregar all_modalities e active_modalities no session_state
```

### 9. Fluxo de remoção

```
Usuário clica 🗑️ em uma linha
  → session_state.confirm_delete_slug = "tc_abdome_total"
  → Aparece st.warning inline naquela linha: "Remover TC de Abdome Total? Dados de produção serão perdidos."
  → [Confirmar] [Cancelar]
  → Confirmar: delete_modality(conn, slug)
  → Cancelar: session_state.confirm_delete_slug = None
  → Recarregar all_modalities e active_modalities
```

---

## Plano de implementação (ordem)

### Fase 1: Backend (db.py)
- [ ] `slugify()` — função pura, zero dependências
- [ ] `add_modality(conn, slug, label, price, exams_per_hour, active, color)`
- [ ] `delete_modality(conn, slug)` — com cascade nos daily_production_items
- [ ] Atualizar `_MODALITY_SEED` para 5 modalidades com valores de produção
- [ ] Atualizar `_seed_modalities()` para incluir price + eph + active=1 no seed inicial
- [ ] `_migrate_v1_3_to_v1_4_defaults()` — migration para bancos existentes

### Fase 2: Testes (tests/test_db.py)
- [ ] `test_slugify_basic` — acentos, espaços, pontuação
- [ ] `test_slugify_edge_cases` — vazio, só símbolos
- [ ] `test_add_modality_success`
- [ ] `test_add_modality_duplicate_slug`
- [ ] `test_delete_modality_success`
- [ ] `test_delete_modality_cascades_to_daily_items`
- [ ] `test_delete_nonexistent_modality`
- [ ] `test_seed_has_five_modalities` (atualizar `test_init_db_seeds_modalities` e `test_returns_11_ordered` → `test_returns_5_ordered`)
- [ ] `test_seed_values_match_production`
- [ ] `test_save_modality_with_label` — label é persistido
- [ ] `test_rename_modality_label` — slug permanece, label muda
- [ ] `test_delete_modality_cascades_to_daily_items` — items removidos antes da modality
- [ ] `test_migration_v1_3_to_v1_4_applies_defaults` — DB com 11 mods price=0 recebe defaults
- [ ] `test_migration_v1_3_to_v1_4_preserves_user_config` — mods já configurados não são sobrescritos
- [ ] `test_init_db_idempotent_on_existing_db` — DB com 11 mods não é alterado pelo seed
- [ ] `test_chart_colors_retains_all_11_colors` — MODALITY_COLORS ainda tem 11 entradas (backward compat)

### Fase 3: Frontend (settings.py)
- [ ] Campo label editável (text_input em vez de st.write)
- [ ] Botão "➕ Adicionar modalidade"
- [ ] Linha de nova modalidade com slug automático
- [ ] Botão 🗑️ por linha com confirmação inline
- [ ] Salvar modalidade também salva label (slugs existentes) + preço + eph + cor
- [ ] Salvar nova modalidade chama `add_modality()`

### Fase 4: Integração e testes manuais
- [ ] `uv run streamlit run app.py` — verificar grid completo
- [ ] Adicionar "Tomografia de Crânio" → deve aparecer na sidebar
- [ ] Remover "TC de Abdome Total" → deve sumir da sidebar
- [ ] Renomear "TC Geral" para "Tomografia Geral" → label muda, slug permanece
- [ ] Verificar que dados de produção não foram perdidos

### Fase 5: Qualidade
- [ ] `uv run ruff check src/ tests/` — zero erros
- [ ] `uv run mypy src/` — zero erros (ou existentes)
- [ ] `uv run pytest tests/ -v` — todos passando
- [ ] Atualizar `pyproject.toml` version → "1.4.0"

---

## Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Slugs duplicados ao adicionar | `add_modality` verifica UNIQUE constraint, retorna False (exibe `st.warning` no grid) |
| Remover modalidade com dados órfãos | `delete_modality` faz DELETE em `daily_production_items` ANTES da modality, em transação |
| Upgrade: 11→5 seed não aplica defaults | `_migrate_v1_3_to_v1_4_defaults()` atualiza as 5 mods com price=0, preservando configs do usuário |
| Slug gerado colide com slug existente | `add_modality` retorna False; `st.warning` sugere nome diferente |
| Usuário renomeia label mas espera mudar slug | Label é display; slug é chave primária imutável. Caption no grid: "Slug: {slug}" |
| Testes existentes quebram (assert 11 mods) | Atualizar `test_db.py` e `test_chart_colors.py`; `MODALITY_COLORS` mantém 11 cores |
| Fragment state frágil (confirm_delete dentro de loop) | Usar chaves únicas: `f"confirm_del_{slug}"`, `f"cancel_del_{slug}"` |
| `st.text_input` dentro de fragment gera rerun parcial | Widgets com `key=` fixo preservam valor; testar fluxo add inline |

---

## Constantes e convenções

- Slug: minúsculo, ASCII, underscore como separador, max ~64 chars (SQLite TEXT)
- Label: livre, exibido com capitalize apropriado
- Cor default para novas modalidades: `#64748B` (Slate-500)
- Preço default: 0.00 (força usuário a configurar)
- Exames/h default: 0.0 (força usuário a configurar)
- Active default: 1 (ativada ao criar)
- Sort order: auto-increment (MAX+1)
