
# ============================================================
# PROJETO INTEGRADOR I
# PROCESSAMENTO DE MEDICAMENTOS - V4.0 CORRIGIDA
# ============================================================

from pathlib import Path
from collections import Counter
from datetime import datetime, date
import json
import re
import unicodedata

import pandas as pd


# ============================================================
# 1. CAMINHOS
# ============================================================

BASE = Path(__file__).resolve().parent

ENTRADA = BASE / "santa_casa.registros_medicos.json"

SAIDA = BASE / "resultados_v40"


# ============================================================
# 2. NOMES COMERCIAIS CONHECIDOS
# ============================================================

ALIAS = {
    "NOVALGINA": "DIPIRONA",
    "DECADRON": "DEXAMETASONA",
    "TRAMAL": "TRAMADOL",
    "ROCEFIN": "CEFTRIAXONA",
    "RIVOTRIL": "CLONAZEPAM",
}

PRINCIPIOS = [
    "DIPIRONA",
    "AZITROMICINA",
    "AMOXICILINA",
    "PARACETAMOL",
    "IBUPROFENO",
    "CEFTRIAXONA",
    "DEXAMETASONA",
    "TRAMADOL",
    "CLONAZEPAM",
]


# ============================================================
# 3. NORMALIZACAO DE TEXTO
# ============================================================

def normalizar(valor):

    if valor is None:
        return ""

    if isinstance(valor, (dict, list)):
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

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def contem(texto, termo):

    padrao = (
        r"(?<![A-Z0-9])"
        + re.escape(termo)
        + r"(?![A-Z0-9])"
    )

    return bool(re.search(padrao, texto))


# ============================================================
# 4. CONVERSAO SEGURA DAS DATAS
# ============================================================

def data_valida(valor):

    if valor is None:
        return pd.NaT

    # Datas podem estar encapsuladas em dicionarios.
    if isinstance(valor, dict):

        for chave in [
            "$date",
            "date",
            "data",
            "value"
        ]:

            if chave in valor:

                return data_valida(
                    valor[chave]
                )

        return pd.NaT

    # Nao presumir unidade de timestamps numericos.
    if isinstance(valor, (int, float, list, tuple)):
        return pd.NaT

    try:

        data = pd.to_datetime(
            valor,
            errors="coerce",
            utc=True
        )

        if isinstance(data, pd.Timestamp):
            return data

        return pd.NaT

    except (
        ValueError,
        TypeError,
        OverflowError
    ):

        return pd.NaT


def obter_data(info, registro):

    campos = [
        "dataAdministrada",
        "dataEntrada",
        "dataCadastro"
    ]

    # Prioridade global por tipo de data.
    for campo in campos:

        for origem in [info, registro]:

            if not isinstance(origem, dict):
                continue

            valor = origem.get(campo)

            data = data_valida(valor)

            if pd.notna(data):

                return data, campo

    return pd.NaT, "SEM_DATA"


# ============================================================
# 5. EXTRAIR MEDICAMENTO
# ============================================================

def extrair_medicamento(info):

    medicamento = info.get("medicamento")

    if not isinstance(medicamento, dict):
        return "", ""

    nome = normalizar(
        medicamento.get("nome")
    )

    descricao = normalizar(
        medicamento.get("descricao")
    )

    return nome, descricao


# ============================================================
# 6. PADRONIZACAO
# ============================================================

def identificar(nome, descricao):

    # Procurar principios ativos explicitamente presentes
    # na descricao.
    encontrados = [
        principio
        for principio in PRINCIPIOS
        if contem(descricao, principio)
    ]

    # Evitar escolher um principio quando varios
    # principios conhecidos aparecem.
    if len(encontrados) > 1:

        return (
            nome or descricao or "NAO IDENTIFICADO",
            "REVISAO_COMPOSICAO"
        )

    # Caso a descricao contenha um principio conhecido,
    # ele sera utilizado como nome de pesquisa.
    if len(encontrados) == 1:

        principio = encontrados[0]

        # Se o nome for um alias conhecido e conflitar
        # com a descricao, preservar para revisao.
        if (
            nome in ALIAS
            and ALIAS[nome] != principio
        ):

            return (
                nome,
                "REVISAO_CONFLITO"
            )

        return principio, "DESCRICAO"

    # Nomes comerciais conhecidos
    if nome in ALIAS:

        return ALIAS[nome], "ALIAS_CANDIDATO"

    # Principio ativo no nome
    encontrados_nome = [
        principio
        for principio in PRINCIPIOS
        if contem(nome, principio)
    ]

    if len(encontrados_nome) == 1:

        return encontrados_nome[0], "NOME"

    if nome:
        return nome, "NOME_ORIGINAL"

    if descricao:
        return descricao, "DESCRICAO_ORIGINAL"

    return "NAO IDENTIFICADO", "SEM_NOME"


# ============================================================
# 7. CARREGAMENTO DO JSON
# ============================================================

def carregar_json():

    print("\nCARREGANDO BANCO DE DADOS...")

    if not ENTRADA.exists():

        raise FileNotFoundError(
            f"Arquivo nao encontrado: {ENTRADA}"
        )

    with open(
        ENTRADA,
        "r",
        encoding="utf-8"
    ) as arquivo:

        banco = json.load(arquivo)

    if isinstance(banco, dict):

        for chave in [
            "dados",
            "pacientes",
            "registros"
        ]:

            if isinstance(banco.get(chave), list):

                banco = banco[chave]
                break

    if not isinstance(banco, list):

        raise ValueError(
            "Estrutura principal do JSON nao reconhecida."
        )

    print(
        f"Pacientes carregados: {len(banco):,}"
    )

    return banco


