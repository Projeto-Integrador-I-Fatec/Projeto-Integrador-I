
# ============================================================
# PROJETO INTEGRADOR I
# DASHBOARD HOSPITALAR - VERSAO 4.0
#
# ATUALIZACOES:
# - Dados somente a partir de 01/01/2021
# - Remocao completa da aba de CIDs
# - Atendimentos por mes e comparacao entre anos
# - Pesquisa de queixas por periodo
# - Pesquisa de medicamentos por nome ou descricao
# - Compatibilidade com Streamlit atualizado
#
# FONTES:
# resultados_v35/
# resultados_v40/
# ============================================================

from pathlib import Path
import re
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# 1. CONFIGURACAO
# ============================================================

st.set_page_config(
    page_title="Dashboard Hospitalar v4.0",
    page_icon="🏥",
    layout="wide"
)

BASE = Path(__file__).resolve().parent

PASTA_V35 = BASE / "resultados_v35"
PASTA_V40 = BASE / "resultados_v40"

DATA_INICIAL = pd.Timestamp("2021-01-01")

MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro"
}


# ============================================================
# 2. FUNCOES AUXILIARES
# ============================================================

def normalizar(valor):

    if valor is None or pd.isna(valor):
        return ""

    texto = str(valor).upper().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return re.sub(
        r"\s+",
        " ",
        texto
    ).strip()


def formatar_numero(valor):

    return f"{int(valor):,}".replace(",", ".")


@st.cache_data
def carregar_csv(caminho):

    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo nao encontrado: {caminho}"
        )

    return pd.read_csv(
        caminho,
        encoding="utf-8-sig",
        dtype={"ano_mes": "string"}
    )


def preparar_tabela(
    df,
    colunas_quantidade,
    nome_tabela
):

    tabela = df.copy()

    if "ano_mes" not in tabela.columns:
        raise ValueError(
            f"{nome_tabela} nao possui ano_mes. "
            f"Colunas: {list(tabela.columns)}"
        )

    coluna_quantidade = next(
        (
            coluna
            for coluna in colunas_quantidade
            if coluna in tabela.columns
        ),
        None
    )

    if coluna_quantidade is None:
        raise ValueError(
            f"Coluna de quantidade nao encontrada "
            f"em {nome_tabela}. "
            f"Colunas: {list(tabela.columns)}"
        )

    tabela["quantidade"] = pd.to_numeric(
        tabela[coluna_quantidade],
        errors="coerce"
    ).fillna(0)

    tabela["periodo"] = pd.to_datetime(
        tabela["ano_mes"],
        format="%Y-%m",
        errors="coerce"
    )

    # FILTRO PERMANENTE: 2021 EM DIANTE
    tabela = tabela.dropna(
        subset=["periodo"]
    ).copy()

    tabela = tabela.loc[
        tabela["periodo"] >= DATA_INICIAL
    ].copy()

    tabela["ano"] = tabela["periodo"].dt.year
    tabela["mes"] = tabela["periodo"].dt.month

    tabela["mes_nome"] = (
        tabela["mes"].map(MESES)
    )

    tabela["mes_ano"] = (
        tabela["periodo"].dt.strftime("%m/%Y")
    )

    return tabela


def filtrar_periodo(tabela, anos, meses):

    return tabela.loc[
        tabela["ano"].isin(anos)
        & tabela["mes"].isin(meses)
    ].copy()


def agrupar_mensal(tabela):

    resultado = (
        tabela.groupby(
            "periodo",
            as_index=False
        )["quantidade"]
        .sum()
        .sort_values("periodo")
    )

    resultado["mes_ano"] = (
        resultado["periodo"].dt.strftime("%m/%Y")
    )

    return resultado


