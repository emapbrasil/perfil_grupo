# Análise EMAP — Automação com GitHub Actions

Este projeto lê respostas de um Google Forms (via Google Sheets), gera gráficos de análise e faz upload automático das imagens para uma pasta no Google Drive — sem nenhuma interação manual.

---

## Como funciona

```
GitHub Actions (agendado)
       │
       ▼
  analise.py
       │
       ├─ Lê dados ──► Google Sheets
       │
       ├─ Gera gráficos (PNG)
       │
       └─ Faz upload ──► Google Drive (pasta configurada)
```

---

## Pré-requisitos

1. Conta Google com acesso à planilha e ao Google Drive.
2. Repositório no GitHub.
3. Uma **Service Account** no Google Cloud (veja abaixo).

---

## Configuração passo a passo

### 1. Criar uma Service Account no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto (ou use um existente)
3. Ative as APIs:
   - **Google Sheets API**
   - **Google Drive API**
4. Vá em **IAM e administrador → Contas de serviço → Criar conta de serviço**
5. Dê um nome e clique em **Concluído**
6. Clique na conta criada → **Chaves → Adicionar chave → JSON**
7. Salve o arquivo `.json` gerado (você usará o conteúdo dele no GitHub)

### 2. Compartilhar a planilha e a pasta com a Service Account

O e-mail da Service Account tem o formato:
```
nome@projeto.iam.gserviceaccount.com
```

- **Planilha Google Sheets**: clique em "Compartilhar" → adicione o e-mail com permissão de **Leitor**
- **Pasta no Google Drive**: clique com botão direito → "Compartilhar" → adicione o e-mail com permissão de **Editor**

### 3. Configurar os Secrets no GitHub

No repositório GitHub, vá em **Settings → Secrets and variables → Actions**:

| Nome | Valor |
|------|-------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Cole o conteúdo **completo** do arquivo `.json` da Service Account |
| `SPREADSHEET_ID` | ID da planilha (parte da URL: `docs.google.com/spreadsheets/d/**ID**/edit`) |
| `DRIVE_FOLDER_ID` | ID da pasta no Drive (parte da URL ao abrir a pasta: `drive.google.com/drive/folders/**ID**`) |

Opcionalmente, em **Variables** (não Secrets):

| Nome | Valor padrão |
|------|-------------|
| `WORKSHEET_NAME` | `Coleta` (nome da aba da planilha) |

### 4. Ajustar o agendamento (opcional)

No arquivo `.github/workflows/agendamento.yml`, a linha:
```yaml
- cron: "0 11 * * 1"
```
Significa: **toda segunda-feira às 8h (Brasília)**. O cron usa UTC, então `11h UTC = 8h BRT`.

Para rodar toda semana na sexta às 18h BRT (21h UTC):
```yaml
- cron: "0 21 * * 5"
```

Referência: [crontab.guru](https://crontab.guru)

---

## Executar localmente

```bash
# Clonar o repositório
git clone https://github.com/seu-usuario/emap-analise.git
cd emap-analise

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Exportar variáveis de ambiente
export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... conteúdo do JSON ... }'
export SPREADSHEET_ID='seu-id-aqui'
export DRIVE_FOLDER_ID='seu-id-aqui'

# Rodar
python analise.py
```

---

## Estrutura do projeto

```
emap-analise/
├── .github/
│   └── workflows/
│       └── agendamento.yml   # Workflow do GitHub Actions
├── graficos/                 # PNGs gerados (ignorados pelo git)
├── analise.py                # Script principal
├── requirements.txt          # Dependências Python
└── README.md
```

---

## Gráficos gerados

| Arquivo | Descrição |
|---------|-----------|
| `distrib_genero.png` | Distribuição por gênero |
| `febre_reumatica.png` | Prevalência de febre reumática |
| `tempo_benzetacil.png` | Tempo de uso da Benzetacil |
| `imc.png` | Distribuição de IMC |
| `faixa_etaria_sintomas.png` | Idade na primeira manifestação |
| `relacao_estresse.png` | Relação com estresse intenso |
| `relacao_covid.png` | Relação com COVID-19 |

---

## Notas de segurança

- **Nunca** adicione o arquivo `.json` da Service Account ao repositório.
- O `.gitignore` deve incluir `*.json` e `graficos/`.
- O conteúdo do JSON fica protegido nos Secrets do GitHub (criptografado).