# ============================================================
# 8. PROCESSAMENTO
# ============================================================

def processar(banco):

    print("\nPROCESSANDO MEDICAMENTOS...")

    contagens = Counter()
    qualidade = Counter()
    origens_data = Counter()

    total = 0

    for paciente in banco:

        if not isinstance(paciente, dict):
            continue

        registros = paciente.get(
            "registros",
            []
        )

        if not isinstance(registros, list):
            continue

        for registro in registros:

            if not isinstance(registro, dict):
                continue

            if registro.get("tipo") != "MEDICAMENTO":
                continue

            total += 1

            info = registro.get(
                "informacoes",
                {}
            )

            if not isinstance(info, dict):
                info = {}

            nome, descricao = extrair_medicamento(
                info
            )

            padronizado, metodo = identificar(
                nome,
                descricao
            )

            data, origem_data = obter_data(
                info,
                registro
            )

            if pd.isna(data):

                periodo = "SEM_DATA"

            else:

                periodo = data.strftime(
                    "%Y-%m"
                )

            chave = (
                periodo,
                padronizado,
                nome,
                descricao,
                origem_data,
                metodo
            )

            contagens[chave] += 1

            qualidade[metodo] += 1

            origens_data[origem_data] += 1

    linhas = []

    for chave, quantidade in contagens.items():

        (
            periodo,
            padronizado,
            nome,
            descricao,
            origem_data,
            metodo
        ) = chave

        linhas.append({
            "ano_mes": periodo,
            "medicamento": padronizado,
            "nome_original": nome,
            "descricao_original": descricao,
            "origem_data": origem_data,
            "metodo_identificacao": metodo,
            "qtd_registros": quantidade
        })

    df = pd.DataFrame(
        linhas,
        columns=[
            "ano_mes",
            "medicamento",
            "nome_original",
            "descricao_original",
            "origem_data",
            "metodo_identificacao",
            "qtd_registros"
        ]
    )

    return (
        df,
        qualidade,
        origens_data,
        total
    )


# ============================================================
# 9. EXPORTACAO
# ============================================================

def exportar(
    df,
    qualidade,
    origens_data,
    total
):

    SAIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    total_agregado = int(
        df["qtd_registros"].sum()
    )

    if total_agregado != total:

        raise ValueError(
            "Inconsistencia na contagem: "
            f"{total_agregado} != {total}"
        )

    catalogo = (
        SAIDA / "catalogo_medicamentos_por_mes.csv"
    )

    df.to_csv(
        catalogo,
        index=False,
        encoding="utf-8-sig"
    )

    resumo = pd.DataFrame([
        {
            "metodo": metodo,
            "qtd_registros": quantidade
        }
        for metodo, quantidade
        in qualidade.items()
    ])

    resumo.to_csv(
        SAIDA / "qualidade_mapeamento.csv",
        index=False,
        encoding="utf-8-sig"
    )

    ranking = (
        df.groupby(
            "medicamento",
            as_index=False
        )["qtd_registros"]
        .sum()
        .sort_values(
            "qtd_registros",
            ascending=False
        )
    )

    ranking.to_csv(
        SAIDA / "frequencia_padronizada.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\n" + "=" * 60)
    print("RESULTADOS DO PROCESSAMENTO")
    print("=" * 60)

    print(
        f"Registros encontrados: {total:,}"
    )

    print(
        f"Registros agregados (soma): {total_agregado:,}"
    )

    print(
        f"Linhas do catalogo: {len(df):,}"
    )

    print(
        f"Medicamentos/categorias: {len(ranking):,}"
    )

    print("\nORIGEM DAS DATAS")

    for origem, quantidade in (
        origens_data.items()
    ):

        print(
            f"{origem}: {quantidade:,}"
        )

    print("\nMETODOS DE IDENTIFICACAO")

    print(
        resumo.to_string(index=False)
    )

    print("\n20 MEDICAMENTOS MAIS FREQUENTES")

    print(
        ranking.head(20)
        .to_string(index=False)
    )

    print("\nVERIFICACAO DE MEDICAMENTOS")

    for termo in [
        "DIPIRONA",
        "AZITROMICINA",
        "AMOXICILINA"
    ]:

        selecionados = df.loc[
            (
                df["medicamento"]
                .fillna("")
                .str.contains(
                    termo,
                    regex=False
                )
            )
            |
            (
                df["descricao_original"]
                .fillna("")
                .str.contains(
                    termo,
                    regex=False
                )
            )
        ]

        print(
            f"{termo}: "
            f"{int(selecionados['qtd_registros'].sum()):,}"
        )

    print("\nARQUIVOS GERADOS")

    for arquivo in SAIDA.glob("*.csv"):

        print(
            arquivo.name
        )

    print("\nPROCESSAMENTO CONCLUIDO!")


# ============================================================
# 10. EXECUCAO
# ============================================================

def main():

    print("=" * 60)
    print("PROJETO INTEGRADOR I - VERSAO 4.0 CORRIGIDA")
    print("=" * 60)

    banco = carregar_json()

    (
        df,
        qualidade,
        origens_data,
        total
    ) = processar(banco)

    if df.empty:

        print(
            "Nenhum medicamento encontrado."
        )

        return

    exportar(
        df,
        qualidade,
        origens_data,
        total
    )


if __name__ == "__main__":
    main()
