"""
Análise de Respostas EMAP - Script Principal
Lê dados do Google Sheets, gera gráficos e faz upload para o Google Drive.
Autenticação via Service Account (sem interação manual).
"""

import os
import re
import unicodedata
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # backend sem GUI, obrigatório para CI/headless
import matplotlib.pyplot as plt
import seaborn as sns

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import gspread

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# IDs configuráveis via variáveis de ambiente (definidas no GitHub Actions)
SPREADSHEET_ID   = os.environ["SPREADSHEET_ID"]       # ID da planilha Google Sheets
DRIVE_FOLDER_ID  = os.environ["DRIVE_FOLDER_ID"]       # ID da pasta no Google Drive
WORKSHEET_NAME   = os.getenv("WORKSHEET_NAME", "Coleta")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

OUTPUT_DIR = Path("graficos")
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Autenticação via Service Account
# ---------------------------------------------------------------------------

def get_google_clients():
    """
    Autentica usando o JSON da Service Account armazenado na variável de ambiente
    GOOGLE_SERVICE_ACCOUNT_JSON (conteúdo do arquivo JSON, não o caminho).
    """
    import json, tempfile

    sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    sa_info = json.loads(sa_json)

    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    drive_service = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)
    return gc, drive_service


# ---------------------------------------------------------------------------
# Carregamento dos dados
# ---------------------------------------------------------------------------

def carregar_dados(gc: gspread.Client) -> pd.DataFrame:
    log.info("Carregando dados da planilha: %s / aba: %s", SPREADSHEET_ID, WORKSHEET_NAME)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet   = spreadsheet.worksheet(WORKSHEET_NAME)
    data        = worksheet.get_all_values()
    df          = pd.DataFrame(data[1:], columns=data[0])
    log.info("Dados carregados: %d linhas", len(df))
    return df


# ---------------------------------------------------------------------------
# Tratamento dos dados
# ---------------------------------------------------------------------------

def tratar_dados(df: pd.DataFrame) -> pd.DataFrame:
    log.info("Iniciando tratamento dos dados...")

    # Renomear colunas
    novos_nomes = [
        "data_hora_resposta", "cod_identificador", "genero", "nasc_ano",
        "ascendencia", "escolaridade", "percep_sintomas_ano", "sintomas",
        "diagnostico_ano", "percep_sinatomas_peso", "altura",
        "percep_sintomas_profissao", "vacinas_antes", "covid_piora_sintomas",
        "covid_sintomas_antes_emap", "covid_piora_sintomas_vacina",
        "afirm_sintomas_surgiram_durante_ou_meses_apos_pandemia",
        "afirm_sintomas_surgiram_apos_vacina_covid",
        "afirm_ano_aparec_sintomas_fumava_intensamente",
        "afirm_ano_aparec_sintomas_exposicao_produtos_quimicos",
        "afirm_ano_aparec_sintomas_estresse_intenso",
        "afirm_ano_aparec_sintomas_exposicao_sol",
        "afirm_ano_aparec_sintomas_dieta_acucar_industrializados",
        "afirm_ano_aparec_sintomas_dieta_farinaceos_gluten",
        "afirm_ano_aparec_sintomas_dieta_laticinios",
        "afirm_ano_aparec_sintomas_bebidas_alcoolicas",
        "afirm_antes_aparec_sintomas_atividades_fisicas_baixo_impacto",
        "afirm_antes_aparec_sintomas_atividades_fisicas_alto_impacto",
        "afirm_ano_aparec_sintomas_hipertensao",
        "afirm_antes_aparec_sintomas_cirurgia",
        "problemas_saude_febre_reumatica", "problemas_saude_tomou_benzetacil",
        "problemas_saude_enxaqueca", "problemas_saude_diabetes",
        "problemas_saude_hipotireoidismo", "problemas_saude_hipertireoidismo",
        "problemas_saude_colesterol", "problemas_saude_triglicerideo",
        "problemas_saude_alergia", "problemas_saude_gordura_figado",
        "problemas_saude_cancer", "problemas_saude_hipertensao",
        "problemas_saude_doenca_cardiovascular",
        "problemas_saude_doenca_renal_cronica",
        "problemas_saude_doenca_inflamatoria",
        "problemas_saude_amigdalas_inflamadas",
        "problemas_saude_cirurgia_amigdalas",
        "problemas_saude_outra_doenca_oftalmologica",
        "febre_reumatica_idade_diagnostico", "febre_reumatica_sintomas",
        "benzetacil_anos_tratamento", "doencas_autoimunes",
        "doencas_inflamatorias", "doencas_oftalmologicas",
        "doencas_autoimunes_pais_irmaos",
        "doencas_autoimunes_pais_irmaos_descricao",
        "piora_sintomas_apos_cirurgia", "sintomas_juventude",
        "end", "uf", "doencas_inflamatorias_pais_irmaos",
    ]

    # Ajuste caso o número de colunas não bata exatamente
    df = df.iloc[:, : len(novos_nomes)]
    df.columns = novos_nomes[: len(df.columns)]

    df.drop(columns=["end"], inplace=True, errors="ignore")

    # Gênero
    df["genero"] = df["genero"].map({"Feminino": "F", "Masculino": "M"})

    # Idades
    ano_atual = datetime.today().year
    df["nasc_ano"]          = pd.to_numeric(df["nasc_ano"], errors="coerce")
    df["percep_sintomas_ano"] = pd.to_numeric(df["percep_sintomas_ano"], errors="coerce")
    df["idade_atual"]       = ano_atual - df["nasc_ano"]
    df["idade_sintomas"]    = df["percep_sintomas_ano"] - df["nasc_ano"]
    df["idade_sintomas"]    = df.loc[(df["idade_sintomas"] < 100) & (df["idade_sintomas"] > 0), "idade_sintomas"]

    # IMC
    df["percep_sinatomas_peso"] = pd.to_numeric(df["percep_sinatomas_peso"], errors="coerce")
    df["altur_m"]               = pd.to_numeric(df["altura"], errors="coerce") / 100
    df["percep_sintomas_imc"]   = df["percep_sinatomas_peso"] / df["altur_m"] ** 2
    df["classificacao_imc"]     = df["percep_sintomas_imc"].apply(_classificar_imc)

    # Febre reumática
    df["fl_teve_febre_reumatica"] = (
        df["febre_reumatica_idade_diagnostico"].notna() |
        df["febre_reumatica_sintomas"].notna()
    )

    # Benzetacil
    df["benzetacil_anos_tratamento"] = pd.to_numeric(df["benzetacil_anos_tratamento"], errors="coerce")

    log.info("Tratamento concluído. Total de respondentes: %d", len(df))
    return df


