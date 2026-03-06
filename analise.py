"""
Análise de Respostas EMAP - Script Principal
Lê dados do Google Sheets e gera gráficos em PNG.
Os gráficos são commitados no repositório e servidos via GitHub Pages com URLs estáticas.
Autenticação via Service Account (sem interação manual).
"""

import os
import re
import unicodedata
import logging
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import json

warnings.filterwarnings("ignore")
pd.options.mode.chained_assignment = None

# ---------------------------------------------------------------------------
# Tamanhos de fonte globais — acessibilidade para baixa visão
# ---------------------------------------------------------------------------
F_TITULO    = 28   # suptitle
F_SUBTITULO = 22   # fig.text secundário
F_EIXO      = 20   # labels dos eixos x/y
F_TICK      = 18   # valores nos ticks
F_ROTULO    = 20   # rótulos dentro/sobre as barras
F_PIZZA     = 22   # percentuais dentro das fatias
F_LEGENDA   = 18   # texto das legendas
F_MAPA      = 14   # números dentro do mapa (espaço limitado)

plt.rcParams.update({
    "font.size":        F_TICK,
    "axes.titlesize":   F_TITULO,
    "axes.labelsize":   F_EIXO,
    "xtick.labelsize":  F_TICK,
    "ytick.labelsize":  F_TICK,
    "legend.fontsize":  F_LEGENDA,
})

import requests
import geopandas as gpd

from google.oauth2 import service_account
import gspread

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1jl1C9z_6f5Z_y-sxBfEGkT35BDJmcXxFVbuhESTk3dI").strip("'\"")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "Coleta")
SCOPES         = ["https://www.googleapis.com/auth/spreadsheets"]

OUTPUT_DIR = Path("graficos")
OUTPUT_DIR.mkdir(exist_ok=True)

LIKERT_MAP = {
    1: "Discordo Totalmente",
    2: "Discordo Parcialmente",
    3: "Nem Concordo Nem Discordo",
    4: "Concordo Parcialmente",
    5: "Concordo Totalmente",
}
LIKERT_COLORS = {
    1: "#47a0b3",
    2: "#a2d9a4",
    3: "#fee999",
    4: "#fca55d",
    5: "#e2514a",
}


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def get_google_client():
    SA_FILE = "service_account.json"
    if Path(SA_FILE).exists():
        gc = gspread.service_account(filename=SA_FILE)
    else:
        import json
        sa_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        gc = gspread.authorize(creds)
    return gc


# ---------------------------------------------------------------------------
# Carregamento dos dados
# ---------------------------------------------------------------------------

def carregar_dados(gc) -> pd.DataFrame:
    log.info("Carregando dados: planilha=%s aba=%s", SPREADSHEET_ID, WORKSHEET_NAME)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet   = spreadsheet.worksheet(WORKSHEET_NAME)
    data        = worksheet.get_all_values()
    df          = pd.DataFrame(data[1:], columns=data[0])
    log.info("%d respostas carregadas", len(df))
    return df


# ---------------------------------------------------------------------------
# Tratamento dos dados
# ---------------------------------------------------------------------------

def _remover_acentos(texto):
    if not isinstance(texto, str):
        return texto
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )

def _replace_commas_in_parentheses(text):
    if not isinstance(text, str):
        return text
    pattern = r"\((.*?)\)"
    for match in re.findall(pattern, text):
        text = text.replace(f"({match})", f"({match.replace(',', ';')})")
    return text

