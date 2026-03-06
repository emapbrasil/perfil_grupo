# Análise EMAP — Automação com GitHub Actions

Este projeto lê respostas de um Google Forms (via Google Sheets), gera gráficos de análise, produz um resumo em cards visuais, gera uma análise textual automática com IA e publica tudo via GitHub Pages — sem nenhuma interação manual.

---

## Como funciona

```
GitHub Actions (toda segunda-feira às 8h BRT)
       │
       ▼
  analise.py
       │
       ├─ Lê dados ──────────► Google Sheets
       │
       ├─ Gera gráficos (PNG)
       │    ├─ Distribuição por gênero
       │    ├─ Febre reumática
       │    ├─ Benzetacil
       │    ├─ IMC
       │    ├─ Faixa etária dos sintomas
       │    ├─ Sintomas visuais
       │    ├─ Ascendência
       │    ├─ Distribuição por estado (barras + mapa)
       │    ├─ Tabagismo, estresse, cirurgia (Likert)
       │    ├─ COVID-19
       │    └─ Cards de resumo
       │
       ├─ Gera análise textual ──► Groq (Llama 3.3 70B) ──► analise.md
       │
       └─ Commit + push ──► GitHub Pages (URLs estáticas)
```

---

## Pré-requisitos

1. Conta Google com acesso à planilha.
2. Repositório no GitHub com GitHub Pages ativado.
3. Uma **Service Account** no Google Cloud.
4. Uma chave de API do **Groq** (gratuita e permanente).

---

## Configuração passo a passo

### 1. Criar uma Service Account no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto (ou use um existente)
3. Ative a API: **Google Sheets API**
4. Vá em **IAM e administrador → Contas de serviço → Criar conta de serviço**
5. Dê um nome e clique em **Concluído**
6. Clique na conta criada → **Chaves → Adicionar chave → JSON**
7. Salve o arquivo `.json` gerado

### 2. Compartilhar a planilha com a Service Account

O e-mail da Service Account tem o formato:
```
nome@projeto.iam.gserviceaccount.com
```

Na planilha Google Sheets: clique em **Compartilhar** → adicione o e-mail com permissão de **Leitor**.

### 3. Criar chave de API do Groq