def grafico_colunas(tabela, titulo):
    """Grafico mensal com cores por faixa de 1.000 registros."""

    if tabela.empty:
        st.info("Nao existem registros para o periodo selecionado.")
        return

    dados = agrupar_mensal(tabela).copy()
    if dados.empty:
        st.info("Nao existem registros para o periodo selecionado.")
        return

    cores = [
        "#34D399",  # 0-999
        "#38BDF8",  # 1000-1999
        "#FBBF24",  # 2000-2999
        "#FB923C",  # 3000-3999
        "#F87171",  # 4000-4999
        "#A78BFA",  # 5000-5999
        "#F472B6",  # 6000-6999
    ]

    dados["indice_faixa"] = (
        dados["quantidade"].clip(lower=0).floordiv(1000).astype(int)
    )
    dados["faixa"] = dados["indice_faixa"].apply(
        lambda i: f"{i * 1000:,.0f} a {i * 1000 + 999:,.0f}".replace(",", ".")
    )

    indices = sorted(dados["indice_faixa"].unique())
    mapa_cores = {
        f"{i * 1000:,.0f} a {i * 1000 + 999:,.0f}".replace(",", "."):
        cores[i % len(cores)]
        for i in indices
    }
    faixas_ordenadas = list(mapa_cores)

    fig = px.bar(
        dados,
        x="mes_ano",
        y="quantidade",
        color="faixa",
        color_discrete_map=mapa_cores,
        category_orders={
            "mes_ano": dados["mes_ano"].tolist(),
            "faixa": faixas_ordenadas,
        },
        text="quantidade",
        title=titulo,
        labels={
            "mes_ano": "Mes / Ano",
            "quantidade": "Quantidade",
            "faixa": "Faixa de registros",
        },
    )

    fig.update_traces(
        texttemplate="%{y:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>Quantidade: %{y:,.0f}<extra></extra>"
        ),
    )
    fig.update_layout(
        height=680,
        bargap=0.10,
        xaxis_tickangle=-45,
        font=dict(size=14),
        legend_title_text="Faixas de 1.000 registros",
        margin=dict(l=35, r=30, t=80, b=85),
    )
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")



def grafico_ranking(tabela, coluna, titulo, limite=15):
    """Exibe apenas um grafico de ranking, com barras largas e coloridas."""

    if tabela.empty:
        st.info("Nenhum registro encontrado.")
        return

    dados = (
        tabela.groupby(coluna, as_index=False)["quantidade"]
        .sum()
        .sort_values("quantidade", ascending=False)
        .head(limite)
        .copy()
    )

    if dados.empty:
        st.info("Nenhum registro encontrado.")
        return

    cores = [
        "#38BDF8", "#A78BFA", "#34D399", "#FBBF24", "#FB7185",
        "#2DD4BF", "#F472B6", "#818CF8", "#FB923C", "#22D3EE",
        "#A3E635", "#C084FC", "#FACC15", "#60A5FA", "#F87171"
    ]

    mapa_cores = {
        nome: cores[i % len(cores)]
        for i, nome in enumerate(dados[coluna])
    }

    fig = px.bar(
        dados,
        x="quantidade",
        y=coluna,
        color=coluna,
        color_discrete_map=mapa_cores,
        orientation="h",
        title=titulo,
        text="quantidade",
    )

    fig.update_traces(
        width=0.86,
        texttemplate="%{x:,.0f}",
        textposition="inside",
        insidetextanchor="end",
        textfont=dict(size=15, color="#172033"),
        hovertemplate=(
            "<b>%{y}</b><br>Registros: %{x:,.0f}<extra></extra>"
        ),
    )

    fig.update_layout(
        showlegend=False,
        height=max(760, len(dados) * 49 + 130),
        bargap=0.10,
        font=dict(size=15),
        title_font=dict(size=22),
        xaxis=dict(title="Quantidade", tickfont=dict(size=14)),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=dados[coluna].tolist()[::-1],
            tickfont=dict(size=14),
            automargin=True,
        ),
        margin=dict(l=30, r=35, t=75, b=45),
    )

    st.plotly_chart(fig, width="stretch")


def buscar_texto(tabela, coluna, pesquisa):

    termo = normalizar(pesquisa)

    if not termo:
        return tabela.iloc[0:0].copy()

    mascara = (
        tabela[coluna]
        .fillna("")
        .astype(str)
        .map(normalizar)
        .str.contains(
            termo,
            regex=False,
            na=False
        )
    )

    return tabela.loc[mascara].copy()


# ============================================================
# 3. CARREGAMENTO DAS BASES
# ============================================================

st.title("🏥 Dashboard Hospitalar")

st.caption(
    "Projeto Integrador I | Versao 4.0"
)

st.info(
    "Periodo de analise: a partir de 01/01/2021."
)

try:

    atendimentos = preparar_tabela(
        carregar_csv(
            PASTA_V35 / "atendimentos_por_mes.csv"
        ),
        [
            "qtd_atendimentos",
            "quantidade",
            "total",
            "registros"
        ],
        "atendimentos_por_mes"
    )

    sintomas = preparar_tabela(
        carregar_csv(
            PASTA_V35 / "sintomas_por_mes.csv"
        ),
        [
            "qtd_triagens",
            "qtd_mencoes",
            "qtd_registros",
            "quantidade",
            "total"
        ],
        "sintomas_por_mes"
    )

    medicamentos = preparar_tabela(
        carregar_csv(
            PASTA_V40
            / "catalogo_medicamentos_por_mes.csv"
        ),
        [
            "qtd_registros",
            "quantidade"
        ],
        "catalogo_medicamentos_por_mes"
    )

    colunas_obrigatorias = {
        "sintomas": (
            sintomas,
            ["categoria"]
        ),
        "medicamentos": (
            medicamentos,
            [
                "medicamento",
                "nome_original",
                "descricao_original"
            ]
        )
    }

    for nome, (tabela, colunas) in (
        colunas_obrigatorias.items()
    ):

        ausentes = [
            coluna
            for coluna in colunas
            if coluna not in tabela.columns
        ]

        if ausentes:
            raise ValueError(
                f"Colunas ausentes em {nome}: "
                f"{ausentes}"
            )