def _classificar_imc(imc):
    if pd.isna(imc):
        return np.nan
    if imc < 18.5:   return "Abaixo do peso"
    if imc < 24.9:   return "Peso normal"
    if imc < 29.9:   return "Sobrepeso"
    if imc < 34.9:   return "Obesidade grau 1"
    if imc < 39.9:   return "Obesidade grau 2"
    return "Obesidade grau 3"


# ---------------------------------------------------------------------------
# Helpers de gráfico / upload
# ---------------------------------------------------------------------------

def _salvar_e_upload(fig, nome_arquivo: str, drive_service, titulo_log: str):
    caminho = OUTPUT_DIR / nome_arquivo
    fig.savefig(caminho, dpi=300, bbox_inches="tight")
    plt.close(fig)
    log.info("Gráfico salvo: %s", caminho)

    file_metadata = {"name": nome_arquivo, "parents": [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(str(caminho), mimetype="image/png")
    resultado = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()
    log.info("Upload OK — %s | Drive ID: %s", titulo_log, resultado.get("id"))


# ---------------------------------------------------------------------------
# Geração dos gráficos
# ---------------------------------------------------------------------------

def grafico_genero(df: pd.DataFrame, drive_service):
    contagem = df["genero"].value_counts().reindex(["F", "M"])
    labels   = ["Feminino", "Masculino"]
    colors   = ["#FA9FBD", "#34C9A1"]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, _ = ax.pie(
        contagem, labels=None, autopct=None, startangle=90,
        colors=colors, wedgeprops=dict(width=0.6, edgecolor="white"),
    )
    for wedge, count in zip(wedges, contagem):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x   = 0.7 * np.cos(np.deg2rad(ang))
        y   = 0.7 * np.sin(np.deg2rad(ang))
        pct = count / contagem.sum() * 100
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                fontsize=20, color="black", weight="bold")

    fig.suptitle("Distribuição por Gênero", fontsize=18, x=0.0, y=0.98,
                 ha="left", va="top", fontweight="bold")
    legend_labels = [
        f"{l}: {c} ({c/contagem.sum()*100:.1f}%)" for l, c in zip(labels, contagem)
    ]
    ax.legend(wedges, legend_labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False, fontsize=13)
    ax.axis("equal")
    plt.tight_layout()
    _salvar_e_upload(fig, "distrib_genero.png", drive_service, "Distribuição por Gênero")


def grafico_febre_reumatica(df: pd.DataFrame, drive_service):
    contagem = df["fl_teve_febre_reumatica"].value_counts()
    labels   = ["Sim", "Não"]
    colors   = ["#71A7CE", "#E2803E"]

    fig, ax = plt.subplots(figsize=(8, 5))
    wedges, _ = ax.pie(
        contagem, labels=None, autopct=None, startangle=90,
        colors=colors, wedgeprops=dict(width=0.6, edgecolor="white"),
    )
    for wedge, count in zip(wedges, contagem):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x   = 0.6 * np.cos(np.deg2rad(ang))
        y   = 0.6 * np.sin(np.deg2rad(ang))
        pct = count / contagem.sum() * 100
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                fontsize=18, color="black", weight="bold")

    legend_labels = [
        f"{l}: {c} ({c/contagem.sum()*100:.1f}%)" for l, c in zip(labels, contagem)
    ]
    ax.legend(legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
              ncol=2, frameon=False)
    ax.axis("equal")
    plt.tight_layout(rect=[0, 0, 1, 0.85])
    fig.suptitle("Histórico de Febre Reumática", fontsize=18, x=0.01,
                 ha="left", fontweight="bold", y=0.98)
    fig.text(0.01, 0.90,
             "Prevalência de histórico de febre reumática entre os participantes",
             fontsize=14, ha="left")
    _salvar_e_upload(fig, "febre_reumatica.png", drive_service, "Febre Reumática")


