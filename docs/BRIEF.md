# Brief — radtracker

**Projeto**: Dashboard pessoal de produtividade para telerradiologia
**Usuário**: Galvani, médico radiologista, 100% home office
**Status**: Planejamento concluído. Implementação pendente.
**Data do brief**: 2026-04-29

---

## 1. Problema

Galvani trabalha por telerradiologia laudando exames de **RM** (ressonância), **TC** (tomografia) e **RX** (raio-X). Ele ganha por exame laudado, e a média de pagamento não é alta — para fazer dinheiro, precisa trabalhar rápido e em alto volume.

Nos últimos anos, a previsibilidade do faturamento mensal piorou. Galvani não consegue enxergar com clareza:
- Se está no ritmo certo para bater a meta mensal
- Quantos exames/horas faltam por dia para atingi-la
- Quais modalidades estão puxando ou freando o faturamento
- Tendências de curto e longo prazo na sua produtividade

Sem esses dados, o planejamento financeiro é no escuro.

## 2. Solução Proposta

Um **dashboard local** (roda no computador de casa, offline-first) onde Galvani registra, ao longo do dia, quantos exames de cada tipo laudou. O sistema:

- Calcula instantaneamente o faturamento do dia e o acumulado do mês
- Projeta se a meta mensal será batida no ritmo atual
- Informa quantos exames/dia e horas/dia são necessários para vencer a meta
- Compara o desempenho com semanas e meses anteriores
- Gera insights acionáveis em português (ex: _"Foque mais em RM — está 15% abaixo da sua média"_)
- Opcionalmente usa um LLM (DeepSeek V4 Flash, via Ollama Cloud) para análises mais profundas

## 3. Requisitos

### 3.1 Funcionais

- Entrada de dados: RM, TC, RX (3 números inteiros) para uma data — várias vezes ao dia (UPSERT)
- Cálculos em tempo real: faturamento, projeções, médias móveis, % da meta
- Visualização: gráficos de linha, barra, pizza, tendências
- Insights textuais: regras + LLM opcional
- Configuração de preços por exame e meta mensal
- Modo claro/escuro

### 3.2 Não-funcionais

- **Local only**: tudo roda em `localhost`, dados no SQLite local
- **100% open-source**: stack MIT/BSD/Apache — sem taxas, sem APIs pagas obrigatórias
- **Privacidade total**: dados nunca saem do computador (exceto se LLM for usado via API)
- **Simplicidade**: execução com um comando (`streamlit run app.py`)
- **Único usuário**: sem autenticação, sem multi-tenant

### 3.3 Regras de Negócio

| Modalidade | Pagamento por exame | Produtividade (exames/hora) |
|---|---|---|
| RM (Ressonância) | R$ 35,00 | 5–10/h |
| TC (Tomografia) | R$ 25,00 | 5–10/h |
| RX (Raio-X) | R$ 4,50 | 50–100/h |

- **Meta mensal inicial**: R$ 45.000
- **Dias de trabalho**: Segunda a Sábado
- **Horas ideais/dia**: 4–6h

## 4. Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Interface | **Streamlit 1.54** | Dashboard em Python puro, zero HTML/CSS/JS |
| Gráficos | **Plotly Express** | Interativo, integração nativa com Streamlit |
| Cálculos | **Pandas + NumPy** | Séries temporais, médias móveis, projeções |
| Banco | **SQLite** (built-in) | Arquivo único, zero configuração, UPSERT |
| LLM (opcional) | **Ollama Cloud** (`deepseek-v4-flash:cloud`) | Plano Free suficiente; fallback para regras |
| Tema | `.streamlit/config.toml` | Claro (default) + escuro |

## 5. Estrutura do Projeto

```
radtracker/
├── .streamlit/
│   └── config.toml
├── .env                        # OLLAMA_API_KEY (gitignored)
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── app.py                      # Entry point Streamlit
├── src/
│   ├── __init__.py
│   ├── db.py                   # SQLite schema, CRUD, UPSERT
│   ├── calculations.py         # Projeções, médias, estimativas
│   ├── insights_rules.py       # Regras de insight (sem LLM)
│   ├── llm_client.py           # Cliente Ollama Cloud
│   ├── chart_colors.py         # Paleta de cores padronizada
│   ├── charts.py               # Fábrica de gráficos Plotly
│   └── ui/
│       ├── __init__.py
│       ├── sidebar.py          # Entrada de dados
│       ├── today.py            # Aba "Hoje"
│       ├── month.py            # Aba "Mês Atual"
│       ├── analysis.py         # Aba "Análise & Insights"
│       └── settings.py         # Aba "Configurações"
├── data/                       # SQLite .db (gitignored)
└── tests/
    ├── conftest.py
    ├── test_calculations.py
    ├── test_db.py
    └── test_insights.py
```