except (
    FileNotFoundError,
    ValueError,
    KeyError,
    pd.errors.ParserError
) as erro:

    st.error(
        "Nao foi possivel carregar os CSVs."
    )

    st.code(str(erro))

    st.info(
        "Verifique as pastas resultados_v35 "
        "e resultados_v40."
    )

    st.stop()


# ============================================================
# 4. FILTROS DE PERIODO
# ============================================================

anos_disponiveis = sorted(
    set(atendimentos["ano"].tolist())
    | set(sintomas["ano"].tolist())
    | set(medicamentos["ano"].tolist())
)

st.sidebar.header("Filtros de periodo")

anos = st.sidebar.multiselect(
    "Selecione os anos",
    options=anos_disponiveis,
    default=anos_disponiveis
)

meses = st.sidebar.multiselect(
    "Selecione os meses",
    options=list(MESES.keys()),
    default=list(MESES.keys()),
    format_func=lambda mes: MESES[mes]
)

st.sidebar.divider()

st.sidebar.caption(
    "Somente registros de 2021 em diante."
)

if not anos or not meses:

    st.warning(
        "Selecione pelo menos um ano e um mes."
    )
    st.stop()


# ============================================================
# 5. APLICAR FILTROS
# ============================================================

atend_f = filtrar_periodo(
    atendimentos, anos, meses
)

sintomas_f = filtrar_periodo(
    sintomas, anos, meses
)

medicamentos_f = filtrar_periodo(
    medicamentos, anos, meses
)


# ============================================================
# 6. INDICADORES
# ============================================================

total_atendimentos = atend_f["quantidade"].sum()
total_sintomas = sintomas_f["quantidade"].sum()
total_medicamentos = medicamentos_f["quantidade"].sum()

c1, c2, c3 = st.columns(3)

c1.metric(
    "Atendimentos",
    formatar_numero(total_atendimentos)
)

c2.metric(
    "Mencoes de sintomas",
    formatar_numero(total_sintomas)
)

c3.metric(
    "Registros de medicamentos",
    formatar_numero(total_medicamentos)
)


# ============================================================
# 7. ABAS
# ============================================================

aba1, aba2, aba3 = st.tabs([
    "📊 Atendimentos",
    "🩺 Queixas",
    "💊 Medicamentos"
])


# ============================================================
# 8. ABA ATENDIMENTOS
# ============================================================