def tratar_dados(df: pd.DataFrame):
    log.info("Tratando dados...")

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
        "doencas_autoimunes_pais_irmaos", "doencas_autoimunes_pais_irmaos_descricao",
        "piora_sintomas_apos_cirurgia", "sintomas_juventude",
        "end", "uf", "doencas_inflamatorias_pais_irmaos",
    ]

    df = df.iloc[:, : len(novos_nomes)]
    df.columns = novos_nomes[: len(df.columns)]
    df.drop(columns=["end"], inplace=True, errors="ignore")

    # Gênero
    df["genero"] = df["genero"].map({"Feminino": "F", "Masculino": "M"})

    # Idades
    ano_atual = datetime.today().year
    df["nasc_ano"]            = pd.to_numeric(df["nasc_ano"], errors="coerce")
    df["percep_sintomas_ano"] = pd.to_numeric(df["percep_sintomas_ano"], errors="coerce")

    # Filtra anos de nascimento implausíveis (idade entre 10 e 100 anos)
    df.loc[~df["nasc_ano"].between(ano_atual - 100, ano_atual - 10), "nasc_ano"] = np.nan

    # Filtra ano de aparecimento dos sintomas (entre 1950 e o ano atual)
    df.loc[~df["percep_sintomas_ano"].between(1950, ano_atual), "percep_sintomas_ano"] = np.nan

    df["idade_atual"]    = ano_atual - df["nasc_ano"]
    df["idade_sintomas"] = df["percep_sintomas_ano"] - df["nasc_ano"]

    # Garante que idade dos sintomas seja plausível (entre 1 e 100 anos)
    df.loc[~df["idade_sintomas"].between(1, 100), "idade_sintomas"] = np.nan

    # IMC
    df["percep_sinatomas_peso"] = pd.to_numeric(df["percep_sinatomas_peso"], errors="coerce")
    df["altur_m"]               = pd.to_numeric(df["altura"], errors="coerce") / 100
    df["percep_sintomas_imc"]   = df["percep_sinatomas_peso"] / df["altur_m"] ** 2
    df["classificacao_imc"]     = df["percep_sintomas_imc"].apply(_classificar_imc)

    # Febre reumática
    df["fl_teve_febre_reumatica"] = (
        (df["febre_reumatica_idade_diagnostico"].notna() &
         (df["febre_reumatica_idade_diagnostico"].astype(str).str.strip() != "")) |
        (df["febre_reumatica_sintomas"].notna() &
         (df["febre_reumatica_sintomas"].astype(str).str.strip() != ""))
    )

    # Benzetacil
    df["benzetacil_anos_tratamento"] = pd.to_numeric(df["benzetacil_anos_tratamento"], errors="coerce")

    # UF padronizada
    df["UF"] = df["uf"].str.upper().str.strip()

    # Ascendência
    asc = df[["data_hora_resposta", "cod_identificador", "ascendencia"]].copy()
    asc["ascendencia"] = asc["ascendencia"].apply(_replace_commas_in_parentheses)
    asc["ascendencia"] = asc["ascendencia"].apply(_remover_acentos)
    asc["ascendencia"] = asc["ascendencia"].str.split(", ")
    asc_exploded = asc.explode("ascendencia")
    asc_dummies  = pd.get_dummies(asc_exploded["ascendencia"])
    ascendencia_final = (
        asc_exploded[["cod_identificador", "data_hora_resposta"]]
        .join(asc_dummies)
        .groupby(["cod_identificador", "data_hora_resposta"])
        .sum()
        .reset_index()
    )

    # Sintomas
    sint = df[["data_hora_resposta", "cod_identificador", "sintomas"]].copy()
    sint["sintomas"] = sint["sintomas"].apply(_remover_acentos)
    sint["sintomas"] = sint["sintomas"].str.split(", ")
    sint_exploded = sint.explode("sintomas")
    sint_dummies  = pd.get_dummies(sint_exploded["sintomas"])
    sintomas_final = (
        sint_exploded[["cod_identificador", "data_hora_resposta"]]
        .join(sint_dummies)
        .groupby(["cod_identificador", "data_hora_resposta"])
        .sum()
        .reset_index()
    )
    for col in sintomas_final.columns:
        if col not in ["cod_identificador", "data_hora_resposta"]:
            sintomas_final[col] = sintomas_final[col].apply(lambda x: 1 if x != 0 else 0)

    log.info("Tratamento concluído. Total: %d respondentes", len(df))
    return df, ascendencia_final, sintomas_final


def _classificar_imc(imc):
    if pd.isna(imc): return np.nan
    if imc < 18.5:   return "Abaixo do peso"
    if imc < 24.9:   return "Peso normal"
    if imc < 29.9:   return "Sobrepeso"
    if imc < 34.9:   return "Obesidade grau 1"
    if imc < 39.9:   return "Obesidade grau 2"
    return "Obesidade grau 3"


# ---------------------------------------------------------------------------
# Helper de salvamento
# ---------------------------------------------------------------------------

def _salvar(fig, nome_arquivo: str, titulo_log: str):
    caminho = OUTPUT_DIR / nome_arquivo
    fig.savefig(caminho, dpi=300, bbox_inches="tight")
    plt.close(fig)
    log.info("Salvo: %s — %s", nome_arquivo, titulo_log)


# ---------------------------------------------------------------------------
# Helper gráfico de pizza Likert
# ---------------------------------------------------------------------------

def _grafico_pizza_likert(df, coluna, ordem_map, colors_map, titulo, subtitulo, nome_arquivo):
    contagem = df[coluna].value_counts().reset_index()
    contagem.columns = ["Indice", "count"]
    contagem["Indice"] = pd.to_numeric(contagem["Indice"], errors="coerce")
    contagem["label"] = contagem["Indice"].map(ordem_map)
    contagem["cores"] = contagem["Indice"].map(colors_map)
    contagem = contagem.dropna(subset=["label"]).sort_values("Indice")
    percentuais = (contagem["count"] / contagem["count"].sum()) * 100

    fig, ax = plt.subplots(figsize=(10, 9))
    ax.set_position([0.1, 0.30, 0.80, 0.55])  # [left, bottom, width, height]
    wedges, _ = ax.pie(
        percentuais,
        startangle=90,
        colors=contagem["cores"],
        wedgeprops=dict(width=0.6, edgecolor="white"),
    )
    # Só exibe % dentro da fatia se ela for grande o suficiente para caber
    for wedge, row, pct in zip(wedges, contagem.itertuples(), percentuais):
        if pct < 5:
            continue
        ang = (wedge.theta2 + wedge.theta1) / 2
        x = 0.6 * np.cos(np.deg2rad(ang))
        y = 0.6 * np.sin(np.deg2rad(ang))
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                fontsize=F_PIZZA, color="black", weight="bold")

    legend_labels = [
        f"{l}: {int(c)} ({p:.1f}%)"
        for l, c, p in zip(contagem["label"], contagem["count"], percentuais)
    ]
    ax.legend(legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.35),
              fontsize=F_LEGENDA, frameon=False, ncol=2)
    ax.axis("equal")

    fig.suptitle(titulo, fontsize=F_TITULO, x=0.1, ha="left",
                 fontweight="bold", y=0.97)
    fig.text(0.1, 0.91, subtitulo, fontsize=F_SUBTITULO,
             ha="left", va="top")

    plt.tight_layout(rect=[0, 0.10, 1, 0.88])
    _salvar(fig, nome_arquivo, titulo)


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def grafico_genero(df):
    contagem = df["genero"].value_counts().reindex(["F", "M"])
    colors   = ["#FA9FBD", "#34C9A1"]
    labels   = ["Feminino", "Masculino"]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, _ = ax.pie(contagem, labels=None, startangle=90, colors=colors,
                       wedgeprops=dict(width=0.6, edgecolor="white"))
    for wedge, count in zip(wedges, contagem):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x = 0.7 * np.cos(np.deg2rad(ang))
        y = 0.7 * np.sin(np.deg2rad(ang))
        ax.text(x, y, f"{int(count/contagem.sum()*100)}%",
                ha="center", va="center", fontsize=F_PIZZA, color="black", weight="bold")

    legend_labels = [f"{l}: {c} ({c/contagem.sum()*100:.1f}%)" for l, c in zip(labels, contagem)]
    ax.legend(wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
              ncol=2, frameon=False, fontsize=F_LEGENDA)
    ax.axis("equal")
    fig.suptitle("Distribuição por Gênero", fontsize=F_TITULO, x=0.1, y=0.98,
                 ha="left", va="top", fontweight="bold")
    plt.tight_layout()
    _salvar(fig, "distrib_genero.png", "Gênero")