## 6. Roadmap

| Fase | Entrega | Dias estimados |
|---|---|---|
| **1** | Estrutura do projeto, `pip install` deps, banco SQLite, CRUD, sidebar com entrada de dados | 2–3 |
| **2** | Aba "Hoje": cards KPI, barra de progresso, estimativa de horas, breakdown por modalidade | 1–2 |
| **3** | Aba "Mês Atual": progresso da meta, gráfico de faturamento diário, projeção, alertas de ritmo | 2–3 |
| **4** | Aba "Análise": médias móveis 7d/30d, comparações WoW/MoM, insights por regras | 2–3 |
| **5** | LLM (Ollama Cloud) + fallback, aba Configurações (preços, meta), temas claro/escuro | 1–2 |
| **6** | Testes, README, .gitignore, push para GitHub privado | 1–2 |

## 7. Design System (resumo)

Ver especificação completa em [`DESIGN_SPEC.md`](./DESIGN_SPEC.md).

- **Cor primária**: Teal `#0D9488` — moderno, remete a saúde sem ser hospital-blue
- **Modalidades**: RM = Azul `#2563EB` · TC = Âmbar `#D97706` · RX = Ciano `#0891B2` (testado para daltonismo)
- **Semânticas**: Success verde `#16A34A` · Warning amarelo `#CA8A04` · Danger vermelho `#DC2626`
- **Tom de voz**: Direto, em português, chama Galvani pelo nome. Ex: _"Galvani, você está 12% acima do ritmo para a meta de R$ 45.000."_
- **Estados**: Empty state (onboarding simples), loading (spinner), erro (fallback), sucesso (toast)

## 8. Arquivos de Referência

| Arquivo | Conteúdo |
|---|---|
| [`RESEARCH.md`](./RESEARCH.md) | Pesquisa técnica: documentação de Streamlit, Plotly, Pandas, SQLite, Ollama Cloud. Códigos de exemplo, schema SQL, estimativas de custo |
| [`DESIGN.md`](./DESIGN.md) | Design system do Cal.com (referência externa): cores, tipografia, componentes, espaçamento, responsividade |
| [`DESIGN_SPEC.md`](./DESIGN_SPEC.md) | Design system do radtracker: paleta de 24 cores, tipografia mapeada para Streamlit, 7 componentes com layout ASCII, 5 exemplos de insights, `config.toml` completo, estados e transições |
| [`BRIEF.md`](./BRIEF.md) | Este arquivo — visão geral e índice do projeto |

## 9. Contexto Pessoal

> _Nas palavras do próprio Galvani:_
>
> "Sou médico radiologista, trabalho 100% por telerradiologia de casa. Todos os dias eu laudo RM, TC e RX. Meu objetivo é trabalhar o mais eficiente possível, pois ganho por exame laudado e a média de pagamento não é boa. Consigo trabalhar muito rápido, logo consigo fazer dinheiro. Tenho percebido que a previsibilidade do meu faturamento mensal tem ficado cada vez pior e não estou conseguindo ganhar dinheiro suficiente para pagar as contas. A minha ideia é um aplicativo que monitora minha produção a partir de um input muito simples: ao final do dia, digo quantos exames de RM, TC e RX laudei. Esses valores geram uma projeção com todos os cálculos, estatísticas, dados e estimativas que eu preciso para entender quanto devo trabalhar nos próximos dias para atingir a meta mensal."

**Objetivo maior**: Galvani quer se dedicar a outros empreendimentos sem perder sua renda atual. Se conseguisse trabalhar 4 a 6 horas por dia (Seg a Sáb) e ainda bater a meta de R$ 45.000, seria o cenário ideal.

**Restrição explícita**: O projeto deve ser 100% open-source, sem hidden fees e sem "gotchas". É uma ferramenta pessoal, não um produto comercial.

## 10. Ambiente e Perfil do Usuário

| Característica | Detalhe |
|---|---|
| **Sistema operacional** | Linux (Ubuntu) |
| **Python** | 3.12.3 instalado, usa terminal com fluência |
| **Streamlit/Plotly/Pandas** | Não instalados — precisam ser adicionados via pip |
| **Ollama local** | Não usa, não quer rodar modelos locais |
| **Conta Ollama Cloud** | Possui conta, pode gerar API key |
| **LLM preferido** | DeepSeek V4 Flash (via Ollama Cloud ou API direta) |
| **Interface preferida** | Dashboard Streamlit no navegador |
| **Rotina de entrada** | Registra exames várias vezes ao dia (meio-dia, tarde, noite) — precisa poder editar a qualquer momento |
| **GitHub** | Repositório privado, mesmo nome do projeto |