with aba1:

    st.header(
        "Volume de atendimentos por periodo"
    )

    st.write(
        "Visualize o numero de atendimentos "
        "registrados em cada mes."
    )

    grafico_colunas(
        atend_f,
        "Atendimentos mensais"
    )

    st.subheader(
        "Comparacao entre anos"
    )

    comparacao = (
        atend_f.groupby(
            ["ano", "mes"],
            as_index=False
        )["quantidade"]
        .sum()
    )

    if not comparacao.empty:

        comparacao["mes_nome"] = (
            comparacao["mes"].map(MESES)
        )

        comparacao["ano_texto"] = (
            comparacao["ano"]
            .astype(int)
            .astype(str)
        )

        fig = px.bar(
            comparacao,
            x="mes_nome",
            y="quantidade",
            color="ano_texto",
            barmode="group",
            category_orders={
                "mes_nome": [
                    MESES[mes]
                    for mes in sorted(meses)
                ]
            },
            labels={
                "mes_nome": "Mes",
                "quantidade": "Atendimentos",
                "ano_texto": "Ano"
            },
            title=(
                "Comparacao mensal entre os anos"
            )
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

    st.subheader("Tabela mensal")

    tabela_atend = agrupar_mensal(atend_f)

    st.dataframe(
        tabela_atend[
            ["mes_ano", "quantidade"]
        ].rename(
            columns={
                "mes_ano": "Periodo",
                "quantidade": "Atendimentos"
            }
        ),
        width="stretch",
        hide_index=True
    )


# ============================================================
# 9. ABA QUEIXAS
# ============================================================

with aba2:

    st.header("Pesquisa de queixas")

    st.write(
        "Pesquise uma categoria de sintoma "
        "e consulte sua frequencia mensal."
    )

    pesquisa_queixa = st.text_input(
        "Digite a queixa",
        placeholder="Ex.: febre, dor, tosse",
        key="pesquisa_queixa"
    )

    if pesquisa_queixa.strip():

        encontradas = buscar_texto(
            sintomas,
            "categoria",
            pesquisa_queixa
        )

        opcoes = sorted(
            encontradas["categoria"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if opcoes:

            escolha = st.selectbox(
                "Selecione a queixa",
                options=opcoes
            )

            resultado = sintomas_f.loc[
                sintomas_f["categoria"]
                .astype(str)
                == escolha
            ].copy()

            st.metric(
                "Mencoes no periodo",
                formatar_numero(
                    resultado["quantidade"].sum()
                )
            )

            grafico_colunas(
                resultado,
                f"Frequencia mensal: {escolha}"
            )

            tabela_queixa = agrupar_mensal(
                resultado
            )

            st.dataframe(
                tabela_queixa[
                    ["mes_ano", "quantidade"]
                ].rename(
                    columns={
                        "mes_ano": "Periodo",
                        "quantidade": "Mencoes"
                    }
                ),
                width="stretch",
                hide_index=True
            )

        else:

            st.info(
                "Nenhuma categoria encontrada."
            )

    else:

        grafico_ranking(
            sintomas_f,
            "categoria",
            "15 queixas mais frequentes"
        )

    st.caption(
        "As contagens representam mencoes "
        "de sintomas e nao necessariamente "
        "pacientes unicos."
    )


# ============================================================
# 10. ABA MEDICAMENTOS
# ============================================================

with aba3:

    st.header("Pesquisa de medicamentos")

    st.write(
        "Pesquise pelo principio ativo, "
        "nome comercial ou descricao."
    )

    pesquisa_med = st.text_input(
        "Nome do medicamento",
        placeholder=(
            "Ex.: DIPIRONA, AZITROMICINA, "
            "NOVALGINA"
        ),
        key="pesquisa_medicamento"
    )

    if pesquisa_med.strip():

        termo = normalizar(pesquisa_med)

        # Pesquisa nos tres campos.
        # Cada linha e contada apenas uma vez.

        mascara = pd.Series(
            False,
            index=medicamentos_f.index
        )

        for coluna in [
            "medicamento",
            "nome_original",
            "descricao_original"
        ]:

            correspondencia = (
                medicamentos_f[coluna]
                .fillna("")
                .astype(str)
                .map(normalizar)
                .str.contains(
                    termo,
                    regex=False,
                    na=False
                )
            )

            mascara = mascara | correspondencia

        resultado = medicamentos_f.loc[
            mascara
        ].copy()

        st.metric(
            "Registros encontrados no periodo",
            formatar_numero(
                resultado["quantidade"].sum()
            )
        )

        if not resultado.empty:

            grafico_colunas(
                resultado,
                (
                    "Evolucao mensal: "
                    f"{pesquisa_med.upper()}"
                )
            )

            st.subheader(
                "Medicamentos identificados"
            )

            tabela_med = (
                resultado.groupby(
                    "medicamento",
                    as_index=False
                )["quantidade"]
                .sum()
                .sort_values(
                    "quantidade",
                    ascending=False
                )
            )

            st.dataframe(
                tabela_med.rename(
                    columns={
                        "medicamento": "Medicamento",
                        "quantidade": "Registros"
                    }
                ),
                width="stretch",
                hide_index=True
            )

            st.subheader(
                "Nomes originais encontrados"
            )

            nomes_originais = (
                resultado.groupby(
                    "nome_original",
                    as_index=False
                )["quantidade"]
                .sum()
                .sort_values(
                    "quantidade",
                    ascending=False
                )
            )

            st.dataframe(
                nomes_originais.rename(
                    columns={
                        "nome_original": "Nome original",
                        "quantidade": "Registros"
                    }
                ),
                width="stretch",
                hide_index=True
            )

        else:

            st.info(
                "Nenhum medicamento encontrado "
                "no periodo selecionado."
            )

    else:

        catalogo = medicamentos_f.loc[
            medicamentos_f["medicamento"]
            != "NAO IDENTIFICADO"
        ].copy()

        grafico_ranking(
            catalogo,
            "medicamento",
            "15 medicamentos mais registrados"
        )

    st.warning(
        "Os valores representam registros "
        "de medicamentos, nao prescricoes "
        "ou administracoes confirmadas."
    )

    st.caption(
        "O mapeamento por principio ativo "
        "ainda e parcial. Os nomes originais "
        "foram preservados."
    )


# ============================================================
# 11. RODAPE
# ============================================================

st.divider()

st.caption(
    "Projeto Integrador I - Dashboard v4.0"
)

st.caption(
    "Periodo analisado: a partir de 01/01/2021."
)

st.caption(
    "Fontes: resultados_v35 e resultados_v40."
)