def grafico_febre_reumatica(df):
    contagem    = df["fl_teve_febre_reumatica"].value_counts().reindex([True, False])
    labels      = ["Sim", "Não"]
    colors      = ["#71A7CE", "#E2803E"]
    percentuais = (contagem / contagem.sum()) * 100

    fig, ax = plt.subplots(figsize=(10, 9))
    ax.set_position([0.1, 0.30, 0.80, 0.55])
    wedges, _ = ax.pie(contagem, labels=None, startangle=90, colors=colors,
                       wedgeprops=dict(width=0.6, edgecolor="white"))
    for wedge, count, pct in zip(wedges, contagem, percentuais):
        if pct < 5:
            continue
        ang = (wedge.theta2 + wedge.theta1) / 2
        x = 0.6 * np.cos(np.deg2rad(ang))
        y = 0.6 * np.sin(np.deg2rad(ang))
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                fontsize=F_PIZZA, color="black", weight="bold")

    legend_labels = [f"{l}: {c} ({c/contagem.sum()*100:.1f}%)" for l, c in zip(labels, contagem)]
    ax.legend(legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.35),
              fontsize=F_LEGENDA, frameon=False, ncol=2)
    ax.axis("equal")

    fig.suptitle("Histórico de Febre Reumática", fontsize=F_TITULO, x=0.1,
                 ha="left", fontweight="bold", y=0.97)
    fig.text(0.1, 0.91, "Prevalência de histórico de febre reumática entre os participantes",
             fontsize=F_SUBTITULO, ha="left", va="top")
    plt.tight_layout(rect=[0, 0.10, 1, 0.88])
    _salvar(fig, "febre_reumatica.png", "Febre Reumática")


def grafico_benzetacil(df):
    bins   = [0, 5, 10, 15, 20, 100]
    labels = ["menos de 5", "5-10", "10-15", "15-20", "mais de 20"]
    df["faixa_benzetacil"] = pd.cut(df["benzetacil_anos_tratamento"], bins=bins,
                                     labels=labels, right=False)
    contagem    = df["faixa_benzetacil"].value_counts().reindex(labels, fill_value=0)
    media_tempo = df["benzetacil_anos_tratamento"].mean()

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.barplot(x=contagem.index, y=contagem.values, color="#34C9A1", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Faixa de Tempo de Uso (anos)", fontsize=F_EIXO)
    ax.set_ylabel("Número de Respondentes", fontsize=F_EIXO)

    offset = contagem.max() * 0.03
    for i, count in enumerate(contagem.values):
        if count > 0:
            ax.text(i, count + offset, str(int(count)), ha="center", va="bottom", fontsize=F_ROTULO)

    fig.subplots_adjust(top=0.78)
    fig.suptitle("Tempo de Uso da Benzetacil", 
                 fontsize=F_TITULO, 
                 x=0.1,
                 ha="left", 
                 fontweight="bold", 
                 y=0.97)
    fig.text(0.1, 0.90, 
             f"Tempo médio de uso entre os participantes (média: {media_tempo:.1f} anos)",
             fontsize=F_SUBTITULO, 
             ha="left", 
             va="top")
    _salvar(fig, "tempo_benzetacil.png", "Benzetacil")


def grafico_imc(df):
    ordem    = ["Abaixo do peso", "Peso normal", "Sobrepeso",
                "Obesidade grau 1", "Obesidade grau 2", "Obesidade grau 3"]
    contagem = df["classificacao_imc"].value_counts().reindex(ordem).dropna()
    contagem = contagem[contagem > 0]
    percentuais = (contagem / contagem.sum()) * 100
    colors   = sns.color_palette("Spectral")[: len(contagem)][::-1]

    fig, ax = plt.subplots(figsize=(10, 9))
    ax.set_position([0.1, 0.30, 0.80, 0.55])
    wedges, _ = ax.pie(contagem, labels=None, startangle=90, colors=colors,
                       wedgeprops=dict(width=0.6, edgecolor="white"))
    for wedge, count, pct in zip(wedges, contagem, percentuais):
        if pct < 5:
            continue
        ang = (wedge.theta2 + wedge.theta1) / 2
        x = 0.6 * np.cos(np.deg2rad(ang))
        y = 0.6 * np.sin(np.deg2rad(ang))
        ax.text(x, y, f"{int(pct)}%", ha="center", va="center",
                fontsize=F_PIZZA, color="black", weight="bold")

    legend_labels = [f"{l}: {int(c)} ({p:.1f}%)"
                     for l, c, p in zip(contagem.index, contagem.values, percentuais.values)]
    ax.legend(legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.35),
              fontsize=F_LEGENDA, frameon=False, ncol=2)
    ax.axis("equal")

    fig.suptitle("Distribuição de IMC", fontsize=F_TITULO, x=0.1,
                 ha="left", fontweight="bold", y=0.97)
    fig.text(0.1, 0.91, "Classificação dos participantes por faixa de IMC",
             fontsize=F_SUBTITULO, ha="left", va="top")
    plt.tight_layout(rect=[0, 0.10, 1, 0.88])
    _salvar(fig, "imc.png", "IMC")