## 11. Decisões de Arquitetura (com Porquês)

Cada decisão abaixo foi discutida e validada com Galvani. Se outro agente for implementar, **não altere estas escolhas sem consultar**.

| Decisão | Escolha | Por quê |
|---|---|---|
| **Framework UI** | Streamlit | Zero HTML/CSS/JS — Galvani quer simplicidade. Flask+React seria overkill para 1 usuário local. |
| **Banco de dados** | SQLite | Arquivo único, queries temporais nativas (WHERE date BETWEEN), UPSERT atômico, backup é copiar 1 arquivo. JSON seria frágil para edições múltiplas/dia. |
| **LLM** | Ollama Cloud Free → fallback DeepSeek API | Plano Free cobre uso leve (~30 análises/dia). Se estourar, API direta custa centavos. Sempre com fallback para regras — LLM é um "plus". |
| **Modelo LLM** | `deepseek-v4-flash:cloud` | 284B parâmetros, raciocínio forte, barato. Suficiente para análise de dados tabulares. |
| **Cor primária** | Teal #0D9488 | Sugestão do agente — moderno, remete a saúde sem ser o azul-hospital-genérico que toda ferramenta médica usa. Galvani aprovou. |
| **Modo de cor padrão** | Claro | Galvani trabalha de dia, ambiente iluminado. Modo escuro disponível como opção. |
| **Entrada de dados** | UPSERT por data | Galvani edita o mesmo dia várias vezes. O sistema sobrescreve (não duplica). |
| **Idioma da interface** | Português | Ferramenta pessoal de um brasileiro. Código-fonte em inglês (convenção). |
| **Estrutura de pastas** | `src/` com submódulos | Separação clara: db, cálculos, insights, UI. Cada arquivo <500 linhas. |
| **Gráficos** | Plotly Express + Graph Objects | Integração nativa com Streamlit via `st.plotly_chart`. Altair seria alternativa, Plotly é mais maduro. |

## 12. Fluxo de Uso Diário (UX)

```
1. Galvani abre o terminal, roda:  streamlit run app.py
2. Browser abre em http://localhost:8501
3. Vê o dashboard na aba "📊 Hoje":
   - Se for primeiro uso → empty state amigável
   - Se já tem dados hoje → KPIs calculados
4. Na sidebar, ajusta os números de RM, TC, RX (edita o que já existe ou digita do zero)
5. Clica "💾 Salvar produção"
6. Toast: "✅ Produção de 29/04 salva!"
7. Dashboard recarrega com novos cálculos
8. Navega entre abas para ver mês, tendências, insights
9. Fecha o navegador. Na próxima vez, dados estão lá.
```

**Comportamento esperado na edição**:
- Meio-dia: Galvani salva RM=5, TC=3, RX=20
- 16h: Edita para RM=8, TC=6, RX=35 (sobrescreve, não adiciona)
- 22h: Edita para RM=12, TC=9, RX=50 (valores finais do dia)
- Cada salvamento recalcula tudo instantaneamente

## 13. Definição de "Pronto"

O projeto estará completo quando Galvani puder:

- [x] Abrir o app com 1 comando no terminal
- [x] Registrar exames do dia em <10 segundos
- [x] Ver instantaneamente: faturamento do dia, % da meta mensal, horas estimadas, quantos exames/dia faltam
- [x] Ver gráficos de tendência (diário, semanal, mensal)
- [x] Ler insights em português que façam sentido para um radiologista
- [x] Ajustar preços e meta mensal sem mexer em código
- [x] Confiar que os dados estão seguros (SQLite local, backup fácil)
- [x] Alternar entre modo claro e escuro

## 14. Notas e Decisões

- **Nome**: "radtracker" — combina radiologia + tracker. Curto e descritivo.
- **Repositório**: GitHub privado, mesmo nome do projeto. A criar.
- **LLM é opcional**: se API key não existir ou chamada falhar, o app gera insights por regras. Sem dependência crítica.
- **Custo do LLM**: Ollama Cloud Free cobre o uso esperado (~10-50 chamadas/dia). Se estourar, API direta da DeepSeek custa centavos/mês.
- **Idioma**: Interface em português. Código e comentários em inglês (convenção open-source).
- **Sem migração complexa**: SQLite com `CREATE TABLE IF NOT EXISTS`. Schema simples, sem ORM.