def grafico_benzetacil(df: pd.DataFrame, drive_service):
    bins   = [0, 5, 10, 15, 20, 100]
    labels = ["menos de 5", "5-10", "10-15", "15-20", "mais de 20"]
    df["faixa_benzetacil"] = pd.cut(
        df["benzetacil_anos_tratamento"], bins=bins, labels=labels, right=False
    )
    contagem   = df["faixa_benzetacil"].value_counts().reindex(labels, fill_value=0)
    media_tempo = df["benzetacil_anos_tratamento"].mean()

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(x=contagem.index, y=contagem.values, color="#34C9A1", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Faixa de Tempo de Uso (anos)", fontsize=12)
    ax.set_ylabel("Número de Respondentes", fontsize=12)

    offset = contagem.max() * 0.03
    for i, count in enumerate(contagem.values):
        if count > 0:
            ax.text(i, count + offset, str(int(count)),
                    ha="center", va="bottom", fontsize=12)

    plt.tight_layout(rect=[0, 0, 1, 0.85])
    fig.suptitle("Tempo de Uso da Benzetacil", fontsize=18, x=0.01,
                 ha="left", fontweight="bold", y=0.98)
    fig.text(0.01, 0.90,
             f"Tempo médio de uso entre os participantes (média: {media_tempo:.1f} anos)",
             fontsize=14, ha="left")
    _salvar_e_upload(fig, "tempo_benzetacil.png", drive_service, "Benzetacil")


def grafico_imc(df: pd.DataFrame, drive_service):
    ordem = ["Abaixo do peso", "Peso normal", "Sobrepeso",
             "Obesidade grau 1", "Obesidade grau 2", "Obesidade grau 3"]
    contagem    = df["classificacao_imc"].value_counts().reindex(ordem).dropna()
    contagem    = contagem[contagem > 0]
    percentuais = (contagem / contagem.sum()) * 100
    colors      = sns.color_palette("Spectral")[: len(contagem)][::-1]

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, _ = ax.pie(
        contagem, labels=None, autopct=None, startangle=90,
        colors=colors, wedgeprops=dict(width=0.6, edgecolor="white"),
    )
    for wedge, count in zip(wedges, contagem):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x   = 0.6 * np.cos(np.deg2rad(ang))
        y   = 0.6 * np.sin(np.deg2rad(ang))
        pct = count / contagem.sum() * 100
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                fontsize=16, color="black", weight="bold")

    legend_labels = [
        f"{l}: {int(c)} ({p:.1f}%)"
        for l, c, p in zip(contagem.index, contagem.values, percentuais.values)
    ]
    ax.legend(legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.15),
              fontsize=14, frameon=False, ncol=2)
    ax.axis("equal")
    plt.tight_layout(rect=[0, 0.75, 1, 0.85])
    fig.suptitle("Distribuição de IMC", fontsize=18, x=0.01,
                 ha="left", fontweight="bold", y=0.98)
    fig.text(0.01, 0.90, "Classificação dos participantes por faixa de IMC",
             fontsize=14, ha="left")
    _salvar_e_upload(fig, "imc.png", drive_service, "IMC")