def grafico_faixa_etaria_sintomas(df):
    bins   = [0, 40, 45, 50, 55, 60, 100]
    labels = ["<40", "40-45", "45-50", "50-55", "55-60", ">60"]
    df["faixa_idade_manifestacao"] = pd.cut(df["idade_sintomas"], bins=bins,
                                             labels=labels, right=False)
    contagem    = df["faixa_idade_manifestacao"].value_counts().reindex(labels, fill_value=0)
    media_idade = df["idade_sintomas"].mean()

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.barplot(x=contagem.index, y=contagem.values, color="#34C9A1", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Faixa etária quando os sintomas apareceram", fontsize=F_EIXO)
    ax.set_ylabel("Número de Respondentes", fontsize=F_EIXO)

    for i, count in enumerate(contagem.values):
        if count > 0:
            ax.text(i, count + 0.5, str(int(count)), ha="center", va="bottom", fontsize=F_ROTULO)

    fig.subplots_adjust(top=0.78)
    fig.suptitle("Distribuição por Idade na Primeira Manifestação", fontsize=F_TITULO,
                 x=0.1, ha="left", fontweight="bold", y=0.97)
    fig.text(0.1, 0.90,
             f"Idade média de manifestação dos sintomas (média: {media_idade:.1f} anos)",
             fontsize=F_SUBTITULO, ha="left", va="top")
    _salvar(fig, "idade_primeiros_sintomas.png", "Faixa Etária Sintomas")


def grafico_sintomas(df, sintomas_final):
    contagem    = sintomas_final.drop(columns=["cod_identificador", "data_hora_resposta"]).sum().sort_values(ascending=False)
    contagem    = contagem[contagem > 0]
    total       = len(sintomas_final)
    percentuais = (contagem / total) * 100

    fig, ax = plt.subplots(figsize=(14, 12))
    sns.barplot(x=contagem.values, y=contagem.index, palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Número de Respondentes", fontsize=F_EIXO)
    ax.set_ylabel("Sintomas", fontsize=F_EIXO)

    for i, (count, pct) in enumerate(zip(contagem.values, percentuais.values)):
        ax.text(count + 0.5, i, f"{int(count)} ({pct:.1f}%)", va="center", fontsize=F_ROTULO)

    fig.subplots_adjust(top=0.92)
    fig.suptitle("Principais Sintomas Visuais", fontsize=F_TITULO, x=0.1,
                 ha="left", fontweight="bold", y=0.98)
    _salvar(fig, "sintomas.png", "Sintomas")


def grafico_ascendencia(df, ascendencia_final):
    contagem    = ascendencia_final.drop(columns=["cod_identificador", "data_hora_resposta"]).sum().sort_values(ascending=False)
    contagem    = contagem[contagem > 0]
    total       = len(ascendencia_final)
    percentuais = (contagem / total) * 100

    fig, ax = plt.subplots(figsize=(14, 10))
    sns.barplot(x=contagem.values, y=contagem.index, palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Número de Respondentes", fontsize=F_EIXO)
    ax.set_ylabel("Ascendência", fontsize=F_EIXO)

    for i, (count, pct) in enumerate(zip(contagem.values, percentuais.values)):
        ax.text(count + 0.5, i, f"{int(count)} ({pct:.1f}%)", va="center", fontsize=F_ROTULO)

    fig.subplots_adjust(top=0.78)
    fig.suptitle("Origem Étnica", fontsize=F_TITULO, x=0.1, ha="left",
                 fontweight="bold", y=0.97)
    fig.text(0.1, 0.90, "Ancestralidade declarada pelos participantes (múltiplas respostas permitidas)",
             fontsize=F_SUBTITULO, ha="left", va="top")
    _salvar(fig, "ascendencia.png", "Ascendência")


UFS_DICT = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}

COORDENADAS_UF = {
    "AC": [-70.55, -9.02], "AL": [-36.57, -9.57], "AP": [-51.77, 1.41], "AM": [-63.9, -3.47],
    "BA": [-41.7, -12.4], "CE": [-39.3, -5.2], "DF": [-47.9, -14.8], "ES": [-40.4, -19.5],
    "GO": [-49.6, -15.9], "MA": [-45.3, -5.4], "MT": [-56.1, -12.9], "MS": [-54.5, -20.5],
    "MG": [-44.3, -18.2], "PA": [-52.5, -3.8], "PB": [-36.7, -7.1], "PR": [-51.2, -24.4],
    "PE": [-37.8, -8.3], "PI": [-42.8, -7.5], "RJ": [-43.5, -22.8], "RN": [-36.7, -5.8],
    "RS": [-53.4, -30.0], "RO": [-63.9, -10.8], "RR": [-61.5, 2.3], "SC": [-50.9, -27.3],
    "SP": [-48.8, -22.5], "SE": [-37.4, -10.6], "TO": [-48.2, -10.2],
}

COLORSCALE_MAP = ["#F0F0F0", "#47a0b3", "#a2d9a4", "#edf8a3", "#fee999", "#fca55d", "#e2514a"]


def _preparar_dados_uf(df) -> pd.DataFrame:
    contagem   = df["UF"].value_counts().rename_axis("UF").reset_index(name="Total")
    df_ufs     = pd.DataFrame(list(UFS_DICT.items()), columns=["UF", "Estado"])
    dados      = df_ufs.merge(contagem, on="UF", how="left")
    dados["Total"]   = dados["Total"].fillna(0).astype(int)
    total            = dados["Total"].sum()
    dados["percent"] = (dados["Total"] / total * 100).round(1)
    return dados


def grafico_uf_barras(df):
    dados   = _preparar_dados_uf(df)
    contagem = dados[dados["Total"] > 0].sort_values("Total", ascending=False)
    total    = contagem["Total"].sum()

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.barplot(data=contagem, x="Total", y="UF", palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Número de Respondentes", fontsize=F_EIXO)
    ax.set_ylabel("Estado", fontsize=F_EIXO)

    for i, row in enumerate(contagem.itertuples()):
        ax.text(row.Total + 0.2, i, f"{row.Total} ({row.Total/total*100:.1f}%)",
                va="center", fontsize=F_ROTULO)

    fig.subplots_adjust(top=0.78)
    fig.suptitle("Distribuição por Estado", fontsize=F_TITULO, x=0.1,
                 ha="center", fontweight="bold", y=0.97)
    fig.text(0.1, 0.90, "Estado de residência no momento do diagnóstico",
             fontsize=F_SUBTITULO, ha="center", va="top")
    _salvar(fig, "distribuicao_uf_barras.png", "UF Barras")


def grafico_uf_mapa(df):
    dados = _preparar_dados_uf(df)
    total = dados["Total"].sum()

    # Baixa GeoJSON dos estados brasileiros
    geojson_url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    gdf = gpd.read_file(geojson_url)

    # Normaliza nomes para fazer o merge
    gdf["name_norm"] = gdf["name"].str.strip()
    dados["Estado_norm"] = dados["Estado"].str.strip()
    gdf = gdf.merge(dados[["Estado_norm", "Total", "percent"]],
                    left_on="name_norm", right_on="Estado_norm", how="left")
    gdf["Total"]   = gdf["Total"].fillna(0).astype(int)
    gdf["percent"] = gdf["percent"].fillna(0)

    # Escala de cores por faixas (igual ao notebook)
    def _cor(total):
        if total == 0:   return COLORSCALE_MAP[0]
        if total <= 3:   return COLORSCALE_MAP[1]
        if total <= 6:   return COLORSCALE_MAP[2]
        if total <= 10:  return COLORSCALE_MAP[3]
        if total <= 15:  return COLORSCALE_MAP[4]
        if total <= 25:  return COLORSCALE_MAP[5]
        return COLORSCALE_MAP[6]

    gdf["cor"] = gdf["Total"].apply(_cor)

    fig, ax = plt.subplots(figsize=(14, 10))
    gdf.plot(ax=ax, color=gdf["cor"], edgecolor="white", linewidth=0.8)

    # Rótulos com total em cada estado
    for uf, coords in COORDENADAS_UF.items():
        estado = UFS_DICT[uf]
        row    = gdf[gdf["name_norm"] == estado]
        if row.empty:
            continue
        total_uf = int(row["Total"].values[0])
        if total_uf > 0:
            ax.text(coords[0], coords[1], str(total_uf),
                    ha="center", va="center", fontsize=F_MAPA,
                    fontweight="bold", color="black")

    ax.axis("off")

    # Legenda de cores
    from matplotlib.patches import Patch
    legenda = [
        Patch(color=COLORSCALE_MAP[0], label="0"),
        Patch(color=COLORSCALE_MAP[1], label="1–3"),
        Patch(color=COLORSCALE_MAP[2], label="4–6"),
        Patch(color=COLORSCALE_MAP[3], label="7–10"),
        Patch(color=COLORSCALE_MAP[4], label="11–15"),
        Patch(color=COLORSCALE_MAP[5], label="16–25"),
        Patch(color=COLORSCALE_MAP[6], label=">25"),
    ]
    ax.legend(handles=legenda, loc="lower left", title="Respondentes",
              frameon=False, fontsize=F_LEGENDA, title_fontsize=F_LEGENDA)

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    fig.suptitle("Distribuição Geográfica por Estado", fontsize=F_TITULO, x=0.1,
                 ha="left", fontweight="bold", y=0.97)
    fig.text(0.1, 0.90, "Estado de residência no momento do diagnóstico",
             fontsize=F_SUBTITULO, ha="left")
    _salvar(fig, "distribuicao_uf_mapa.png", "UF Mapa")


def grafico_tabagismo(df):
    _grafico_pizza_likert(
        df,
        coluna="afirm_ano_aparec_sintomas_fumava_intensamente",
        ordem_map=LIKERT_MAP,
        colors_map=LIKERT_COLORS,
        titulo="Relação com o Tabagismo",
        subtitulo="Fumava intensamente quando surgiram sintomas",
        nome_arquivo="relacao_tabagismo.png",
    )


def grafico_estresse(df):
    _grafico_pizza_likert(
        df,
        coluna="afirm_ano_aparec_sintomas_estresse_intenso",
        ordem_map=LIKERT_MAP,
        colors_map=LIKERT_COLORS,
        titulo="Relação com o Estresse",
        subtitulo="Estava em um período de estresse intenso quando surgiram sintomas",
        nome_arquivo="relacao_estresse.png",
    )


def grafico_cirurgia(df):
    ordem_cirurgia = {
        1: "5 ou mais anos",
        2: "4 anos",
        3: "3 anos",
        4: "2 anos",
        5: "Até 1 ano",
    }
    colors_cirurgia = {
        1: "#47a0b3",
        2: "#a2d9a4",
        3: "#fee999",
        4: "#fca55d",
        5: "#e2514a",
    }
    _grafico_pizza_likert(
        df,
        coluna="afirm_antes_aparec_sintomas_cirurgia",
        ordem_map=ordem_cirurgia,
        colors_map=colors_cirurgia,
        titulo="Cirurgia antes do aparecimento dos sintomas",
        subtitulo="Quantos anos antes do aparecimento dos primeiros sintomas",
        nome_arquivo="relacao_cirurgia.png",
    )


def grafico_covid(df):
    contagem    = df["covid_piora_sintomas"].value_counts()
    percentuais = (contagem / contagem.sum()) * 100

    fig, ax = plt.subplots(figsize=(14, 9))
    sns.barplot(x=contagem.values, y=contagem.index, palette="Spectral", ax=ax)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#CCCCCC")
    ax.grid(axis="x", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_xlabel("Número de Respondentes", fontsize=F_EIXO)
    ax.set_ylabel("")

    for i, (count, pct) in enumerate(zip(contagem.values, percentuais.values)):
        ax.text(count + 0.5, i, f"{int(count)} ({pct:.1f}%)", va="center", fontsize=F_ROTULO)

    fig.subplots_adjust(top=0.88)
    fig.suptitle("Relação dos sintomas com COVID-19", fontsize=F_TITULO,
                 x=0.1, ha="center", fontweight="bold", y=0.97)
    _salvar(fig, "relacao_covid.png", "COVID-19")

# ---------------------------------------------------------------------------
# Cards de resumo
# ---------------------------------------------------------------------------

def grafico_cards_resumo(df, ascendencia_final, sintomas_final):
    """
    Gera uma imagem com cards de resumo das principais informações da pesquisa.
    """
    from matplotlib.patches import FancyBboxPatch

    total = len(df)

    sint     = sintomas_final.drop(columns=["cod_identificador", "data_hora_resposta"]).sum().sort_values(ascending=False)
    sintoma_nome = sint.index[0] if len(sint) > 0 else "N/A"
    sintoma_pct  = sint.iloc[0] / total * 100 if len(sint) > 0 else 0

    uf_top   = df["UF"].value_counts()
    uf_nome  = uf_top.index[0] if len(uf_top) > 0 else "N/A"
    uf_pct   = uf_top.iloc[0] / total * 100 if len(uf_top) > 0 else 0

    asc_top  = ascendencia_final.drop(columns=["cod_identificador", "data_hora_resposta"]).sum().sort_values(ascending=False)
    asc_nome = asc_top.index[0] if len(asc_top) > 0 else "N/A"
    asc_pct  = asc_top.iloc[0] / total * 100 if len(asc_top) > 0 else 0

    fr_sim   = df["fl_teve_febre_reumatica"].sum()
    fr_pct   = fr_sim / total * 100

    media_sint = df["idade_sintomas"].mean()

    estresse   = pd.to_numeric(df["afirm_ano_aparec_sintomas_estresse_intenso"], errors="coerce")
    estresse_pct = (estresse >= 4).sum() / total * 100

    media_atual = df["idade_atual"].mean()

    cards = [
        {"valor": str(total),            "label": "Total de\nParticipantes",               "cor": "#6C63FF"},
        {"valor": f"{sintoma_pct:.0f}%", "label": f"Sintoma mais comum\n{sintoma_nome}",   "cor": "#A855F7"},
        {"valor": f"{uf_pct:.0f}%",      "label": f"Maior concentração\n{uf_nome}",         "cor": "#22C55E"},
        {"valor": f"{asc_pct:.0f}%",     "label": f"Ascendência predominante\n{asc_nome}",  "cor": "#D97706"},
        {"valor": f"{fr_pct:.0f}%",      "label": "Histórico de\nFebre Reumática",          "cor": "#DC2626"},
        {"valor": f"{media_atual:.0f}",  "label": "Idade média\natual",                     "cor": "#0891B2"},
        {"valor": f"{media_sint:.0f}",   "label": "Idade média no\nsurgimento dos sintomas", "cor": "#2563EB"},
        {"valor": f"{estresse_pct:.0f}%","label": "Relataram estresse\nno período",          "cor": "#EA580C"},
    ]

    cols  = 4
    rows  = (len(cards) + cols - 1) // cols
    fig_w = cols * 5.0
    fig_h = rows * 3.8 + 1.8

    fig, axes = plt.subplots(rows, cols, figsize=(fig_w, fig_h))
    fig.subplots_adjust(top=0.82, hspace=0.35, wspace=0.25)
    axes = np.array(axes).reshape(rows, cols)

    for idx, card in enumerate(cards):
        r, c = divmod(idx, cols)
        ax   = axes[r][c]
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        cor = card["cor"]

        fundo = FancyBboxPatch((0.04, 0.04), 0.92, 0.92,
                               boxstyle="round,pad=0.02",
                               facecolor="#F0F4FF",
                               edgecolor="#D0D8F0", linewidth=2,
                               transform=ax.transAxes, clip_on=False)
        ax.add_patch(fundo)

        # Valor principal — grande e em bold
        ax.text(0.5, 0.62, card["valor"], ha="center", va="center",
                fontsize=38, fontweight="bold", color=cor,
                transform=ax.transAxes)

        # Label — escuro para contraste
        ax.text(0.5, 0.22, card["label"], ha="center", va="center",
                fontsize=14, fontweight="semibold", color="#1a1a1a",
                transform=ax.transAxes,
                multialignment="center", linespacing=1.5)

    for idx in range(len(cards), rows * cols):
        r, c = divmod(idx, cols)
        axes[r][c].axis("off")

    fig.suptitle("Resumo do Perfil EMAP Brasil", fontsize=F_TITULO,
                 fontweight="bold", y=0.97)
    fig.text(0.5, 0.91,
             f"Baseado em {total} respondentes · {datetime.today().strftime('%d/%m/%Y')}",
             ha="center", fontsize=F_SUBTITULO - 4, color="#333333")

    _salvar(fig, "cards_resumo.png", "Cards Resumo")

# ---------------------------------------------------------------------------
# Análise automática com GROQ
# ---------------------------------------------------------------------------

PROMPT_ANALISE = """
Você é um especialista em análise de dados de saúde, com experiência em comunicação acessível para pacientes e familiares.

Você recebeu dados de uma pesquisa de perfil dos participantes do grupo EMAP Brasil.

EMAP (Atrofia Macular Extensa cpm Pseudodrusas) é uma síndrome inflamatória autoimune rara, 
possivelmente relacionada a histórico de febre reumática e infecção por estreptococos. 
A pesquisa foi realizada com pacientes diagnosticados com EMAP, de forma voluntária via internet.

Com base nesses dados fornecidos, escreva uma análise em português brasileiro, em linguagem acessível 
(evite jargões médicos sem explicação), dividida nas seguintes seções:

## Dados Básicos
Analise perfil demográfico: gênero, idade de manifestação dos sintomas, distribuição geográfica e ascendência.
Comente padrões relevantes e possíveis explicações (ex: viés de seleção por internet, concentração em SP, etc).

## Dados de Saúde
Analise IMC, febre reumática, uso de Benzetacil, tabagismo, estresse, cirurgias e relação com COVID-19.
Destaque o que chamou atenção e o que surpreendentemente NÃO foi encontrado como fator prevalente.

## Conclusão
Sintetize os achados mais relevantes em 2-3 parágrafos. Aponte o que pode ser interessante para pesquisadores.
Mantenha tom de esperança e engajamento, condizente com uma ONG de suporte a pacientes.

Importante:
- Use linguagem direta e empática, como se estivesse explicando para um paciente ou familiar
- Mencione números e percentuais dos gráficos quando relevante
- Não faça afirmações causais definitivas — use "pode indicar", "sugere", "é possível que"
- O texto deve ter entre 400 e 600 palavras no total
"""


def _resumir_dados(df, ascendencia_final, sintomas_final) -> str:
    """
    Monta um resumo textual dos dados para enviar ao Groq.
    """
    total = len(df)
    linhas = [f"Total de respondentes: {total}"]

    # Gênero
    genero = df["genero"].value_counts()
    for g, n in genero.items():
        linhas.append(f"Gênero {g}: {n} ({n/total*100:.1f}%)")

    # Idades
    media_atual   = df["idade_atual"].mean()
    media_sintomas = df["idade_sintomas"].mean()
    linhas.append(f"Idade média atual: {media_atual:.1f} anos")
    linhas.append(f"Idade média no surgimento dos sintomas: {media_sintomas:.1f} anos")

    # IMC
    imc = df["classificacao_imc"].value_counts()
    for cat, n in imc.items():
        linhas.append(f"IMC - {cat}: {n} ({n/total*100:.1f}%)")

    # Febre reumática
    fr = df["fl_teve_febre_reumatica"].value_counts()
    sim = fr.get(True, 0)
    nao = fr.get(False, 0)
    linhas.append(f"Histórico de febre reumática - Sim: {sim} ({sim/total*100:.1f}%), Não: {nao} ({nao/total*100:.1f}%)")

    # Benzetacil
    media_benz = df["benzetacil_anos_tratamento"].mean()
    linhas.append(f"Tempo médio de uso de Benzetacil: {media_benz:.1f} anos")

    # UF (top 5)
    ufs = df["UF"].value_counts().head(5)
    for uf, n in ufs.items():
        linhas.append(f"Estado {uf}: {n} respondentes ({n/total*100:.1f}%)")

    # Ascendência (top 5)
    asc = ascendencia_final.drop(columns=["cod_identificador", "data_hora_resposta"]).sum().sort_values(ascending=False).head(5)
    for nome, n in asc.items():
        linhas.append(f"Ascendência {nome}: {int(n)} ({int(n)/total*100:.1f}%)")

    # Sintomas (top 5)
    sint = sintomas_final.drop(columns=["cod_identificador", "data_hora_resposta"]).sum().sort_values(ascending=False).head(5)
    for nome, n in sint.items():
        linhas.append(f"Sintoma '{nome}': {int(n)} ({int(n)/total*100:.1f}%)")

    # Likert — estresse
    likert_map = {1: "Discordo Totalmente", 2: "Discordo Parcialmente",
                  3: "Neutro", 4: "Concordo Parcialmente", 5: "Concordo Totalmente"}
    for col, label in [
        ("afirm_ano_aparec_sintomas_estresse_intenso",     "Estresse intenso"),
        ("afirm_ano_aparec_sintomas_fumava_intensamente",  "Tabagismo intenso"),
        ("afirm_antes_aparec_sintomas_cirurgia",           "Cirurgia antes dos sintomas"),
    ]:
        contagem = pd.to_numeric(df[col], errors="coerce").value_counts().sort_index()
        partes = [f"{likert_map.get(int(k), k)}: {v} ({v/total*100:.1f}%)"
                  for k, v in contagem.items() if pd.notna(k)]
        linhas.append(f"{label} — {', '.join(partes)}")

    # COVID
    covid = df["covid_piora_sintomas"].value_counts()
    for resp, n in covid.items():
        linhas.append(f"COVID piora sintomas - '{resp}': {n} ({n/total*100:.1f}%)")

    return "\n".join(linhas)


def gerar_analise_ia(df, ascendencia_final, sintomas_final):
    """
    Envia os dados numéricos para o Groq e salva a análise em analise.md
    """
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        log.warning("GROQ_API_KEY não configurada — análise automática ignorada.")
        return

    log.info("Gerando análise com Groq...")

    resumo  = _resumir_dados(df, ascendencia_final, sintomas_final)
    mensagem = f"Dados da pesquisa de perfil EMAP Brasil:\n\n{resumo}\n\n{PROMPT_ANALISE}"

    client   = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1500,
        messages=[{"role": "user", "content": mensagem}],
    )
    texto = response.choices[0].message.content

    output_path = Path("analise.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Análise do Perfil EMAP Brasil\n\n")
        f.write(f"*Gerado automaticamente em {datetime.today().strftime('%d/%m/%Y')} "
                f"com base em {len(df)} respondentes.*\n\n")
        f.write(texto)

    log.info("Análise salva em %s", output_path)

# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    log.info("=== Iniciando análise EMAP ===")

    # gc              = get_google_client()
    # df_raw          = carregar_dados(gc)
    url = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=tsv'
    df_raw = pd.read_csv(url, sep="\t")
    df, ascendencia_final, sintomas_final = tratar_dados(df_raw)

    graficos = [
        lambda: grafico_genero(df),
        lambda: grafico_febre_reumatica(df),
        lambda: grafico_benzetacil(df),
        lambda: grafico_imc(df),
        lambda: grafico_faixa_etaria_sintomas(df),
        lambda: grafico_sintomas(df, sintomas_final),
        lambda: grafico_ascendencia(df, ascendencia_final),
        lambda: grafico_uf_barras(df),
        lambda: grafico_uf_mapa(df),
        lambda: grafico_tabagismo(df),
        lambda: grafico_estresse(df),
        lambda: grafico_cirurgia(df),
        lambda: grafico_covid(df),
        lambda: grafico_cards_resumo(df, ascendencia_final, sintomas_final),
    ]

    erros = []
    for fn in graficos:
        try:
            fn()
        except Exception as exc:
            log.error("Erro em %s: %s", fn.__name__, exc, exc_info=True)
            erros.append(fn.__name__)

    if erros:
        raise RuntimeError(f"Falha em {len(erros)} gráfico(s): {erros}")

    log.info("=== Análise concluída. %d gráficos gerados. ===", len(graficos))

    # Gera o texto com os dados dos gráficos com IA (não bloqueia o script se falhar)
    try:
        gerar_analise_ia(df, ascendencia_final, sintomas_final)
    except Exception as exc:
        log.error("Falha ao gerar análise: %s", exc, exc_info=True)

if __name__ == "__main__":
    main()