1. Acesse [console.groq.com](https://console.groq.com) e crie uma conta (gratuita, sem cartão)
2. Vá em **API Keys → Create API Key**
3. Copie a chave gerada

### 4. Configurar os Secrets no GitHub

No repositório GitHub, vá em **Settings → Secrets and variables → Actions**:

| Nome | Valor |
|------|-------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Conteúdo completo do arquivo `.json` da Service Account |
| `SPREADSHEET_ID` | ID da planilha (parte da URL: `docs.google.com/spreadsheets/d/**ID**/edit`) |
| `GROQ_API_KEY` | Chave de API do Groq |

Opcionalmente, em **Variables**:

| Nome | Valor padrão |
|------|-------------|
| `WORKSHEET_NAME` | `Coleta` (nome da aba da planilha) |

### 5. Ativar o GitHub Pages

1. No repositório, vá em **Settings → Pages**
2. Em **Source**, selecione **Deploy from a branch**
3. Branch: `main` / pasta: `/ (root)` → **Save**

Após a primeira execução, os arquivos estarão disponíveis em:
```
https://emapbrasil.github.io/perfil_grupo/graficos/cards_resumo.png
https://emapbrasil.github.io/perfil_grupo/analise.md
```

### 6. Ajustar o agendamento (opcional)

No arquivo `.github/workflows/agendamento.yml`:
```yaml
- cron: "0 11 * * 1"   # toda segunda-feira às 8h BRT (11h UTC)
```

Referência: [crontab.guru](https://crontab.guru)

---

## Executar localmente

```bash
# Clonar o repositório
git clone https://github.com/emapbrasil/perfil_grupo.git
cd perfil_grupo

# Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis (Windows)
set GOOGLE_SERVICE_ACCOUNT_JSON=conteudo_do_json_aqui
set SPREADSHEET_ID=seu-id-aqui
set GROQ_API_KEY=sua-chave-aqui

# Rodar
python analise.py
```

> O arquivo `service_account.json` na raiz do projeto também é aceito para autenticação local (não commitar).

---

## Estrutura do projeto

```
perfil_grupo/
├── .github/
│   └── workflows/
│       └── agendamento.yml        # Workflow do GitHub Actions
├── graficos/                      # PNGs gerados, servidos via GitHub Pages
│   ├── cards_resumo.png
│   ├── distrib_genero.png
│   ├── febre_reumatica.png
│   ├── tempo_benzetacil.png
│   ├── imc.png
│   ├── idade_primeiros_sintomas.png
│   ├── sintomas.png
│   ├── ascendencia.png
│   ├── distribuicao_uf_barras.png
│   ├── distribuicao_uf_mapa.png
│   ├── relacao_tabagismo.png
│   ├── relacao_estresse.png
│   ├── relacao_cirurgia.png
│   └── relacao_covid.png
├── analise.md                     # Análise textual gerada pelo Groq
├── analise.py                     # Script principal
├── requirements.txt               # Dependências Python
├── .gitignore
└── README.md
```

---

## Gráficos gerados (14 arquivos)

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `cards_resumo.png` | Cards | Principais indicadores em destaque |
| `distrib_genero.png` | Donut | Distribuição por gênero |
| `febre_reumatica.png` | Donut | Prevalência de febre reumática |
| `imc.png` | Donut | Distribuição de IMC |
| `relacao_tabagismo.png` | Pizza | Relação com tabagismo (Likert) |
| `relacao_estresse.png` | Pizza | Relação com estresse (Likert) |
| `relacao_cirurgia.png` | Pizza | Cirurgia antes dos sintomas (Likert) |
| `tempo_benzetacil.png` | Barras | Tempo de uso da Benzetacil |
| `idade_primeiros_sintomas.png` | Barras | Faixa etária na primeira manifestação |
| `sintomas.png` | Barras horizontais | Principais sintomas visuais |
| `ascendencia.png` | Barras horizontais | Origem étnica declarada |
| `distribuicao_uf_barras.png` | Barras horizontais | Distribuição por estado |
| `distribuicao_uf_mapa.png` | Mapa | Distribuição geográfica coroplética |
| `relacao_covid.png` | Barras horizontais | Relação dos sintomas com COVID-19 |

---

## Análise textual automática (Groq)

A cada execução, o script monta um resumo numérico dos dados e envia para o modelo **Llama 3.3 70B** via API do Groq, gerando o arquivo `analise.md` com três seções:

- **Dados Básicos** — perfil demográfico, distribuição geográfica e ascendência
- **Dados de Saúde** — IMC, febre reumática, Benzetacil, fatores de risco
- **Conclusão** — síntese dos achados mais relevantes

O Groq é **gratuito e permanente** — sem expiração de créditos ou necessidade de cartão de crédito para uso moderado semanal.

---

## Acessibilidade

Todos os gráficos foram configurados com fontes ampliadas para facilitar a leitura por pessoas com baixa visão. Os tamanhos são definidos por variáveis globais no topo do `analise.py` e podem ser ajustados centralmente:

```python
F_TITULO    = 28   # títulos principais
F_SUBTITULO = 22   # subtítulos
F_EIXO      = 20   # labels dos eixos
F_TICK      = 18   # valores nos ticks
F_ROTULO    = 20   # rótulos nas barras
F_PIZZA     = 22   # percentuais nas fatias
F_LEGENDA   = 18   # legendas
```

---

## Notas de segurança

- **Nunca** adicione o arquivo `.json` da Service Account ao repositório.
- O `.gitignore` inclui `*.json`.
- Os secrets do GitHub são criptografados e nunca aparecem nos logs.