def grafico_faixa_etaria_sintomas(df: pd.DataFrame, drive_service):
    bins   = [0, 40, 45, 50, 55, 60, 100]
    labels = ["<40", "40-45", "45-50", "50-55", "55-60", ">60"]
    df["faixa_idade_manifestacao"] = pd.cut(
        df["idade_sintomas"], bins=bins, labels=labels, right=False
    )
    contagem    = df["faixa_idade_manifestacao"].value_counts().reindex(labels, fill_value=0)
    percentuais = (contagem / contagem.sum()) * 100
    media_idade = df["idade_sintomas"].mean()

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=contagem.index, y=contagem.values,
                palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Faixa Etária", fontsize=12)
    ax.set_ylabel("Número de Respondentes", fontsize=12)

    offset = contagem.max() * 0.02
    for i, (count, pct) in enumerate(zip(contagem.values, percentuais.values)):
        if count > 0:
            ax.text(i, count + offset, f"{int(count)} ({pct:.1f}%)",
                    ha="center", va="bottom", fontsize=11)

    plt.tight_layout(rect=[0, 0, 1, 0.85])
    fig.suptitle("Idade na Primeira Manifestação dos Sintomas", fontsize=18,
                 x=0.01, ha="left", fontweight="bold", y=0.98)
    fig.text(0.01, 0.90, f"Média de idade na manifestação: {media_idade:.1f} anos",
             fontsize=14, ha="left")
    _salvar_e_upload(fig, "faixa_etaria_sintomas.png", drive_service, "Faixa Etária Sintomas")


def grafico_estresse(df: pd.DataFrame, drive_service):
    contagem    = df["afirm_ano_aparec_sintomas_estresse_intenso"].value_counts()
    percentuais = (contagem / contagem.sum()) * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x=contagem.values, y=contagem.index, palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Número de Respondentes", fontsize=12)
    ax.set_ylabel("", fontsize=6)

    for i, (count, pct) in enumerate(zip(contagem.values, percentuais.values)):
        ax.text(count + 0.5, i, f"{int(count)} ({pct:.1f}%)",
                va="center", fontsize=14)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.suptitle("Estresse Intenso no Período de Sintomas", fontsize=18,
                 x=0.01, ha="left", fontweight="bold", y=0.98)
    fig.text(0.01, 0.90,
             "Estava em um período de estresse intenso quando surgiram sintomas",
             fontsize=14, ha="left")
    _salvar_e_upload(fig, "relacao_estresse.png", drive_service, "Estresse")


def grafico_covid(df: pd.DataFrame, drive_service):
    contagem    = df["covid_piora_sintomas"].value_counts()
    percentuais = (contagem / contagem.sum()) * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x=contagem.values, y=contagem.index, palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Número de Respondentes", fontsize=12)
    ax.set_ylabel("", fontsize=6)

    for i, (count, pct) in enumerate(zip(contagem.values, percentuais.values)):
        ax.text(count + 0.5, i, f"{int(count)} ({pct:.1f}%)",
                va="center", fontsize=14)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.suptitle("Relação dos sintomas com COVID-19", fontsize=18,
                 x=0.01, ha="left", fontweight="bold", y=0.98)
    _salvar_e_upload(fig, "relacao_covid.png", drive_service, "COVID-19")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    log.info("=== Iniciando análise EMAP ===")

    gc, drive_service = get_google_clients()
    df_raw = carregar_dados(gc)
    df     = tratar_dados(df_raw)

    graficos = [
        grafico_genero,
        grafico_febre_reumatica,
        grafico_benzetacil,
        grafico_imc,
        grafico_faixa_etaria_sintomas,
        grafico_estresse,
        grafico_covid,
    ]

    erros = []
    for fn in graficos:
        try:
            fn(df, drive_service)
        except Exception as exc:
            log.error("Erro em %s: %s", fn.__name__, exc, exc_info=True)
            erros.append(fn.__name__)

    if erros:
        raise RuntimeError(f"Falha em {len(erros)} gráfico(s): {erros}")

    log.info("=== Análise concluída. %d gráficos gerados. ===", len(graficos))


if __name__ == "__main__":
    main()
