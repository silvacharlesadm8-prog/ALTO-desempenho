from calendar import monthrange
from datetime import date, datetime, time, timedelta
from html import escape
from pathlib import Path
from textwrap import dedent

import pandas as pd
import altair as alt
import streamlit as st

from compromissos_db import (
    cadastrar_compromisso,
    inicializar_modulo_compromissos,
    listar_compromissos,
)
from database import (
    atualizar_status_evento_agenda,
    atualizar_integrante,
    atualizar_prioridade,
    buscar_integrante_por_id,
    buscar_prioridade_por_id,
    cadastrar_evento_agenda,
    cadastrar_integrante,
    cadastrar_prioridade,
    excluir_evento_agenda,
    inicializar_banco,
    listar_eventos_agenda,
    listar_historico_integrante,
    listar_historico_prioridade,
    listar_integrantes,
    listar_prioridades,
    obter_configuracao,
    salvar_configuracao,
    sincronizar_eventos_microsoft,
)
from graph_agenda import (
    IntegracaoMicrosoftErro,
    conexao_ativa,
    consultar_disponibilidade,
    desconectar,
    obter_token,
)
from entregaveis_db import (
    atualizar_modelo_entregavel,
    atualizar_status_acao,
    buscar_modelo_por_id,
    cadastrar_aviso,
    cadastrar_modelo_entregavel,
    confirmar_entregavel,
    contar_ocorrencias_modelo,
    excluir_modelo_entregavel,
    gerar_ocorrencias_mes,
    inicializar_modulo_entregaveis,
    listar_avisos,
    listar_historico_acoes,
    listar_modelos,
    listar_ocorrencias_mes,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

PASTA_APP = Path(__file__).resolve().parent
CAMINHO_LOGO = PASTA_APP / "assets" / "alto_desempenho_symbol.png"

st.set_page_config(
    page_title="ALTO DESEMPENHO",
    page_icon=str(CAMINHO_LOGO) if CAMINHO_LOGO.is_file() else "📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inicializar_banco()
inicializar_modulo_compromissos()
inicializar_modulo_entregaveis()


# ============================================================
# FUNÇÕES BÁSICAS
# ============================================================

def renderizar_html(conteudo):
    st.html(dedent(conteudo).strip())


def formatar_data(data_iso):
    if not data_iso:
        return "—"

    try:
        return date.fromisoformat(data_iso).strftime(
            "%d/%m/%Y"
        )
    except ValueError:
        return data_iso


def obter_intervalo_semana(data_referencia):
    inicio_semana = (
        data_referencia
        - timedelta(days=data_referencia.weekday())
    )

    fim_semana = inicio_semana + timedelta(days=6)

    return inicio_semana, fim_semana


if "modo_escuro" not in st.session_state:
    st.session_state.modo_escuro = False

# Mantém a navegação na página correta quando um card abre sua baixa.
if st.query_params.get("pagina") == "entregaveis_d1":
    st.session_state["pagina_principal"] = "Entregáveis D-1"


# ============================================================
# MENU
# ============================================================

with st.sidebar:
    if CAMINHO_LOGO.is_file():
        st.image(str(CAMINHO_LOGO), width=150)
    renderizar_html(
        """
        <div class="marca">
            <div class="marca-titulo">ALTO DESEMPENHO</div>
            <div class="marca-subtitulo">
                Acompanhamento, Liderança,<br>
                Tarefas e Objetivos
            </div>
        </div>
        """
    )

    st.divider()

    pagina = st.radio(
        "Menu principal",
        [
            "Início",
            "Direcionamento",
            "Minha semana",
            "Entregáveis D-1",
            "Agenda da gerente",
            "Equipe",
            "Indicadores",
        ],
        label_visibility="collapsed",
        key="pagina_principal",
    )

    st.divider()

    modo_escuro = st.toggle(
        "Modo escuro",
        key="modo_escuro",
    )

    tema_atual = "Escuro" if modo_escuro else "Claro"

    renderizar_html(
        f"""
        <div class="tema-atual">
            Tema atual: {tema_atual}
        </div>

        <div class="rodape-lateral">
            Versão 0.17 · Demonstração executiva
        </div>
        """
    )


# ============================================================
# CORES
# ============================================================

if modo_escuro:
    fundo = "#111A15"
    superficie = "#1C2921"
    campo = "#243129"
    titulo = "#F2F5F2"
    texto = "#C6CEC8"
    texto_suave = "#9EAAA1"
    texto_campo = "#F5F7F5"
    placeholder = "#849087"
    borda = "#3B5042"
    verde_claro = "#2E4737"
    sombra = "rgba(0, 0, 0, 0.25)"
    sidebar_inicio = "#14251B"
    sidebar_fim = "#20382A"
else:
    fundo = "#F3F5F2"
    superficie = "#FFFFFF"
    campo = "#FFFFFF"
    titulo = "#24382B"
    texto = "#59615B"
    texto_suave = "#7E8880"
    texto_campo = "#24382B"
    placeholder = "#8B958E"
    borda = "#D8DED9"
    verde_claro = "#DDE6DF"
    sombra = "rgba(36, 56, 43, 0.08)"
    sidebar_inicio = "#203226"
    sidebar_fim = "#2F4736"


# ============================================================
# ESTILO
# ============================================================

renderizar_html(
    f"""
    <style>
        :root {{
            --verde-escuro: #24382B;
            --dourado: #D5A928;
            --dourado-hover: #E5B832;
            --verde: #2F855A;
            --vermelho: #C74646;
            --neutro: #77817A;

            --fundo: {fundo};
            --superficie: {superficie};
            --campo: {campo};
            --titulo: {titulo};
            --texto: {texto};
            --texto-suave: {texto_suave};
            --texto-campo: {texto_campo};
            --placeholder: {placeholder};
            --borda: {borda};
            --verde-claro: {verde_claro};
            --sombra: {sombra};
        }}

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .stApp {{
            background-color: var(--fundo) !important;
            color: var(--titulo) !important;
        }}

        [data-testid="stHeader"] {{
            background-color: transparent !important;
        }}

        .block-container {{
            max-width: 1500px;
            padding: 2rem 2.5rem 3rem;
        }}

        section[data-testid="stSidebar"] {{
            background: linear-gradient(
                180deg,
                {sidebar_inicio},
                {sidebar_fim}
            );
        }}

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label {{
            color: #FFFFFF !important;
        }}

        section[data-testid="stSidebar"] hr {{
            border-color: rgba(255, 255, 255, 0.15);
        }}

        .marca {{
            padding: 8px 2px 14px;
        }}

        .marca-simbolo {{
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: var(--dourado);
            color: var(--verde-escuro);
            border-radius: 10px;
            font-size: 23px;
            font-weight: 800;
            margin-bottom: 13px;
        }}

        .marca-titulo {{
            color: #FFFFFF;
            font-size: 20px;
            font-weight: 700;
        }}

        .marca-subtitulo,
        .tema-atual,
        .rodape-lateral {{
            color: #C5CEC7;
            font-size: 11px;
            margin-top: 5px;
        }}

        .rodape-lateral {{
            margin-top: 25px;
            padding-top: 14px;
            border-top: 1px solid rgba(255, 255, 255, 0.15);
        }}

        .rotulo-pagina {{
            display: inline-block;
            color: var(--titulo);
            background-color: var(--verde-claro);
            border-radius: 20px;
            padding: 5px 12px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }}

        .titulo-principal {{
            color: var(--titulo);
            font-size: 35px;
            line-height: 1.15;
            font-weight: 750;
        }}

        .subtitulo-principal {{
            color: var(--texto);
            font-size: 16px;
            line-height: 1.6;
            margin-top: 9px;
            margin-bottom: 24px;
            max-width: 950px;
        }}

        .faixa-direcionamento {{
            background: linear-gradient(
                120deg,
                #24382B,
                #395442
            );
            border-radius: 15px;
            padding: 25px 27px;
            margin-bottom: 25px;
            box-shadow: 0 8px 24px var(--sombra);
        }}

        .faixa-rotulo,
        .card-numero {{
            color: var(--dourado);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.8px;
        }}

        .faixa-titulo {{
            color: #FFFFFF;
            font-size: 21px;
            font-weight: 650;
            margin: 8px 0;
        }}

        .faixa-texto {{
            color: #DDE5DF;
            font-size: 14px;
            line-height: 1.55;
        }}

        .card {{
            min-height: 175px;
            background-color: var(--superficie);
            border: 1px solid var(--borda);
            border-radius: 13px;
            padding: 21px;
            box-shadow: 0 3px 12px var(--sombra);
        }}

        .card-titulo {{
            color: var(--titulo);
            font-size: 17px;
            font-weight: 700;
            margin: 13px 0 9px;
        }}

        .card-texto {{
            color: var(--texto);
            font-size: 14px;
            line-height: 1.55;
        }}

        .item-gestao {{
            background-color: var(--superficie);
            border: 1px solid var(--borda);
            border-left: 5px solid var(--dourado);
            border-radius: 11px;
            padding: 18px 20px;
            margin-bottom: 14px;
            box-shadow: 0 3px 12px var(--sombra);
        }}

        .item-titulo {{
            color: var(--titulo);
            font-size: 17px;
            font-weight: 750;
            margin-bottom: 8px;
        }}

        .item-resultado {{
            color: var(--texto);
            font-size: 14px;
            line-height: 1.55;
            margin-bottom: 12px;
        }}

        .item-detalhes {{
            color: var(--texto-suave);
            font-size: 12px;
            line-height: 1.6;
        }}

        .selo {{
            display: inline-block;
            color: #FFFFFF;
            border-radius: 20px;
            padding: 3px 9px;
            font-size: 10px;
            font-weight: 700;
            margin-left: 7px;
        }}

        .selo-programado {{
            background-color: var(--neutro);
        }}

        .selo-entregue {{
            background-color: var(--verde);
        }}

        .selo-nao-entregue {{
            background-color: var(--vermelho);
        }}

        .selo-ativo {{
            background-color: var(--verde);
        }}

        .selo-encerrado {{
            background-color: var(--vermelho);
        }}

        .semana-periodo {{
            color: var(--texto);
            background-color: var(--verde-claro);
            border-radius: 10px;
            padding: 13px 16px;
            margin-bottom: 18px;
            font-size: 14px;
            font-weight: 650;
        }}

        [data-testid="stMain"] h1,
        [data-testid="stMain"] h2,
        [data-testid="stMain"] h3,
        [data-testid="stMain"] h4,
        [data-testid="stMain"] p {{
            color: var(--titulo);
        }}

        [data-testid="stMain"] label,
        [data-testid="stMain"] label p {{
            color: var(--texto) !important;
            opacity: 1 !important;
        }}

        [data-testid="stMain"] div[data-baseweb="input"],
        [data-testid="stMain"] textarea {{
            background-color: var(--campo) !important;
            border-color: var(--borda) !important;
            color: var(--texto-campo) !important;
        }}

        [data-testid="stMain"] input,
        [data-testid="stMain"] textarea {{
            color: var(--texto-campo) !important;
            -webkit-text-fill-color: var(--texto-campo) !important;
            caret-color: var(--dourado) !important;
        }}

        [data-testid="stMain"] input::placeholder,
        [data-testid="stMain"] textarea::placeholder {{
            color: var(--placeholder) !important;
            -webkit-text-fill-color: var(--placeholder) !important;
            opacity: 1 !important;
        }}

        [data-testid="stMain"] div[data-baseweb="select"] > div {{
            background-color: var(--campo) !important;
            border-color: var(--borda) !important;
            color: var(--texto-campo) !important;
        }}

        [data-testid="stMain"] div[data-baseweb="select"] span,
        [data-testid="stMain"] div[data-baseweb="select"] svg {{
            color: var(--texto-campo) !important;
            fill: var(--texto-campo) !important;
        }}

        div[data-baseweb="popover"],
        ul[data-baseweb="menu"] {{
            background-color: var(--superficie) !important;
            color: var(--texto-campo) !important;
        }}

        ul[data-baseweb="menu"] li {{
            color: var(--texto-campo) !important;
            background-color: var(--superficie) !important;
        }}

        ul[data-baseweb="menu"] li:hover {{
            background-color: var(--verde-claro) !important;
        }}

        [data-testid="stForm"] {{
            background-color: var(--superficie) !important;
            border: 1px solid var(--borda) !important;
            border-radius: 12px !important;
            padding: 20px !important;
        }}

        [data-testid="stTabs"] button,
        [data-testid="stTabs"] button p {{
            color: var(--texto) !important;
        }}

        [data-testid="stTabs"] button[aria-selected="true"],
        [data-testid="stTabs"] button[aria-selected="true"] p {{
            color: var(--dourado) !important;
            font-weight: 700 !important;
        }}

        [data-testid="stTabs"] div[data-baseweb="tab-highlight"] {{
            background-color: var(--dourado) !important;
        }}

        [data-testid="stDataFrame"],
        [data-testid="stMetric"],
        [data-testid="stExpander"] {{
            background-color: var(--superficie) !important;
            border: 1px solid var(--borda);
            border-radius: 10px;
        }}

        [data-testid="stMetric"] {{
            padding: 15px;
        }}

        [data-testid="stMetricLabel"] p {{
            color: var(--texto) !important;
        }}

        [data-testid="stMetricValue"] {{
            color: var(--titulo) !important;
        }}

        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button {{
            background-color: var(--dourado) !important;
            color: var(--verde-escuro) !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }}

        div.stButton > button p,
        div[data-testid="stFormSubmitButton"] > button p {{
            color: var(--verde-escuro) !important;
        }}

        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {{
            background-color: var(--dourado-hover) !important;
        }}
    </style>
    """
)


# ============================================================
# COMPONENTES
# ============================================================

def cabecalho(rotulo, titulo_pagina, subtitulo):
    renderizar_html(
        f"""
        <div class="rotulo-pagina">
            {escape(rotulo)}
        </div>

        <div class="titulo-principal">
            {escape(titulo_pagina)}
        </div>

        <div class="subtitulo-principal">
            {escape(subtitulo)}
        </div>
        """
    )


def card(numero, acao, titulo_card, texto_card):
    renderizar_html(
        f"""
        <div class="card">
            <div class="card-numero">
                {escape(numero)} · {escape(acao)}
            </div>

            <div class="card-titulo">
                {escape(titulo_card)}
            </div>

            <div class="card-texto">
                {escape(texto_card)}
            </div>
        </div>
        """
    )


# ============================================================
# INÍCIO
# ============================================================

def pagina_inicio():
    cabecalho(
        "Visão geral",
        "ALTO DESEMPENHO",
        (
            "Acompanhamento, Liderança, Tarefas e Objetivos em um único ambiente "
            "para desenvolver a equipe e transformar compromissos em resultados."
        ),
    )

    renderizar_html(
        """
        <div class="faixa-direcionamento">
            <div class="faixa-rotulo">
                Propósito do sistema
            </div>

            <div class="faixa-titulo">
                Clareza para direcionar. Autonomia para executar.
            </div>

            <div class="faixa-texto">
                A gerente define o que precisa ser alcançado, os responsáveis
                assumem os compromissos e a equipe organiza a execução com
                transparência, responsabilidade e apoio da liderança.
            </div>
        </div>
        """
    )

    coluna_1, coluna_2, coluna_3 = st.columns(
        3,
        gap="large",
    )

    with coluna_1:
        card(
            "01",
            "DIRECIONAR",
            "Prioridades claras",
            "A gerente define o que é prioritário e o resultado esperado.",
        )

    with coluna_2:
        card(
            "02",
            "EXECUTAR",
            "Autonomia com responsabilidade",
            "Cada integrante organiza seus compromissos e sua execução.",
        )

    with coluna_3:
        card(
            "03",
            "ACOMPANHAR",
            "Gestão orientada a resultados",
            "A liderança acompanha resultados e remove impedimentos.",
        )


# ============================================================
# MINHA SEMANA
# ============================================================

def pagina_minha_semana():
    cabecalho(
        "Execução",
        "Minha semana",
        (
            "Organização dos compromissos assumidos por cada integrante, "
            "conectando autonomia, responsabilidade e prioridades."
        ),
    )

    integrantes = listar_integrantes(
        apenas_ativos=True
    )

    prioridades = listar_prioridades(
        apenas_ativas=True
    )

    if not integrantes:
        st.warning(
            "Cadastre pelo menos um integrante ativo "
            "antes de criar compromissos."
        )
        return

    nomes_integrantes = {
        item["id"]: item["nome"]
        for item in integrantes
    }

    opcoes_prioridades = {
        None: "Sem vínculo com prioridade"
    }

    for prioridade in prioridades:
        opcoes_prioridades[prioridade["id"]] = (
            prioridade["titulo"]
        )

    aba_cadastrar, aba_visualizar = st.tabs(
        [
            "Novo compromisso",
            "Visualizar semana",
        ]
    )

    with aba_cadastrar:
        st.subheader("Assumir novo compromisso")

        with st.form(
            "formulario_novo_compromisso",
            clear_on_submit=True,
        ):
            coluna_1, coluna_2 = st.columns(2)

            with coluna_1:
                responsavel_id = st.selectbox(
                    "Responsável *",
                    options=list(
                        nomes_integrantes.keys()
                    ),
                    format_func=lambda identificador: (
                        nomes_integrantes[identificador]
                    ),
                )

                origem = st.selectbox(
                    "Origem do compromisso *",
                    [
                        "Equipe",
                        "Gerente",
                    ],
                    help=(
                        "Equipe: compromisso assumido pelo integrante. "
                        "Gerente: compromisso direcionado pela liderança."
                    ),
                )

            with coluna_2:
                prioridade_id = st.selectbox(
                    "Prioridade relacionada",
                    options=list(
                        opcoes_prioridades.keys()
                    ),
                    format_func=lambda identificador: (
                        opcoes_prioridades[identificador]
                    ),
                )

                criado_por_id = st.selectbox(
                    "Registrado por",
                    options=list(
                        nomes_integrantes.keys()
                    ),
                    format_func=lambda identificador: (
                        nomes_integrantes[identificador]
                    ),
                )

            titulo_compromisso = st.text_input(
                "Compromisso *",
                placeholder=(
                    "Ex.: Consolidar o relatório "
                    "semanal de contratos"
                ),
            )

            resultado_compromisso = st.text_area(
                "Resultado esperado *",
                placeholder=(
                    "Descreva o que precisa estar pronto "
                    "para o compromisso ser considerado concluído."
                ),
                height=120,
            )

            observacao_compromisso = st.text_area(
                "Observação",
                placeholder=(
                    "Informações adicionais, dependências "
                    "ou orientações para a execução."
                ),
                height=90,
            )

            coluna_1, coluna_2 = st.columns(2)

            with coluna_1:
                inicio_compromisso = st.date_input(
                    "Data de início *",
                    value=date.today(),
                    format="DD/MM/YYYY",
                )

            with coluna_2:
                prazo_compromisso = st.date_input(
                    "Prazo *",
                    value=date.today(),
                    format="DD/MM/YYYY",
                )

            salvar_compromisso = st.form_submit_button(
                "Cadastrar compromisso",
                use_container_width=True,
            )

        if salvar_compromisso:
            sucesso, mensagem = cadastrar_compromisso(
                prioridade_id=prioridade_id,
                responsavel_id=responsavel_id,
                criado_por_id=criado_por_id,
                titulo=titulo_compromisso,
                resultado_esperado=resultado_compromisso,
                observacao=observacao_compromisso,
                data_inicio=inicio_compromisso,
                data_prazo=prazo_compromisso,
                origem=origem,
            )

            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)

    with aba_visualizar:
        coluna_1, coluna_2 = st.columns(2)

        with coluna_1:
            integrante_selecionado = st.selectbox(
                "Integrante",
                options=list(
                    nomes_integrantes.keys()
                ),
                format_func=lambda identificador: (
                    nomes_integrantes[identificador]
                ),
                key="responsavel_semana",
            )

        with coluna_2:
            referencia_semana = st.date_input(
                "Semana de referência",
                value=date.today(),
                format="DD/MM/YYYY",
            )

        inicio_semana, fim_semana = obter_intervalo_semana(
            referencia_semana
        )

        renderizar_html(
            f"""
            <div class="semana-periodo">
                Semana de
                {inicio_semana.strftime("%d/%m/%Y")}
                até
                {fim_semana.strftime("%d/%m/%Y")}
            </div>
            """
        )

        compromissos = listar_compromissos(
            responsavel_id=integrante_selecionado,
            data_inicio=inicio_semana,
            data_fim=fim_semana,
            apenas_ativos=True,
        )

        if not compromissos:
            st.info(
                "Este integrante não possui compromissos "
                "com prazo nesta semana."
            )

        else:
            total = len(compromissos)

            programados = sum(
                1
                for item in compromissos
                if item["status"] == "Programado"
            )

            entregues = sum(
                1
                for item in compromissos
                if item["status"] == "Entregue"
            )

            nao_entregues = sum(
                1
                for item in compromissos
                if item["status"] == "Não entregue"
            )

            coluna_1, coluna_2, coluna_3, coluna_4 = (
                st.columns(4)
            )

            coluna_1.metric(
                "Compromissos",
                total,
            )

            coluna_2.metric(
                "Programados",
                programados,
            )

            coluna_3.metric(
                "Entregues",
                entregues,
            )

            coluna_4.metric(
                "Não entregues",
                nao_entregues,
            )

            st.write("")

            for compromisso in compromissos:
                status = compromisso["status"]

                if status == "Entregue":
                    classe_status = "selo-entregue"

                elif status == "Não entregue":
                    classe_status = "selo-nao-entregue"

                else:
                    classe_status = "selo-programado"

                prioridade_titulo = (
                    compromisso["prioridade_titulo"]
                    or "Sem vínculo com prioridade"
                )

                renderizar_html(
                    f"""
                    <div class="item-gestao">
                        <div class="item-titulo">
                            {escape(compromisso["titulo"])}

                            <span class="selo {classe_status}">
                                {escape(status.upper())}
                            </span>
                        </div>

                        <div class="item-resultado">
                            <strong>Resultado esperado:</strong>
                            {escape(compromisso["resultado_esperado"])}
                        </div>

                        <div class="item-detalhes">
                            <strong>Prioridade:</strong>
                            {escape(prioridade_titulo)}
                            &nbsp; · &nbsp;

                            <strong>Prazo:</strong>
                            {formatar_data(compromisso["data_prazo"])}
                            &nbsp; · &nbsp;

                            <strong>Origem:</strong>
                            {escape(compromisso["origem"])}
                        </div>
                    </div>
                    """
                )

                if compromisso["observacao"]:
                    with st.expander(
                        f'Observações — {compromisso["titulo"]}'
                    ):
                        st.write(
                            compromisso["observacao"]
                        )


# ============================================================
# ENTREGÁVEIS D-1 — PAINEL GERAL
# ============================================================

def pagina_entregaveis_d1():
    # Quando o card é acionado por um link, a própria URL preserva o modo
    # reunião mesmo que o navegador reconstrua a sessão do Streamlit.
    if st.query_params.get("modo_reuniao") == "1":
        st.session_state["modo_reuniao_d1"] = True

    cabecalho(
        "Controle coletivo",
        "Entregáveis D-1",
        (
            "Timeline, calendário mensal e baixa das entregas da equipe. "
            "Verde significa entregue e vermelho significa não entregue."
        ),
    )

    integrantes = listar_integrantes(apenas_ativos=True)
    prioridades = listar_prioridades(apenas_ativas=True)

    if not integrantes:
        st.warning("Cadastre pelo menos um integrante ativo antes de usar o painel D-1.")
        return

    nomes = {item["id"]: item["nome"] for item in integrantes}
    opcoes_prioridade = {None: "Sem vínculo com prioridade"}
    opcoes_prioridade.update({item["id"]: item["titulo"] for item in prioridades})

    @st.dialog("Adicionar entrega ao painel")
    def abrir_cadastro_entrega():
        st.caption(
            "Preencha os dados abaixo. Ao salvar, a entrega será posicionada "
            "automaticamente na timeline ou na swimlane semanal."
        )
        titulo_novo = st.text_input(
            "Nome da entrega *",
            placeholder="Ex.: Enviar relatório de produção",
            key="modal_titulo_entrega",
        )
        responsavel_novo = st.selectbox(
            "Responsável *",
            options=list(nomes.keys()),
            format_func=lambda item: nomes[item],
            key="modal_responsavel_entrega",
        )
        coluna_data, coluna_horario = st.columns(2)
        with coluna_data:
            data_nova = st.date_input(
                "Data de início *",
                value=date.today(),
                format="DD/MM/YYYY",
                key="modal_data_entrega",
            )
        with coluna_horario:
            horario_novo = st.text_input(
                "Horário limite",
                placeholder="Ex.: 17:00",
                key="modal_horario_entrega",
            )

        periodicidade_nova = st.selectbox(
            "Repetição *",
            ["Pontual", "Diária", "Semanal", "Mensal"],
            help="Pontual aparece em uma data. Diária e semanal alimentam as swimlanes.",
            key="modal_periodicidade_entrega",
        )

        data_fim_nova = data_nova
        dias_novos = []
        dia_mes_novo = data_nova.day
        if periodicidade_nova != "Pontual":
            data_fim_nova = st.date_input(
                "Repetir até *",
                value=data_nova + timedelta(days=90),
                min_value=data_nova,
                format="DD/MM/YYYY",
                key="modal_fim_entrega",
            )
        if periodicidade_nova == "Semanal":
            dias_novos = st.multiselect(
                "Dias da semana *",
                ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"],
                key="modal_dias_entrega",
            )
        if periodicidade_nova == "Mensal":
            dia_mes_novo = st.number_input(
                "Dia do mês *",
                min_value=1,
                max_value=31,
                value=data_nova.day,
                key="modal_dia_mes_entrega",
            )

        with st.expander("Informações complementares"):
            prioridade_nova = st.selectbox(
                "Prioridade relacionada",
                options=list(opcoes_prioridade.keys()),
                format_func=lambda item: opcoes_prioridade[item],
                key="modal_prioridade_entrega",
            )
            descricao_nova = st.text_area(
                "Descrição ou critério de aceite",
                key="modal_descricao_entrega",
            )

        if st.button(
            "Salvar e adicionar ao painel",
            type="primary",
            use_container_width=True,
            key="modal_salvar_entrega",
        ):
            if not titulo_novo.strip():
                st.error("Informe o nome da entrega.")
            elif periodicidade_nova == "Semanal" and not dias_novos:
                st.error("Selecione pelo menos um dia da semana.")
            else:
                sucesso, mensagem = cadastrar_modelo_entregavel(
                    prioridade_nova,
                    responsavel_novo,
                    titulo_novo,
                    descricao_nova,
                    periodicidade_nova,
                    data_nova,
                    data_fim_nova,
                    dias_novos,
                    int(dia_mes_novo),
                    horario_novo,
                )
                if sucesso:
                    st.session_state["mensagem_entrega_criada"] = mensagem
                    st.rerun()
                else:
                    st.error(mensagem)

    @st.dialog("Excluir entrega do painel")
    def abrir_exclusao_entrega():
        modelos_disponiveis = listar_modelos(apenas_ativos=False)
        if not modelos_disponiveis:
            st.info("Não existem entregas cadastradas para excluir.")
            return
        modelos_por_id = {item["id"]: item for item in modelos_disponiveis}
        modelo_excluir_id = st.selectbox(
            "Selecione a entrega *",
            options=list(modelos_por_id.keys()),
            format_func=lambda item: (
                f'{modelos_por_id[item]["titulo"]} · '
                f'{modelos_por_id[item]["responsavel_nome"]} · '
                f'{modelos_por_id[item]["periodicidade"]}'
            ),
            key="modelo_excluir_d1",
        )
        modelo_excluir = modelos_por_id[modelo_excluir_id]
        total_ocorrencias = contar_ocorrencias_modelo(modelo_excluir_id)
        st.warning(
            f'Você excluirá definitivamente “{modelo_excluir["titulo"]}” e '
            f'{total_ocorrencias} ocorrência(s) vinculada(s), incluindo baixas já realizadas.'
        )
        confirmar_exclusao = st.checkbox(
            "Confirmo que desejo excluir permanentemente esta entrega.",
            key="confirmar_exclusao_d1",
        )
        if st.button(
            "Excluir definitivamente",
            type="primary",
            disabled=not confirmar_exclusao,
            use_container_width=True,
            key="executar_exclusao_d1",
        ):
            sucesso, mensagem = excluir_modelo_entregavel(modelo_excluir_id)
            if sucesso:
                st.session_state["mensagem_entrega_excluida"] = mensagem
                st.rerun()
            st.error(mensagem)

    @st.dialog("Adicionar prioridade do dia")
    def abrir_cadastro_acao():
        st.caption("Registre uma ação objetiva, com responsável, prazo e situação inicial.")
        acao_titulo = st.text_input(
            "Ação *",
            placeholder="Ex.: Consolidar retorno das medições",
            key="acao_titulo_d1",
        )
        acao_descricao = st.text_area(
            "Orientação ou resultado esperado",
            key="acao_descricao_d1",
        )
        coluna_responsavel, coluna_prazo = st.columns(2)
        with coluna_responsavel:
            acao_responsavel = st.selectbox(
                "Responsável *",
                options=list(nomes.keys()),
                format_func=lambda item: nomes[item],
                key="acao_responsavel_d1",
            )
        with coluna_prazo:
            acao_prazo = st.date_input(
                "Prazo *",
                value=date.today(),
                format="DD/MM/YYYY",
                key="acao_prazo_d1",
            )
        acao_status = st.selectbox(
            "Status inicial *",
            ["A planejar", "Em andamento", "Concluído"],
            key="acao_status_d1",
        )
        if st.button(
            "Adicionar ao plano de ação",
            type="primary",
            use_container_width=True,
            key="salvar_acao_d1",
        ):
            sucesso, mensagem = cadastrar_aviso(
                "Bullet point",
                acao_titulo,
                acao_descricao,
                date.today(),
                None,
                acao_responsavel,
                acao_prazo,
                acao_status,
                "Normal",
            )
            if sucesso:
                st.session_state["mensagem_comunicacao_d1"] = mensagem
                st.rerun()
            st.error(mensagem)

    @st.dialog("Adicionar novo aviso")
    def abrir_cadastro_aviso():
        st.caption("Classifique o aviso para facilitar a leitura rápida durante o DMS.")
        aviso_titulo = st.text_input(
            "Título *",
            placeholder="Ex.: Indisponibilidade do sistema",
            key="aviso_titulo_d1",
        )
        aviso_descricao = st.text_area("Descrição *", key="aviso_descricao_d1")
        coluna_nivel, coluna_validade = st.columns(2)
        with coluna_nivel:
            aviso_criticidade = st.selectbox(
                "Classificação *",
                ["Normal", "Atenção", "Crítico"],
                key="aviso_criticidade_d1",
            )
        with coluna_validade:
            aviso_fim = st.date_input(
                "Exibir até *",
                value=date.today() + timedelta(days=7),
                min_value=date.today(),
                format="DD/MM/YYYY",
                key="aviso_fim_d1",
            )
        if st.button(
            "Publicar aviso",
            type="primary",
            use_container_width=True,
            key="salvar_novo_aviso_d1",
        ):
            sucesso, mensagem = cadastrar_aviso(
                "Aviso",
                aviso_titulo,
                aviso_descricao,
                date.today(),
                aviso_fim,
                None,
                None,
                "A planejar",
                aviso_criticidade,
            )
            if sucesso:
                st.session_state["mensagem_comunicacao_d1"] = mensagem
                st.rerun()
            st.error(mensagem)

    @st.dialog("Atualizar ação")
    def abrir_status_acao(acao):
        st.markdown(f"**{acao['titulo']}**")
        st.caption("Atualize somente a situação para manter o DMS rápido e objetivo.")
        opcoes_status = ["A planejar", "Em andamento", "Concluído"]
        status_atual = (acao.get("status") or "A planejar").replace(
            "Pendente", "A planejar"
        )
        novo_status = st.selectbox(
            "Status *",
            opcoes_status,
            index=opcoes_status.index(status_atual) if status_atual in opcoes_status else 0,
            key=f"status_acao_{acao['id']}",
        )
        if st.button(
            "Salvar status",
            type="primary",
            use_container_width=True,
            key=f"salvar_status_acao_{acao['id']}",
        ):
            sucesso, mensagem = atualizar_status_acao(acao["id"], novo_status)
            if sucesso:
                st.session_state["mensagem_comunicacao_d1"] = mensagem
                st.rerun()
            st.error(mensagem)

    @st.dialog("Confirmar entrega")
    def abrir_baixa_entrega(entregas_disponiveis):
        st.caption(
            "Baixa rápida para o DMS. Registre a referência da evidência; "
            "ela só precisa ser aberta na reunião quando houver exceção ou dúvida."
        )
        rotulos_baixa = {
            item["id"]: (
                f"{formatar_data(item['data_prevista'])} · "
                f"{item['titulo']} · {item['status'] or 'Aguardando baixa'}"
            )
            for item in entregas_disponiveis
        }
        ocorrencia_selecionada = st.selectbox(
            "Entrega *",
            options=list(rotulos_baixa.keys()),
            format_func=lambda item: rotulos_baixa[item],
            key="modal_ocorrencia_baixa",
        )
        entrega = next(
            item for item in entregas_disponiveis
            if item["id"] == ocorrencia_selecionada
        )
        indice_resultado = 1 if entrega["status"] == "Não entregue" else 0
        resultado_novo = st.radio(
            "Resultado *",
            ["Entregue", "Não entregue"],
            index=indice_resultado,
            horizontal=True,
            key=f"modal_resultado_{ocorrencia_selecionada}",
        )
        registrado_por = st.selectbox(
            "Registrado por *",
            options=list(nomes.keys()),
            format_func=lambda item: nomes[item],
            key="modal_registrado_por",
        )
        evidencia_nova = st.text_input(
            "Referência da evidência",
            value=entrega["evidencia"] or "",
            placeholder="Link, nome do arquivo, protocolo ou local de armazenamento",
            help="Não é necessário abrir a evidência durante o DMS, salvo quando houver dúvida.",
            key=f"modal_evidencia_{ocorrencia_selecionada}",
        )
        justificativa_nova = ""
        if resultado_novo == "Não entregue":
            justificativa_nova = st.text_area(
                "Motivo da não entrega *",
                value=entrega["justificativa"] or "",
                placeholder="Registre o impedimento de forma objetiva.",
                key=f"modal_justificativa_{ocorrencia_selecionada}",
            )
        st.info(
            "No DMS: confirmar status, responsável e impedimento. "
            "A análise detalhada da evidência fica para tratamento posterior."
        )
        coluna_cancelar, coluna_confirmar = st.columns([1, 2])
        with coluna_cancelar:
            if st.button("Cancelar", use_container_width=True, key="cancelar_baixa_card"):
                st.rerun()
        with coluna_confirmar:
            if st.button(
                "Confirmar baixa",
                type="primary",
                use_container_width=True,
                key="confirmar_baixa_card",
            ):
                sucesso, mensagem = confirmar_entregavel(
                    ocorrencia_selecionada,
                    resultado_novo,
                    registrado_por,
                    evidencia_nova,
                    justificativa_nova,
                )
                if sucesso:
                    st.session_state["mensagem_baixa_criada"] = mensagem
                    st.rerun()
                else:
                    st.error(mensagem)

    if st.session_state.get("modo_reuniao_d1", False):
        renderizar_html(
            """
            <style>
                [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
                header[data-testid="stHeader"] { display:none !important; }
                .block-container { max-width:100% !important; padding:1rem 1.4rem 2rem !important; }
                .d1-hero { display:none !important; }
            </style>
            """
        )

    renderizar_html(
        f"""
        <style>
            .d1-hero {{
                padding: 24px 28px; border-radius: 20px;
                background: linear-gradient(125deg, #203B2A 0%, #31533C 100%);
                color: #FFFFFF; margin: 4px 0 22px 0;
                box-shadow: 0 14px 34px {sombra}; position: relative; overflow: hidden;
            }}
            .d1-hero::after {{
                content: ""; position: absolute; width: 170px; height: 170px;
                border: 28px solid rgba(213,169,40,.17); border-radius: 50%;
                right: -60px; top: -85px;
            }}
            .d1-kicker {{ color:#E5B52A; font-size:.76rem; font-weight:800;
                letter-spacing:.12em; text-transform:uppercase; margin-bottom:7px; }}
            .d1-hero-title {{ font-size:1.42rem; font-weight:760; margin-bottom:5px; }}
            .d1-hero-text {{ color:#DCE7DF; font-size:.94rem; max-width:840px; }}
            .d1-section {{ font-size:1.05rem; font-weight:750; color:{titulo};
                margin:25px 0 12px; display:flex; align-items:center; gap:9px; }}
            .d1-section::before {{ content:""; width:5px; height:20px;
                background:#D5A928; border-radius:5px; display:block; }}
            .d1-summary {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px;
                margin:15px 0 10px; }}
            .d1-summary-card {{ background:{superficie}; border:1px solid {borda};
                border-radius:16px; padding:17px 19px; box-shadow:0 8px 20px {sombra}; }}
            .d1-summary-label {{ color:{texto_suave}; font-size:.74rem; font-weight:800;
                letter-spacing:.07em; text-transform:uppercase; }}
            .d1-summary-value {{ color:{titulo}; font-size:1.75rem; font-weight:800; margin-top:3px; }}
            .d1-summary-card.ok {{ border-top:4px solid #2F855A; }}
            .d1-summary-card.bad {{ border-top:4px solid #C74646; }}
            .d1-summary-card.gold {{ border-top:4px solid #D5A928; }}
            .swim-board {{ overflow-x:auto; border:1px solid {borda}; border-radius:18px;
                background:{superficie}; box-shadow:0 10px 26px {sombra}; margin-bottom:18px; }}
            .swim-band {{ min-width:1080px; padding:16px 18px 22px; }}
            .swim-titlebar {{ display:flex; justify-content:space-between; align-items:center;
                background:#263F30; color:#FFF; border-radius:10px; padding:9px 14px;
                font-size:.76rem; font-weight:850; letter-spacing:.09em; text-transform:uppercase; }}
            .month-axis {{ display:grid; gap:0; align-items:start; margin-top:18px; position:relative; }}
            .month-axis::before {{ content:""; position:absolute; left:0; right:0; top:20px;
                height:3px; background:#263F30; border-radius:3px; }}
            .month-column {{ position:relative; min-height:230px; padding:0 7px; text-align:center; }}
            .month-column::before {{ content:""; position:absolute; left:50%; top:20px; bottom:0;
                border-left:2px dashed #AAB3AC; opacity:.8; }}
            .month-date {{ position:relative; z-index:2; display:inline-flex; width:42px; height:42px;
                align-items:center; justify-content:center; background:#173023; color:#FFF;
                border:4px solid {superficie}; border-radius:50%; font-weight:850; font-size:.78rem; }}
            .month-stack {{ position:relative; z-index:2; margin-top:15px; display:flex;
                flex-direction:column; gap:7px; align-items:stretch; }}
            .lane-card {{ border-radius:8px; padding:8px 7px; color:#FFF; font-size:.7rem;
                font-weight:750; line-height:1.25; box-shadow:0 4px 10px {sombra};
                position:relative; padding-right:31px; }}
            .lane-person {{ display:block; opacity:.82; font-size:.61rem; font-weight:600; margin-top:3px; }}
            .week-axis {{ min-width:1080px; display:grid; grid-template-columns:210px repeat(7,1fr);
                position:relative; margin-top:14px; }}
            .week-head {{ padding:10px 7px; text-align:center; color:{titulo}; font-size:.7rem;
                font-weight:850; border-bottom:2px solid #263F30; }}
            .week-head:first-child {{ text-align:left; }}
            .week-label {{ padding:10px 12px; border-top:1px solid {borda}; color:{titulo};
                font-size:.72rem; font-weight:750; display:flex; flex-direction:column; justify-content:center; }}
            .week-label small {{ color:{texto_suave}; font-weight:500; margin-top:3px; }}
            .week-cell {{ min-height:54px; border-left:1px dashed #AAB3AC;
                border-top:1px solid {borda}; padding:7px 4px; }}
            .week-block {{ min-height:38px; border-radius:7px; color:#FFF; font-size:.65rem;
                font-weight:750; padding:6px; display:flex; align-items:center; justify-content:center;
                text-align:center; box-shadow:0 3px 8px {sombra}; position:relative; padding-right:28px; }}
            .card-check {{ position:absolute; right:6px; top:50%; transform:translateY(-50%);
                width:21px; height:21px; display:flex; align-items:center; justify-content:center;
                border:1.5px solid rgba(255,255,255,.88); border-radius:5px; color:#FFF !important;
                text-decoration:none !important; font-size:.74rem; font-weight:900;
                background:rgba(0,0,0,.16); transition:.15s ease; }}
            .card-check:hover {{ background:#FFF; color:#173023 !important; transform:translateY(-50%) scale(1.08); }}
            .card-check.ok {{ background:#2F855A; border-color:#8FE0AD; color:#FFF !important; }}
            .card-check.bad {{ background:#C74646; border-color:#FFB0B0; color:#FFF !important; }}
            .card-check.pending {{ background:transparent; color:transparent !important; }}
            .swim-empty {{ color:{texto_suave}; padding:28px; text-align:center; font-size:.85rem; }}
            .d1-calendar-wrap {{ overflow-x:auto; border:1px solid {borda};
                border-radius:16px; background:{superficie}; box-shadow:0 8px 22px {sombra}; }}
            table.d1-calendar {{ border-collapse:separate; border-spacing:0; min-width:1250px;
                width:100%; font-size:.75rem; }}
            .d1-calendar th {{ background:#263F30; color:#FFF; padding:11px 7px;
                text-align:center; position:sticky; top:0; z-index:2; }}
            .d1-calendar th:first-child {{ text-align:left; position:sticky; left:0; z-index:4; min-width:190px; }}
            .d1-calendar td {{ border-top:1px solid {borda}; border-right:1px solid {borda};
                padding:10px 6px; text-align:center; color:{texto}; min-width:34px; }}
            .d1-calendar td:first-child {{ position:sticky; left:0; z-index:3;
                background:{superficie}; text-align:left; min-width:190px; font-weight:700; color:{titulo}; }}
            .d1-cell {{ width:17px; height:17px; border-radius:5px; margin:auto; }}
            .d1-cell.ok {{ background:#2F855A; }} .d1-cell.bad {{ background:#C74646; }}
            .d1-cell.wait {{ border:2px solid #A8B0AA; background:transparent; }}
            .d1-note {{ background:{superficie}; border:1px solid {borda}; border-radius:14px;
                padding:14px 16px; margin-bottom:10px; box-shadow:0 5px 14px {sombra}; }}
            .d1-note-type {{ color:#D5A928; font-size:.68rem; font-weight:850;
                letter-spacing:.08em; text-transform:uppercase; }}
            .d1-note-title {{ color:{titulo}; font-weight:750; margin:3px 0; }}
            .d1-note-text {{ color:{texto}; font-size:.82rem; line-height:1.45; }}
            .action-card {{ background:{superficie}; border:1px solid {borda};
                border-left:5px solid #D5A928; border-radius:14px; padding:14px 17px;
                margin:8px 0 4px; box-shadow:0 5px 14px {sombra}; }}
            .action-card.overdue {{ border-left-color:#C74646; background:rgba(199,70,70,.07); }}
            .action-card.progress {{ border-left-color:#377DB7; }}
            .action-card.done {{ border-left-color:#2F855A; }}
            .action-title {{ color:{titulo}; font-size:.95rem; font-weight:800; margin-bottom:5px; }}
            .action-desc {{ color:{texto}; font-size:.79rem; line-height:1.4; margin-bottom:9px; }}
            .action-meta {{ display:flex; flex-wrap:wrap; gap:8px 18px; color:{texto_suave};
                font-size:.73rem; }}
            .action-status {{ display:inline-flex; border-radius:999px; padding:3px 9px;
                font-size:.66rem; font-weight:850; text-transform:uppercase; letter-spacing:.05em; }}
            .action-status.pending {{ color:#8A6810; background:rgba(213,169,40,.18); }}
            .action-status.progress {{ color:#2B6598; background:rgba(54,125,183,.16); }}
            .action-status.overdue {{ color:#A83232; background:rgba(199,70,70,.16); }}
            .action-status.done {{ color:#247348; background:rgba(47,133,90,.16); }}
            .kanban-head {{ display:flex; align-items:center; justify-content:space-between;
                border-radius:11px; padding:11px 13px; margin-bottom:10px; border-top:4px solid #D5A928;
                background:rgba(213,169,40,.08); color:{titulo}; }}
            .kanban-head.progress {{ border-top-color:#377DB7; background:rgba(55,125,183,.08); }}
            .kanban-head.done {{ border-top-color:#2F855A; background:rgba(47,133,90,.08); }}
            .kanban-head span {{ display:block; color:{texto_suave}; font-size:.62rem;
                font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
            .kanban-head strong {{ display:block; font-size:.92rem; margin-top:2px; }}
            .kanban-head > b {{ display:flex; align-items:center; justify-content:center;
                width:29px; height:29px; border-radius:50%; background:{superficie};
                border:1px solid {borda}; font-size:.78rem; }}
            .kanban-empty {{ min-height:78px; display:flex; align-items:center; justify-content:center;
                color:{texto_suave}; font-size:.76rem; text-align:center; }}
            .notice-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:13px; }}
            .notice-card {{ background:{superficie}; border:1px solid {borda}; border-top:5px solid #2F855A;
                border-radius:15px; padding:15px 17px; box-shadow:0 5px 14px {sombra}; }}
            .notice-card.attention {{ border-top-color:#D5A928; }}
            .notice-card.critical {{ border-top-color:#C74646; }}
            .notice-level {{ font-size:.66rem; font-weight:850; letter-spacing:.07em;
                text-transform:uppercase; margin-bottom:5px; }}
            .notice-card.normal .notice-level {{ color:#2F855A; }}
            .notice-card.attention .notice-level {{ color:#B88D16; }}
            .notice-card.critical .notice-level {{ color:#C74646; }}
            .notice-title {{ color:{titulo}; font-weight:800; margin-bottom:5px; }}
            .notice-text {{ color:{texto}; font-size:.8rem; line-height:1.45; }}
            .notice-date {{ color:{texto_suave}; font-size:.7rem; margin-top:10px; }}
            @media(max-width:900px) {{
                .d1-summary {{ grid-template-columns:repeat(2,1fr); }}
                .notice-grid {{ grid-template-columns:1fr; }}
            }}
        </style>
        <div class="d1-hero">
            <div class="d1-kicker">CENTRAL DE CONTROLE DA EQUIPE</div>
            <div class="d1-hero-title">Uma leitura rápida do que deveria acontecer e do que foi entregue.</div>
            <div class="d1-hero-text">Use este painel na rotina D-1 para visualizar o mês, registrar as baixas e direcionar os pontos que exigem ação.</div>
        </div>
        """
    )

    aba_painel, aba_editar = st.tabs(
        ["Visão executiva", "Editar cronograma"]
    )

    with aba_painel:
        acao_esquerda, acao_adicionar, acao_excluir, acao_expandir = st.columns(
            [2.7, 1.2, 1.15, 1.2]
        )
        with acao_esquerda:
            if "mensagem_entrega_criada" in st.session_state:
                st.success(st.session_state.pop("mensagem_entrega_criada"))
            if "mensagem_baixa_criada" in st.session_state:
                st.success(st.session_state.pop("mensagem_baixa_criada"))
            if "mensagem_entrega_excluida" in st.session_state:
                st.success(st.session_state.pop("mensagem_entrega_excluida"))
        with acao_adicionar:
            if st.button(
                "＋ Adicionar entrega",
                type="primary",
                use_container_width=True,
                key="abrir_modal_entrega",
            ):
                abrir_cadastro_entrega()
        with acao_excluir:
            if st.button(
                "Excluir entrega",
                use_container_width=True,
                key="abrir_exclusao_entrega_d1",
            ):
                abrir_exclusao_entrega()
        with acao_expandir:
            modo_reuniao = st.session_state.get("modo_reuniao_d1", False)
            texto_modo = "↙ Sair da expansão" if modo_reuniao else "⛶ Expandir painel"
            if st.button(texto_modo, use_container_width=True, key="alternar_modo_reuniao"):
                st.session_state["modo_reuniao_d1"] = not modo_reuniao
                if not modo_reuniao:
                    st.session_state["filtro_responsavel_d1"] = None
                st.rerun()

        filtro_1, filtro_2 = st.columns([1, 2])
        with filtro_1:
            mes_referencia = st.date_input(
                "Mês de referência",
                value=date.today().replace(day=1),
                format="DD/MM/YYYY",
                key="mes_painel_d1",
            )
        with filtro_2:
            responsavel_filtro = st.selectbox(
                "Integrante",
                options=[None] + list(nomes.keys()),
                format_func=lambda item: "Toda a equipe" if item is None else nomes[item],
                key="filtro_responsavel_d1",
            )

        gerar_ocorrencias_mes(mes_referencia.year, mes_referencia.month)
        ocorrencias = listar_ocorrencias_mes(
            mes_referencia.year,
            mes_referencia.month,
            responsavel_filtro,
        )
        avisos = listar_avisos(date.today())

        baixa_parametro = st.query_params.get("baixa")
        modelo_parametro = st.query_params.get("modelo_baixa")
        dia_parametro = st.query_params.get("dia_semana")
        entregas_para_baixa = []
        try:
            if baixa_parametro:
                baixa_id = int(baixa_parametro)
                entregas_para_baixa = [
                    item for item in ocorrencias if item["id"] == baixa_id
                ]
            elif modelo_parametro:
                modelo_baixa_id = int(modelo_parametro)
                entregas_para_baixa = [
                    item for item in ocorrencias
                    if item["modelo_id"] == modelo_baixa_id
                    and (
                        dia_parametro is None
                        or date.fromisoformat(item["data_prevista"]).weekday() == int(dia_parametro)
                    )
                ]
        except (TypeError, ValueError):
            entregas_para_baixa = []

        if baixa_parametro or modelo_parametro:
            st.query_params.clear()
            if entregas_para_baixa:
                abrir_baixa_entrega(entregas_para_baixa)
            else:
                st.warning("Não foi possível localizar essa entrega no período selecionado.")

        total = len(ocorrencias)
        entregues = sum(item["status"] == "Entregue" for item in ocorrencias)
        nao_entregues = sum(item["status"] == "Não entregue" for item in ocorrencias)
        pendentes = total - entregues - nao_entregues
        avaliadas = entregues + nao_entregues
        cumprimento = (entregues / avaliadas * 100) if avaliadas else 0

        renderizar_html(
            f"""
            <div class="d1-summary">
                <div class="d1-summary-card gold"><div class="d1-summary-label">Programadas</div><div class="d1-summary-value">{total}</div></div>
                <div class="d1-summary-card ok"><div class="d1-summary-label">Entregues</div><div class="d1-summary-value">{entregues}</div></div>
                <div class="d1-summary-card bad"><div class="d1-summary-label">Não entregues</div><div class="d1-summary-value">{nao_entregues}</div></div>
                <div class="d1-summary-card"><div class="d1-summary-label">Cumprimento</div><div class="d1-summary-value">{cumprimento:.0f}%</div></div>
            </div>
            """
        )

        modelos = listar_modelos(apenas_ativos=True)
        inicio_mes = mes_referencia.replace(day=1)
        fim_mes = mes_referencia.replace(
            day=monthrange(mes_referencia.year, mes_referencia.month)[1]
        )
        modelos = [
            modelo for modelo in modelos
            if (responsavel_filtro is None or modelo["responsavel_id"] == responsavel_filtro)
            and date.fromisoformat(modelo["data_inicio"]) <= fim_mes
            and (not modelo["data_fim"] or date.fromisoformat(modelo["data_fim"]) >= inicio_mes)
        ]

        paleta = ["#173F2B", "#163D75", "#6F3498", "#0797BD", "#D5A400", "#2D8B62", "#8A3E3E", "#44505B"]
        responsaveis_ids = sorted({modelo["responsavel_id"] for modelo in modelos})
        cores = {identificador: paleta[indice % len(paleta)] for indice, identificador in enumerate(responsaveis_ids)}
        preservar_expansao = "&amp;modo_reuniao=1" if st.session_state.get("modo_reuniao_d1", False) else ""

        def estado_caixa(status):
            if status == "Entregue":
                return "ok", "✓"
            if status == "Não entregue":
                return "bad", "×"
            return "pending", ""

        renderizar_html('<div class="d1-section">Linha do tempo e swimlanes</div>')

        entregas_pontuais = [
            item for item in ocorrencias
            if item["periodicidade"] in {"Pontual", "Mensal"}
        ]
        por_data = {}
        for item in entregas_pontuais:
            por_data.setdefault(item["data_prevista"], []).append(item)

        if por_data:
            colunas_mes = []
            for data_iso, itens in sorted(por_data.items()):
                data_item = date.fromisoformat(data_iso)
                cartoes = []
                for item in itens:
                    cor = cores.get(item["responsavel_id"], "#44505B")
                    classe_caixa, simbolo_caixa = estado_caixa(item["status"])
                    cartoes.append(
                        f'<div class="lane-card" style="background:{cor}" title="{escape(item["titulo"])}">'
                        f'{escape(item["titulo"])}'
                        f'<span class="lane-person">{escape(item["responsavel_nome"])}</span>'
                        f'<a class="card-check {classe_caixa}" '
                        f'href="?pagina=entregaveis_d1&amp;baixa={item["id"]}{preservar_expansao}" target="_top" '
                        f'title="Confirmar ou revisar esta entrega">{simbolo_caixa}</a></div>'
                    )
                colunas_mes.append(
                    f'<div class="month-column"><div class="month-date">{data_item.day:02d}</div>'
                    f'<div class="month-stack">{"".join(cartoes)}</div></div>'
                )
            renderizar_html(
                f'<div class="swim-board"><div class="swim-band">'
                f'<div class="swim-titlebar"><span>Entregas com data específica</span>'
                f'<span>{inicio_mes.strftime("%m/%Y")}</span></div>'
                f'<div class="month-axis" style="grid-template-columns:repeat({len(colunas_mes)}, minmax(145px,1fr))">'
                f'{"".join(colunas_mes)}</div></div></div>'
            )

        recorrentes = [modelo for modelo in modelos if modelo["periodicidade"] in {"Diária", "Semanal"}]
        if recorrentes:
            dias_rotulo = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
            dias_indice = {
                "Segunda": 0, "Terça": 1, "Quarta": 2, "Quinta": 3,
                "Sexta": 4, "Sábado": 5, "Domingo": 6,
            }
            ocorrencias_modelo = {}
            for item in ocorrencias:
                ocorrencias_modelo.setdefault(item["modelo_id"], []).append(item)

            cabecalhos = '<div class="week-head">Atividade recorrente</div>' + "".join(
                f'<div class="week-head">{dia}</div>' for dia in dias_rotulo
            )
            linhas_semana = []
            for modelo in recorrentes:
                if modelo["periodicidade"] == "Diária":
                    dias_ativos = set(range(7))
                else:
                    dias_ativos = {
                        dias_indice[nome_dia]
                        for nome_dia in (modelo["dias_semana"] or "").split(",")
                        if nome_dia in dias_indice
                    }
                cor = cores.get(modelo["responsavel_id"], "#44505B")
                celulas = []
                for indice_dia in range(7):
                    if indice_dia not in dias_ativos:
                        celulas.append('<div class="week-cell"></div>')
                        continue
                    itens_dia = sorted(
                        [
                            item for item in ocorrencias_modelo.get(modelo["id"], [])
                            if date.fromisoformat(item["data_prevista"]).weekday() == indice_dia
                        ],
                        key=lambda item: item["data_prevista"],
                    )
                    avaliadas_dia = [item for item in itens_dia if item["status"]]
                    ultimo_resultado = avaliadas_dia[-1]["status"] if avaliadas_dia else None
                    status, simbolo_caixa = estado_caixa(ultimo_resultado)
                    celulas.append(
                        f'<div class="week-cell"><div class="week-block" style="background:{cor}" '
                        f'title="{escape(modelo["titulo"])} — {escape(modelo["responsavel_nome"])}">'
                        f'{escape(modelo["titulo"])}'
                        f'<a class="card-check {status}" '
                        f'href="?pagina=entregaveis_d1&amp;modelo_baixa={modelo["id"]}&amp;dia_semana={indice_dia}{preservar_expansao}" '
                        f'target="_top" title="Selecionar a data e confirmar a entrega">{simbolo_caixa}</a></div></div>'
                    )
                linhas_semana.append(
                    f'<div class="week-label">{escape(modelo["titulo"])}'
                    f'<small>{escape(modelo["responsavel_nome"])} · {escape(modelo["horario_limite"] or "Sem horário")}</small></div>'
                    f'{"".join(celulas)}'
                )
            renderizar_html(
                f'<div class="swim-board"><div class="swim-band">'
                f'<div class="swim-titlebar"><span>Entregas recorrentes</span><span>Visão semanal</span></div>'
                f'<div class="week-axis">{cabecalhos}{"".join(linhas_semana)}</div></div></div>'
            )

        if not por_data and not recorrentes:
            st.info("Nenhum entregável ativo foi encontrado para este período.")

        renderizar_html('<div class="d1-section">Calendário geral de baixas</div>')
        if ocorrencias:
            ultimo_dia = monthrange(mes_referencia.year, mes_referencia.month)[1]
            linhas = {}
            for item in ocorrencias:
                chave = (item["responsavel_id"], item["responsavel_nome"], item["cargo"] or "—")
                if chave not in linhas:
                    linhas[chave] = {dia: [] for dia in range(1, ultimo_dia + 1)}
                dia = date.fromisoformat(item["data_prevista"]).day
                linhas[chave][dia].append(item["status"])
            cabecalho_dias = "".join(f"<th>{dia}</th>" for dia in range(1, ultimo_dia + 1))
            corpo = []
            for (_, nome, cargo), dias in linhas.items():
                celulas = []
                for dia in range(1, ultimo_dia + 1):
                    estados = dias[dia]
                    if not estados:
                        conteudo = ""
                    elif "Não entregue" in estados:
                        conteudo = '<div class="d1-cell bad" title="Não entregue"></div>'
                    elif all(estado == "Entregue" for estado in estados):
                        conteudo = '<div class="d1-cell ok" title="Entregue"></div>'
                    else:
                        conteudo = '<div class="d1-cell wait" title="Aguardando baixa"></div>'
                    celulas.append(f"<td>{conteudo}</td>")
                corpo.append(
                    f'<tr><td>{escape(nome)}<br><small>{escape(cargo)}</small></td>{"".join(celulas)}</tr>'
                )
            renderizar_html(
                f'<div class="d1-calendar-wrap"><table class="d1-calendar"><thead><tr><th>Participante</th>{cabecalho_dias}</tr></thead><tbody>{"".join(corpo)}</tbody></table></div>'
            )
            st.caption("Contorno: aguardando baixa · Verde: entregue · Vermelho: não entregue")
        else:
            st.info("O calendário será preenchido após o cadastro dos entregáveis.")

        renderizar_html('<div class="d1-section">Desempenho por participante</div>')
        participantes_grafico = (
            [nomes[responsavel_filtro]]
            if responsavel_filtro is not None
            else [item["nome"] for item in integrantes]
        )
        contagem_grafico = {
            (participante, resultado): 0
            for participante in participantes_grafico
            for resultado in ["Entregue", "Não entregue"]
        }
        for item in ocorrencias:
            if item["status"] in {"Entregue", "Não entregue"}:
                chave = (item["responsavel_nome"], item["status"])
                if chave in contagem_grafico:
                    contagem_grafico[chave] += 1

        metas_grafico = {
            participante: sum(
                1
                for item in ocorrencias
                if item["responsavel_nome"] == participante
            )
            for participante in participantes_grafico
        }

        dados_grafico = pd.DataFrame(
            [
                {
                    "Participante": participante,
                    "Resultado": resultado,
                    "Quantidade": quantidade,
                }
                for (participante, resultado), quantidade in contagem_grafico.items()
            ]
        )
        dados_meta = pd.DataFrame(
            [
                {"Participante": participante, "Meta": meta}
                for participante, meta in metas_grafico.items()
            ]
        )
        maior_quantidade = max(
            dados_grafico["Quantidade"].max(),
            dados_meta["Meta"].max(),
            1,
        )

        with st.container(border=True):
            st.markdown("**Entregas confirmadas x meta programada**")
            st.caption(
                "Cada meta corresponde ao total de entregas previstas para o integrante no período."
            )
            eixo_participantes = alt.Axis(
                labelAngle=0,
                labelAlign="center",
                labelBaseline="top",
                labelLimit=170,
                labelPadding=14,
                domain=False,
                ticks=False,
                title=None,
            )
            escala_quantidade = alt.Scale(domain=[0, maior_quantidade + 1])
            base_grafico = alt.Chart(dados_grafico).encode(
                x=alt.X(
                    "Participante:N",
                    title=None,
                    sort=participantes_grafico,
                    axis=eixo_participantes,
                ),
                xOffset=alt.XOffset(
                    "Resultado:N",
                    sort=["Entregue", "Não entregue"],
                ),
                y=alt.Y(
                    "Quantidade:Q",
                    title=None,
                    scale=escala_quantidade,
                    axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False),
                ),
                color=alt.Color(
                    "Resultado:N",
                    scale=alt.Scale(
                        domain=["Entregue", "Não entregue"],
                        range=["#2F855A", "#C74646"],
                    ),
                    legend=alt.Legend(
                        title=None,
                        orient="top",
                        direction="horizontal",
                        symbolType="square",
                    ),
                ),
                tooltip=[
                    alt.Tooltip("Participante:N", title="Integrante"),
                    alt.Tooltip("Resultado:N", title="Resultado"),
                    alt.Tooltip("Quantidade:Q", title="Quantidade", format=".0f"),
                ],
            )
            colunas = base_grafico.mark_bar(
                cornerRadiusTopLeft=7,
                cornerRadiusTopRight=7,
                size=30,
            )
            rotulos = base_grafico.mark_text(
                dy=-9,
                fontSize=13,
                fontWeight="bold",
                color=texto,
            ).encode(
                text=alt.Text("Quantidade:Q", format=".0f")
            )
            base_meta = alt.Chart(dados_meta).encode(
                x=alt.X(
                    "Participante:N",
                    title=None,
                    sort=participantes_grafico,
                    axis=eixo_participantes,
                ),
                y=alt.Y(
                    "Meta:Q",
                    title=None,
                    scale=escala_quantidade,
                    axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False),
                ),
                tooltip=[
                    alt.Tooltip("Participante:N", title="Integrante"),
                    alt.Tooltip("Meta:Q", title="Meta programada", format=".0f"),
                ],
            )
            linha_meta = base_meta.mark_line(
                color="#D5A928",
                strokeWidth=2.5,
                strokeDash=[7, 5],
                point=alt.OverlayMarkDef(
                    filled=True,
                    fill="#D5A928",
                    stroke=superficie,
                    strokeWidth=2,
                    size=75,
                ),
            )
            rotulos_meta = (
                base_meta.transform_calculate(
                    RotuloMeta="'Meta ' + datum.Meta"
                )
                .mark_text(
                    dy=-14,
                    fontSize=11,
                    fontWeight="bold",
                    color="#D5A928",
                )
                .encode(text="RotuloMeta:N")
            )
            grafico = (
                (colunas + rotulos + linha_meta + rotulos_meta)
                .properties(height=360, background=superficie)
                .configure_view(strokeOpacity=0)
                .configure_axis(
                    labelColor=texto,
                    titleColor=texto,
                    domain=False,
                    ticks=False,
                    grid=False,
                )
                .configure_legend(labelColor=texto)
            )
            st.altair_chart(grafico, use_container_width=True)
            renderizar_html(
                '<div style="display:flex;align-items:center;gap:10px;margin-top:-8px;'
                f'color:{texto_suave};font-size:.86rem;">'
                '<span style="display:inline-block;width:34px;border-top:2px dashed #D5A928;"></span>'
                'Meta programada individual</div>'
            )

        acoes_dia = [item for item in avisos if item["tipo"] == "Bullet point"]
        itens_avisos = [item for item in avisos if item["tipo"] == "Aviso"]

        titulo_acoes, botao_acoes = st.columns([4, 1.2])
        with titulo_acoes:
            renderizar_html('<div class="d1-section">Prioridades do dia · Plano de ação</div>')
        with botao_acoes:
            st.write("")
            if st.button(
                "＋ Adicionar ação",
                type="primary",
                use_container_width=True,
                key="abrir_acao_d1",
            ):
                abrir_cadastro_acao()

        if "mensagem_comunicacao_d1" in st.session_state:
            st.success(st.session_state.pop("mensagem_comunicacao_d1"))

        if acoes_dia:
            colunas_kanban = st.columns(3, gap="medium")
            configuracao_kanban = [
                ("A planejar", "planning", "Planejamento"),
                ("Em andamento", "progress", "Execução"),
                ("Concluído", "done", "Finalizado"),
            ]
            for coluna_kanban, (status_coluna, classe_coluna, subtitulo) in zip(
                colunas_kanban, configuracao_kanban
            ):
                acoes_coluna = [
                    acao
                    for acao in acoes_dia
                    if (acao.get("status") or "A planejar").replace("Pendente", "A planejar")
                    == status_coluna
                ]
                with coluna_kanban:
                    with st.container(border=True):
                        renderizar_html(
                            f'<div class="kanban-head {classe_coluna}">'
                            f'<div><span>{subtitulo}</span><strong>{status_coluna}</strong></div>'
                            f'<b>{len(acoes_coluna)}</b></div>'
                        )
                        if not acoes_coluna:
                            renderizar_html('<div class="kanban-empty">Nenhuma ação nesta etapa</div>')
                        for acao in acoes_coluna:
                            status_original = status_coluna
                            prazo_acao = None
                            if acao.get("prazo"):
                                try:
                                    prazo_acao = date.fromisoformat(acao["prazo"])
                                except ValueError:
                                    prazo_acao = None
                            atrasada = (
                                prazo_acao is not None
                                and prazo_acao < date.today()
                                and status_original != "Concluído"
                            )
                            status_exibicao = "Atrasado" if atrasada else status_original
                            classe_card = (
                                "overdue" if atrasada
                                else "done" if status_original == "Concluído"
                                else "progress" if status_original == "Em andamento"
                                else ""
                            )
                            classe_status = {
                                "A planejar": "pending",
                                "Em andamento": "progress",
                                "Concluído": "done",
                                "Atrasado": "overdue",
                            }[status_exibicao]
                            nome_responsavel = nomes.get(
                                acao.get("responsavel_id"), "Responsável não informado"
                            )
                            prazo_formatado = (
                                prazo_acao.strftime("%d/%m/%Y") if prazo_acao else "Não informado"
                            )
                            renderizar_html(
                                f'<div class="action-card {classe_card}">'
                                f'<div class="action-title">{escape(acao["titulo"])}</div>'
                                f'<div class="action-desc">{escape(acao.get("descricao") or "Sem orientação complementar.")}</div>'
                                f'<div class="action-meta"><span><b>Responsável</b><br>{escape(nome_responsavel)}</span>'
                                f'<span><b>Prazo</b><br>{prazo_formatado}</span></div>'
                                f'<div style="margin-top:9px"><span class="action-status {classe_status}">{status_exibicao}</span></div></div>'
                            )
                            if st.button(
                                "Mover / atualizar",
                                use_container_width=True,
                                key=f"editar_status_{acao['id']}",
                            ):
                                abrir_status_acao(acao)
        else:
            st.info("Nenhuma prioridade do dia cadastrada.")

        with st.expander("Histórico de ações concluídas", expanded=False):
            filtro_hist_1, filtro_hist_2, filtro_hist_3 = st.columns([1, 1, 1.4])
            with filtro_hist_1:
                historico_inicio = st.date_input(
                    "Conclusões desde",
                    value=date.today() - timedelta(days=30),
                    format="DD/MM/YYYY",
                    key="historico_acoes_inicio",
                )
            with filtro_hist_2:
                historico_fim = st.date_input(
                    "Conclusões até",
                    value=date.today(),
                    min_value=historico_inicio,
                    format="DD/MM/YYYY",
                    key="historico_acoes_fim",
                )
            with filtro_hist_3:
                historico_responsavel = st.selectbox(
                    "Responsável",
                    options=[None] + list(nomes.keys()),
                    format_func=lambda item: "Toda a equipe" if item is None else nomes[item],
                    key="historico_acoes_responsavel",
                )
            historico_acoes = listar_historico_acoes(
                historico_inicio,
                historico_fim,
                historico_responsavel,
            )
            if historico_acoes:
                dados_historico = []
                for item in historico_acoes:
                    conclusao_texto = item.get("concluido_em") or item.get("atualizado_em") or ""
                    try:
                        conclusao_formatada = date.fromisoformat(conclusao_texto[:10]).strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        conclusao_formatada = conclusao_texto[:10]
                    prazo_texto = item.get("prazo") or ""
                    try:
                        prazo_formatado = date.fromisoformat(prazo_texto[:10]).strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        prazo_formatado = prazo_texto[:10] or "Não informado"
                    dados_historico.append(
                        {
                            "Conclusão": conclusao_formatada,
                            "Ação": item["titulo"],
                            "Responsável": item.get("responsavel_nome") or "Não informado",
                            "Prazo": prazo_formatado,
                            "Status": "Concluído",
                        }
                    )
                st.dataframe(
                    pd.DataFrame(dados_historico),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("Nenhuma ação concluída nos filtros selecionados.")

        titulo_avisos, botao_avisos = st.columns([4, 1.2])
        with titulo_avisos:
            renderizar_html('<div class="d1-section">Avisos da equipe</div>')
        with botao_avisos:
            st.write("")
            if st.button(
                "＋ Novo aviso",
                type="primary",
                use_container_width=True,
                key="abrir_aviso_d1",
            ):
                abrir_cadastro_aviso()

        if itens_avisos:
            cards_avisos = []
            for aviso in itens_avisos:
                nivel = aviso.get("criticidade") or "Normal"
                classe = {"Normal": "normal", "Atenção": "attention", "Crítico": "critical"}.get(nivel, "normal")
                data_fim_texto = "Sem data final"
                if aviso.get("data_fim"):
                    try:
                        data_fim_texto = f'Visível até {date.fromisoformat(aviso["data_fim"]).strftime("%d/%m/%Y")}'
                    except ValueError:
                        data_fim_texto = f'Visível até {escape(aviso["data_fim"])}'
                cards_avisos.append(
                    f'<div class="notice-card {classe}"><div class="notice-level">{escape(nivel)}</div>'
                    f'<div class="notice-title">{escape(aviso["titulo"])}</div>'
                    f'<div class="notice-text">{escape(aviso.get("descricao") or "")}</div>'
                    f'<div class="notice-date">{data_fim_texto}</div></div>'
                )
            renderizar_html(f'<div class="notice-grid">{"".join(cards_avisos)}</div>')
        else:
            st.info("Nenhum aviso ativo.")

    with aba_editar:
        renderizar_html('<div class="d1-section">Editar ou inativar entregável</div>')
        todos_modelos = listar_modelos(apenas_ativos=False)
        if not todos_modelos:
            st.info("Ainda não existem entregáveis cadastrados.")
        else:
            rotulos_modelos = {
                item["id"]: (
                    f"{item['titulo']} · {item['responsavel_nome']} · "
                    f"{'Ativo' if item['ativo'] else 'Inativo'}"
                )
                for item in todos_modelos
            }
            modelo_id = st.selectbox(
                "Selecione o entregável",
                options=list(rotulos_modelos.keys()),
                format_func=lambda item: rotulos_modelos[item],
                key="modelo_edicao_d1",
            )
            modelo = buscar_modelo_por_id(modelo_id)
            periodicidades = ["Pontual", "Diária", "Semanal", "Mensal"]
            dias_disponiveis = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            dias_atuais = [
                dia for dia in (modelo["dias_semana"] or "").split(",") if dia
            ]
            inicio_atual = date.fromisoformat(modelo["data_inicio"])
            fim_atual = date.fromisoformat(modelo["data_fim"]) if modelo["data_fim"] else inicio_atual
            responsaveis_ids = list(nomes.keys())
            prioridades_ids = list(opcoes_prioridade.keys())

            with st.form("formulario_editar_entregavel"):
                editar_titulo = st.text_input("Nome do entregável *", value=modelo["titulo"])
                editar_descricao = st.text_area(
                    "Descrição ou critério de aceite",
                    value=modelo["descricao"] or "",
                )
                coluna_1, coluna_2 = st.columns(2)
                with coluna_1:
                    editar_responsavel = st.selectbox(
                        "Responsável *",
                        options=responsaveis_ids,
                        index=responsaveis_ids.index(modelo["responsavel_id"]),
                        format_func=lambda item: nomes[item],
                    )
                    editar_periodicidade = st.selectbox(
                        "Periodicidade *",
                        periodicidades,
                        index=periodicidades.index(modelo["periodicidade"]),
                    )
                    editar_prioridade = st.selectbox(
                        "Prioridade relacionada",
                        options=prioridades_ids,
                        index=prioridades_ids.index(modelo["prioridade_id"]) if modelo["prioridade_id"] in prioridades_ids else 0,
                        format_func=lambda item: opcoes_prioridade[item],
                    )
                with coluna_2:
                    editar_inicio = st.date_input("Início *", value=inicio_atual, format="DD/MM/YYYY")
                    editar_fim = st.date_input("Fim da recorrência", value=fim_atual, format="DD/MM/YYYY")
                    editar_horario = st.text_input("Horário limite", value=modelo["horario_limite"] or "")
                editar_dias = st.multiselect(
                    "Dias da semana",
                    dias_disponiveis,
                    default=dias_atuais,
                )
                editar_dia_mes = st.number_input(
                    "Dia do mês",
                    min_value=1,
                    max_value=31,
                    value=int(modelo["dia_mes"] or 1),
                )
                editar_ativo = st.checkbox("Entregável ativo", value=bool(modelo["ativo"]))
                salvar_edicao = st.form_submit_button("Salvar alterações", use_container_width=True)

            if salvar_edicao:
                fim_enviado = editar_inicio if editar_periodicidade == "Pontual" else editar_fim
                sucesso, mensagem = atualizar_modelo_entregavel(
                    modelo_id,
                    editar_prioridade,
                    editar_responsavel,
                    editar_titulo,
                    editar_descricao,
                    editar_periodicidade,
                    editar_inicio,
                    fim_enviado,
                    editar_dias,
                    int(editar_dia_mes),
                    editar_horario,
                    editar_ativo,
                )
                if sucesso:
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)

# ============================================================
# DIRECIONAMENTO
# ============================================================

def pagina_direcionamento():
    cabecalho(
        "Gestão",
        "Direcionamento da gerente",
        (
            "Definição do que é prioritário, do resultado esperado "
            "e do período de concentração dos esforços da equipe."
        ),
    )

    integrantes = listar_integrantes(
        apenas_ativos=True
    )

    opcoes_responsaveis = {
        None: "Toda a equipe"
    }

    for integrante in integrantes:
        opcoes_responsaveis[integrante["id"]] = (
            integrante["nome"]
        )

    aba_cadastrar, aba_visualizar, aba_editar = st.tabs(
        [
            "Cadastrar prioridade",
            "Prioridades da equipe",
            "Editar ou encerrar",
        ]
    )

    with aba_cadastrar:
        with st.form(
            "formulario_prioridade",
            clear_on_submit=True,
        ):
            titulo_prioridade = st.text_input(
                "Título da prioridade *"
            )

            resultado_esperado = st.text_area(
                "Resultado esperado *",
                height=120,
            )

            justificativa = st.text_area(
                "Justificativa estratégica",
                height=100,
            )

            coluna_1, coluna_2 = st.columns(2)

            with coluna_1:
                responsavel = st.selectbox(
                    "Responsável principal",
                    list(opcoes_responsaveis.keys()),
                    format_func=lambda identificador: (
                        opcoes_responsaveis[identificador]
                    ),
                )

                nivel = st.selectbox(
                    "Nível",
                    [
                        "Alta",
                        "Média",
                        "Baixa",
                    ],
                    index=1,
                )

            with coluna_2:
                inicio = st.date_input(
                    "Data de início",
                    value=date.today(),
                    format="DD/MM/YYYY",
                )

                fim = st.date_input(
                    "Data de conclusão",
                    value=date.today(),
                    format="DD/MM/YYYY",
                )

            salvar = st.form_submit_button(
                "Cadastrar prioridade",
                use_container_width=True,
            )

        if salvar:
            sucesso, mensagem = cadastrar_prioridade(
                titulo_prioridade,
                resultado_esperado,
                justificativa,
                responsavel,
                inicio,
                fim,
                nivel,
            )

            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)

    with aba_visualizar:
        mostrar_encerradas = st.checkbox(
            "Mostrar prioridades encerradas"
        )

        prioridades = listar_prioridades(
            apenas_ativas=not mostrar_encerradas
        )

        if not prioridades:
            st.info(
                "Nenhuma prioridade foi cadastrada."
            )

        for prioridade in prioridades:
            classe = (
                "selo-ativo"
                if prioridade["ativa"] == 1
                else "selo-encerrado"
            )

            situacao = (
                "ATIVA"
                if prioridade["ativa"] == 1
                else "ENCERRADA"
            )

            responsavel = (
                prioridade["responsavel_nome"]
                or "Toda a equipe"
            )

            renderizar_html(
                f"""
                <div class="item-gestao">
                    <div class="item-titulo">
                        {escape(prioridade["titulo"])}

                        <span class="selo {classe}">
                            {situacao}
                        </span>
                    </div>

                    <div class="item-resultado">
                        <strong>Resultado esperado:</strong>
                        {escape(prioridade["resultado_esperado"])}
                    </div>

                    <div class="item-detalhes">
                        <strong>Responsável:</strong>
                        {escape(responsavel)}
                        &nbsp; · &nbsp;

                        <strong>Nível:</strong>
                        {escape(prioridade["nivel_prioridade"])}
                        &nbsp; · &nbsp;

                        <strong>Período:</strong>
                        {formatar_data(prioridade["data_inicio"])}
                        até
                        {formatar_data(prioridade["data_fim"])}
                    </div>
                </div>
                """
            )

    with aba_editar:
        prioridades = listar_prioridades()

        if not prioridades:
            st.info(
                "Cadastre uma prioridade antes de editar."
            )
            return

        opcoes = {
            item["id"]: item["titulo"]
            for item in prioridades
        }

        prioridade_id = st.selectbox(
            "Selecione a prioridade",
            list(opcoes.keys()),
            format_func=lambda identificador: (
                opcoes[identificador]
            ),
        )

        prioridade = buscar_prioridade_por_id(
            prioridade_id
        )

        todos_integrantes = listar_integrantes()

        responsaveis = {
            None: "Toda a equipe"
        }

        for integrante in todos_integrantes:
            responsaveis[integrante["id"]] = (
                integrante["nome"]
            )

        ids_responsaveis = list(
            responsaveis.keys()
        )

        responsavel_atual = prioridade[
            "responsavel_id"
        ]

        indice_responsavel = (
            ids_responsaveis.index(responsavel_atual)
            if responsavel_atual in ids_responsaveis
            else 0
        )

        niveis = [
            "Alta",
            "Média",
            "Baixa",
        ]

        with st.form(
            f"editar_prioridade_{prioridade_id}"
        ):
            titulo_edicao = st.text_input(
                "Título *",
                value=prioridade["titulo"],
            )

            resultado_edicao = st.text_area(
                "Resultado esperado *",
                value=prioridade["resultado_esperado"],
                height=120,
            )

            justificativa_edicao = st.text_area(
                "Justificativa",
                value=(
                    prioridade["justificativa_estrategica"]
                    or ""
                ),
                height=100,
            )

            responsavel_edicao = st.selectbox(
                "Responsável",
                ids_responsaveis,
                index=indice_responsavel,
                format_func=lambda identificador: (
                    responsaveis[identificador]
                ),
            )

            nivel_edicao = st.selectbox(
                "Nível",
                niveis,
                index=niveis.index(
                    prioridade["nivel_prioridade"]
                ),
            )

            coluna_1, coluna_2 = st.columns(2)

            with coluna_1:
                inicio_edicao = st.date_input(
                    "Início",
                    value=date.fromisoformat(
                        prioridade["data_inicio"]
                    ),
                    format="DD/MM/YYYY",
                )

            with coluna_2:
                fim_edicao = st.date_input(
                    "Conclusão",
                    value=date.fromisoformat(
                        prioridade["data_fim"]
                    ),
                    format="DD/MM/YYYY",
                )

            ativa = st.checkbox(
                "Prioridade ativa",
                value=prioridade["ativa"] == 1,
            )

            atualizar = st.form_submit_button(
                "Salvar alterações",
                use_container_width=True,
            )

        if atualizar:
            sucesso, mensagem = atualizar_prioridade(
                prioridade_id,
                titulo_edicao,
                resultado_edicao,
                justificativa_edicao,
                responsavel_edicao,
                inicio_edicao,
                fim_edicao,
                nivel_edicao,
                ativa,
            )

            if sucesso:
                st.success(mensagem)
                st.rerun()
            else:
                st.error(mensagem)

        with st.expander(
            "Histórico da prioridade"
        ):
            historico = listar_historico_prioridade(
                prioridade_id
            )

            for registro in historico:
                st.markdown(
                    f"""
                    **{registro["acao"]}**  
                    {registro["descricao"]}  
                    `{registro["registrado_em"]}`
                    """
                )


# ============================================================
# EQUIPE
# ============================================================

def pagina_equipe():
    cabecalho(
        "Pessoas",
        "Equipe",
        (
            "Cadastro dos integrantes, responsabilidades, "
            "perfis de acesso e situação na equipe."
        ),
    )

    aba_cadastrar, aba_consultar, aba_editar = st.tabs(
        [
            "Cadastrar integrante",
            "Consultar equipe",
            "Editar ou inativar",
        ]
    )

    with aba_cadastrar:
        with st.form(
            "cadastrar_integrante",
            clear_on_submit=True,
        ):
            nome = st.text_input("Nome completo *")

            coluna_1, coluna_2 = st.columns(2)

            with coluna_1:
                email = st.text_input("E-mail")
                cargo = st.text_input("Cargo")

            with coluna_2:
                funcao = st.text_input(
                    "Função na equipe"
                )

                perfil = st.selectbox(
                    "Perfil",
                    [
                        "Integrante",
                        "Administrador",
                        "Gerente",
                    ],
                )

            salvar = st.form_submit_button(
                "Cadastrar integrante",
                use_container_width=True,
            )

        if salvar:
            sucesso, mensagem = cadastrar_integrante(
                nome,
                email,
                cargo,
                funcao,
                perfil,
            )

            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)

    with aba_consultar:
        integrantes = listar_integrantes()

        if not integrantes:
            st.info("Nenhum integrante cadastrado.")

        else:
            tabela = pd.DataFrame(
                [
                    {
                        "Nome": item["nome"],
                        "E-mail": item["email"] or "—",
                        "Cargo": item["cargo"] or "—",
                        "Função": (
                            item["funcao_equipe"]
                            or "—"
                        ),
                        "Perfil": item["perfil_acesso"],
                        "Situação": (
                            "Ativo"
                            if item["ativo"] == 1
                            else "Inativo"
                        ),
                    }
                    for item in integrantes
                ]
            )

            st.dataframe(
                tabela,
                use_container_width=True,
                hide_index=True,
            )

    with aba_editar:
        integrantes = listar_integrantes()

        if not integrantes:
            st.info("Nenhum integrante cadastrado.")
            return

        opcoes = {
            item["id"]: item["nome"]
            for item in integrantes
        }

        integrante_id = st.selectbox(
            "Selecione o integrante",
            list(opcoes.keys()),
            format_func=lambda identificador: (
                opcoes[identificador]
            ),
        )

        integrante = buscar_integrante_por_id(
            integrante_id
        )

        perfis = [
            "Integrante",
            "Administrador",
            "Gerente",
        ]

        with st.form(
            f"editar_integrante_{integrante_id}"
        ):
            nome = st.text_input(
                "Nome completo *",
                value=integrante["nome"] or "",
            )

            email = st.text_input(
                "E-mail",
                value=integrante["email"] or "",
            )

            cargo = st.text_input(
                "Cargo",
                value=integrante["cargo"] or "",
            )

            funcao = st.text_input(
                "Função na equipe",
                value=(
                    integrante["funcao_equipe"]
                    or ""
                ),
            )

            perfil = st.selectbox(
                "Perfil",
                perfis,
                index=perfis.index(
                    integrante["perfil_acesso"]
                ),
            )

            ativo = st.checkbox(
                "Integrante ativo",
                value=integrante["ativo"] == 1,
            )

            atualizar = st.form_submit_button(
                "Salvar alterações",
                use_container_width=True,
            )

        if atualizar:
            sucesso, mensagem = atualizar_integrante(
                integrante_id,
                nome,
                email,
                cargo,
                funcao,
                perfil,
                ativo,
            )

            if sucesso:
                st.success(mensagem)
                st.rerun()
            else:
                st.error(mensagem)

        with st.expander(
            "Histórico do integrante"
        ):
            historico = listar_historico_integrante(
                integrante_id
            )

            for registro in historico:
                st.markdown(
                    f"""
                    **{registro["acao"]}**  
                    {registro["descricao"]}  
                    `{registro["registrado_em"]}`
                    """
                )


# ============================================================
# AGENDA DA GERENTE
# ============================================================

def pagina_agenda_gerente():
    cabecalho(
        "Liderança",
        "Agenda da gerente",
        "Compromissos, reuniões, validações e decisões em uma visão objetiva.",
    )
    renderizar_html(
        f"""
        <style>
            .agenda-card {{ background:{superficie}; border:1px solid {borda}; border-left:5px solid #D5A928;
                border-radius:15px; padding:15px 18px; margin:8px 0; box-shadow:0 6px 16px {sombra}; }}
            .agenda-card.done {{ border-left-color:#2F855A; }}
            .agenda-card.cancel {{ border-left-color:#C74646; opacity:.75; }}
            .agenda-time {{ color:#D5A928; font-size:.75rem; font-weight:850; letter-spacing:.06em; }}
            .agenda-title {{ color:{titulo}; font-size:1rem; font-weight:800; margin:4px 0; }}
            .agenda-meta {{ color:{texto_suave}; font-size:.76rem; line-height:1.55; }}
            .agenda-objective {{ color:{texto}; font-size:.82rem; margin-top:8px; line-height:1.45; }}
            .decision-pill {{ display:inline-block; color:#A83232; background:rgba(199,70,70,.14);
                padding:3px 9px; border-radius:999px; font-size:.65rem; font-weight:850; margin-top:9px; }}
        </style>
        <div class="faixa-direcionamento">
            <div class="faixa-rotulo">ROTINA DA LIDERANÇA</div>
            <div class="faixa-titulo">Tempo protegido para decidir, alinhar e remover impedimentos.</div>
            <div class="faixa-texto">Visualize a disponibilidade corporativa da gerente e complemente a agenda com compromissos manuais.</div>
        </div>
        """
    )

    aba_agenda, aba_microsoft, aba_novo = st.tabs(
        ["Visualizar agenda", "Sincronizar Microsoft 365", "Novo compromisso"]
    )

    with aba_microsoft:
        st.subheader("Conexão com o Teams / Outlook")
        st.caption(
            "Nesta etapa, a integração importa somente data, horário e disponibilidade "
            "(Ocupado, Provisório ou Fora do escritório)."
        )
        tenant_atual = obter_configuracao("m365_tenant_id")
        cliente_atual = obter_configuracao("m365_client_id")
        gerente_atual = obter_configuracao("m365_email_gerente")
        with st.expander("Configuração da integração", expanded=not all([tenant_atual, cliente_atual, gerente_atual])):
            st.info(
                "Os IDs abaixo não são senhas. Eles identificam o diretório e o aplicativo "
                "cadastrado pela TI no Microsoft Entra."
            )
            with st.form("configuracao_microsoft"):
                tenant_id = st.text_input("ID do diretório (Tenant ID) *", value=tenant_atual)
                client_id = st.text_input("ID do aplicativo (Client ID) *", value=cliente_atual)
                email_gerente = st.text_input(
                    "E-mail corporativo da gerente *",
                    value=gerente_atual,
                    placeholder="adriany.ribeiro@amapaminerals.com",
                )
                salvar_m365 = st.form_submit_button("Salvar configuração", use_container_width=True)
            if salvar_m365:
                if not tenant_id.strip() or not client_id.strip() or "@" not in email_gerente:
                    st.error("Preencha Tenant ID, Client ID e um e-mail corporativo válido.")
                else:
                    salvar_configuracao("m365_tenant_id", tenant_id, "Diretório Microsoft Entra")
                    salvar_configuracao("m365_client_id", client_id, "Aplicativo Microsoft Entra")
                    salvar_configuracao("m365_email_gerente", email_gerente, "Agenda consultada")
                    st.success("Configuração salva.")
                    st.rerun()

        conectado, identidade = conexao_ativa(tenant_atual, cliente_atual) if tenant_atual and cliente_atual else (False, {})
        if conectado:
            nome_conectado = identidade.get("name") or identidade.get("preferred_username") or "Conta corporativa"
            st.success(f"Microsoft 365 conectado: {nome_conectado}")
        else:
            st.warning("Microsoft 365 ainda não está conectado.")

        col_conectar, col_desconectar = st.columns(2)
        with col_conectar:
            if st.button(
                "Conectar conta corporativa" if not conectado else "Reconectar conta",
                use_container_width=True,
                disabled=not (tenant_atual and cliente_atual),
            ):
                try:
                    with st.spinner("Conclua o acesso na janela da Microsoft que será aberta..."):
                        token, _ = obter_token(tenant_atual, cliente_atual, interativo=True)
                    if token:
                        st.success("Conta conectada com sucesso.")
                        st.rerun()
                except IntegracaoMicrosoftErro as erro:
                    st.error(str(erro))
        with col_desconectar:
            if st.button("Desconectar", use_container_width=True, disabled=not conectado):
                try:
                    desconectar()
                    st.rerun()
                except IntegracaoMicrosoftErro as erro:
                    st.error(str(erro))

        st.divider()
        periodo_1, periodo_2 = st.columns(2)
        hoje = date.today()
        with periodo_1:
            inicio_sync = st.date_input(
                "Sincronizar de", value=hoje.replace(day=1), format="DD/MM/YYYY", key="inicio_sync_m365"
            )
        with periodo_2:
            fim_sync = st.date_input(
                "Até", value=hoje + timedelta(days=45), format="DD/MM/YYYY", key="fim_sync_m365"
            )
        if st.button("Sincronizar disponibilidade", type="primary", use_container_width=True, disabled=not conectado):
            if fim_sync < inicio_sync:
                st.error("A data final não pode ser anterior à data inicial.")
            elif (fim_sync - inicio_sync).days > 61:
                st.error("Sincronize no máximo 62 dias por vez.")
            else:
                try:
                    token, _ = obter_token(tenant_atual, cliente_atual, interativo=False)
                    if not token:
                        st.error("A sessão expirou. Conecte novamente a conta corporativa.")
                    else:
                        with st.spinner("Consultando disponibilidade no Microsoft 365..."):
                            itens = consultar_disponibilidade(
                                token, gerente_atual, inicio_sync, fim_sync
                            )
                            sucesso, mensagem = sincronizar_eventos_microsoft(
                                itens, inicio_sync, fim_sync
                            )
                        if sucesso:
                            salvar_configuracao(
                                "m365_ultima_sincronizacao",
                                datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "Última sincronização da agenda",
                            )
                            st.success(mensagem)
                        else:
                            st.error(mensagem)
                except IntegracaoMicrosoftErro as erro:
                    st.error(str(erro))
        ultima_sync = obter_configuracao("m365_ultima_sincronizacao")
        if ultima_sync:
            st.caption(f"Última sincronização: {ultima_sync}")

    with aba_novo:
        with st.form("novo_evento_agenda", clear_on_submit=True):
            titulo_evento = st.text_input(
                "Compromisso *",
                placeholder="Ex.: DMS da equipe de Alto Desempenho",
            )
            col_1, col_2, col_3 = st.columns([1.2, 1, 1])
            with col_1:
                tipo_evento = st.selectbox(
                    "Tipo *",
                    ["Reunião", "Validação", "Decisão", "1:1", "Visita", "Outro"],
                )
                data_evento = st.date_input("Data *", value=date.today(), format="DD/MM/YYYY")
            with col_2:
                inicio_evento = st.time_input("Início *", value=time(8, 0))
                fim_evento = st.time_input("Fim", value=time(8, 30))
            with col_3:
                decisao_evento = st.checkbox("Exige decisão da gerente")
                local_evento = st.text_input("Local ou link do Teams")
            participantes_evento = st.text_input(
                "Participantes",
                placeholder="Ex.: Equipe de Alto Desempenho, Suprimentos e Operação",
            )
            objetivo_evento = st.text_area(
                "Objetivo ou resultado esperado",
                placeholder="O que precisa sair definido deste compromisso?",
            )
            salvar_evento = st.form_submit_button("Adicionar à agenda", use_container_width=True)
        if salvar_evento:
            if fim_evento and fim_evento < inicio_evento:
                st.error("O horário final não pode ser anterior ao horário inicial.")
            else:
                sucesso, mensagem = cadastrar_evento_agenda(
                    titulo_evento,
                    tipo_evento,
                    data_evento,
                    inicio_evento.strftime("%H:%M"),
                    fim_evento.strftime("%H:%M") if fim_evento else None,
                    local_evento,
                    participantes_evento,
                    objetivo_evento,
                    decisao_evento,
                )
                if sucesso:
                    st.success(mensagem)
                else:
                    st.error(mensagem)

    with aba_agenda:
        filtro_1, filtro_2 = st.columns([1, 1.6])
        with filtro_1:
            referencia_agenda = st.date_input(
                "Data de referência",
                value=date.today(),
                format="DD/MM/YYYY",
                key="referencia_agenda_gerente",
            )
        with filtro_2:
            visao_agenda = st.radio(
                "Visualização",
                ["Dia", "Semana"],
                horizontal=True,
                key="visao_agenda_gerente",
            )
        if visao_agenda == "Dia":
            inicio_agenda = fim_agenda = referencia_agenda
        else:
            inicio_agenda = referencia_agenda - timedelta(days=referencia_agenda.weekday())
            fim_agenda = inicio_agenda + timedelta(days=6)

        eventos = listar_eventos_agenda(inicio_agenda, fim_agenda)
        eventos_hoje = listar_eventos_agenda(date.today(), date.today())
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Compromissos no período", len(eventos))
        col_b.metric("Agenda de hoje", len(eventos_hoje))
        col_c.metric(
            "Decisões pendentes",
            sum(1 for item in eventos if item["decisao_necessaria"] and item["status"] == "Agendado"),
        )

        if not eventos:
            st.info("Nenhum compromisso encontrado no período selecionado.")
        for evento in eventos:
            classe = "done" if evento["status"] == "Realizado" else "cancel" if evento["status"] == "Cancelado" else ""
            data_formatada = date.fromisoformat(evento["data_evento"]).strftime("%d/%m/%Y")
            decisao_html = '<span class="decision-pill">DECISÃO NECESSÁRIA</span>' if evento["decisao_necessaria"] else ""
            col_card, col_controle = st.columns([4.5, 1.25])
            with col_card:
                renderizar_html(
                    f'<div class="agenda-card {classe}"><div class="agenda-time">{data_formatada} · '
                    f'{escape(evento["hora_inicio"])}{("–" + escape(evento["hora_fim"])) if evento["hora_fim"] else ""}</div>'
                    f'<div class="agenda-title">{escape(evento["titulo"])}</div>'
                    f'<div class="agenda-meta">{escape(evento["tipo"])} · {escape(evento["status"])} · '
                    f'{escape(evento.get("origem") or "Manual")}'
                    f'{(" · " + escape(evento["participantes"])) if evento["participantes"] else ""}</div>'
                    f'<div class="agenda-objective">{escape(evento["objetivo"] or "Sem objetivo registrado.")}</div>'
                    f'{decisao_html}</div>'
                )
                if evento["local_link"] and str(evento["local_link"]).lower().startswith(("http://", "https://")):
                    st.link_button("Abrir reunião / link", evento["local_link"])
            with col_controle:
                if evento.get("origem") == "Microsoft 365":
                    st.caption("Sincronizado do Microsoft 365")
                    st.info("Somente disponibilidade")
                    continue
                novo_status_evento = st.selectbox(
                    "Status",
                    ["Agendado", "Realizado", "Cancelado"],
                    index=["Agendado", "Realizado", "Cancelado"].index(evento["status"]),
                    key=f"status_agenda_{evento['id']}",
                )
                if st.button("Salvar", use_container_width=True, key=f"salvar_agenda_{evento['id']}"):
                    sucesso, mensagem = atualizar_status_evento_agenda(evento["id"], novo_status_evento)
                    if sucesso:
                        st.rerun()
                    st.error(mensagem)
                with st.popover("Remover", use_container_width=True):
                    st.warning("O compromisso será retirado da agenda.")
                    if st.button("Confirmar remoção", key=f"excluir_agenda_{evento['id']}"):
                        sucesso, mensagem = excluir_evento_agenda(evento["id"])
                        if sucesso:
                            st.rerun()
                        st.error(mensagem)


# ============================================================
# INDICADORES
# ============================================================

def pagina_indicadores():
    cabecalho(
        "Performance",
        "Indicadores da equipe",
        "Leitura executiva das entregas, do cumprimento e dos pontos que exigem ação.",
    )

    referencia = st.date_input(
        "Mês de referência",
        value=date.today().replace(day=1),
        format="DD/MM/YYYY",
        key="mes_indicadores",
    )
    gerar_ocorrencias_mes(referencia.year, referencia.month)
    ocorrencias = listar_ocorrencias_mes(referencia.year, referencia.month)
    integrantes_ativos = listar_integrantes(apenas_ativos=True)

    modo_demonstracao = st.toggle(
        "Exibir dados demonstrativos",
        value=False,
        help="Simula resultados somente nesta tela, sem gravar ou alterar o banco de dados.",
        key="modo_demo_indicadores",
    )
    if modo_demonstracao:
        st.warning("MODO DEMONSTRAÇÃO — os valores abaixo são simulados e não alteram os dados reais.")
        cenarios = [
            (6, 5, 0, 1),
            (8, 6, 1, 1),
            (7, 5, 1, 1),
            (6, 6, 0, 0),
            (7, 5, 2, 0),
            (5, 4, 0, 1),
            (8, 7, 1, 0),
        ]
        ocorrencias_demo = []
        for indice, integrante in enumerate(integrantes_ativos):
            programadas, qtd_entregues, qtd_nao_entregues, qtd_aguardando = cenarios[indice % len(cenarios)]
            status_demo = (
                ["Entregue"] * qtd_entregues
                + ["Não entregue"] * qtd_nao_entregues
                + [None] * qtd_aguardando
            )
            status_demo += [None] * max(0, programadas - len(status_demo))
            for numero, status in enumerate(status_demo, start=1):
                ocorrencias_demo.append(
                    {
                        "responsavel_id": integrante["id"],
                        "status": status,
                        "data_prevista": date(
                            referencia.year,
                            referencia.month,
                            min(numero, monthrange(referencia.year, referencia.month)[1]),
                        ).isoformat(),
                    }
                )
        ocorrencias = ocorrencias_demo

    total = len(ocorrencias)
    entregues = sum(item["status"] == "Entregue" for item in ocorrencias)
    nao_entregues = sum(item["status"] == "Não entregue" for item in ocorrencias)
    aguardando = sum(item["status"] is None for item in ocorrencias)
    avaliadas = entregues + nao_entregues
    cumprimento = (entregues / avaliadas * 100) if avaliadas else 0
    ultimo_dia = monthrange(referencia.year, referencia.month)[1]
    fim_mes = date(referencia.year, referencia.month, ultimo_dia)
    limite_d1 = min(date.today() - timedelta(days=1), fim_mes)
    vencidas_sem_baixa = sum(
        item["status"] is None and date.fromisoformat(item["data_prevista"]) <= limite_d1
        for item in ocorrencias
    ) if referencia.replace(day=1) <= limite_d1 else 0

    renderizar_html(
        f"""
        <style>
            .ind-grid {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:14px; margin:18px 0 28px; }}
            .ind-card {{ background:{superficie}; border:1px solid {borda}; border-radius:16px;
                padding:17px 18px; box-shadow:0 7px 18px {sombra}; }}
            .ind-card.green {{ border-top:4px solid #2F855A; }}
            .ind-card.red {{ border-top:4px solid #C74646; }}
            .ind-card.gold {{ border-top:4px solid #D5A928; }}
            .ind-label {{ color:{texto_suave}; font-size:.66rem; font-weight:850; letter-spacing:.1em; }}
            .ind-value {{ color:{titulo}; font-size:1.75rem; font-weight:900; margin-top:8px; }}
            .ind-note {{ color:{texto_suave}; font-size:.68rem; margin-top:3px; }}
            .section-title {{ color:{titulo}; font-size:1.08rem; font-weight:850; margin:28px 0 13px;
                border-left:5px solid #D5A928; padding-left:11px; }}
            @media(max-width:1000px) {{ .ind-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
        </style>
        <div class="ind-grid">
            <div class="ind-card gold"><div class="ind-label">PROGRAMADAS</div><div class="ind-value">{total}</div><div class="ind-note">no mês</div></div>
            <div class="ind-card green"><div class="ind-label">ENTREGUES</div><div class="ind-value">{entregues}</div><div class="ind-note">baixas verdes</div></div>
            <div class="ind-card red"><div class="ind-label">NÃO ENTREGUES</div><div class="ind-value">{nao_entregues}</div><div class="ind-note">baixas vermelhas</div></div>
            <div class="ind-card"><div class="ind-label">CUMPRIMENTO</div><div class="ind-value">{cumprimento:.0f}%</div><div class="ind-note">sobre as avaliadas</div></div>
            <div class="ind-card {'red' if vencidas_sem_baixa else ''}"><div class="ind-label">D-1 PENDENTE</div><div class="ind-value">{vencidas_sem_baixa}</div><div class="ind-note">vencidas sem baixa</div></div>
        </div>
        """
    )

    nomes = [item["nome"] for item in integrantes_ativos]
    desempenho = []
    for integrante in integrantes_ativos:
        itens = [item for item in ocorrencias if item["responsavel_id"] == integrante["id"]]
        e = sum(item["status"] == "Entregue" for item in itens)
        n = sum(item["status"] == "Não entregue" for item in itens)
        a = sum(item["status"] is None for item in itens)
        base = e + n
        desempenho.append(
            {
                "Integrante": integrante["nome"],
                "Programadas": len(itens),
                "Entregues": e,
                "Não entregues": n,
                "Aguardando": a,
                "Cumprimento": round(e / base * 100, 1) if base else 0,
            }
        )

    renderizar_html('<div class="section-title">Desempenho por integrante</div>')
    if nomes and total:
        dados_grafico = pd.DataFrame(desempenho).melt(
            id_vars=["Integrante", "Programadas"],
            value_vars=["Entregues", "Não entregues"],
            var_name="Resultado",
            value_name="Quantidade",
        )
        barras = (
            alt.Chart(dados_grafico)
            .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, size=24)
            .encode(
                x=alt.X("Integrante:N", sort=nomes, title=None, axis=alt.Axis(labelAngle=0, labelLimit=150, ticks=False, domain=False)),
                xOffset=alt.XOffset("Resultado:N"),
                y=alt.Y("Quantidade:Q", title=None, axis=None),
                color=alt.Color(
                    "Resultado:N",
                    scale=alt.Scale(domain=["Entregues", "Não entregues"], range=["#2F855A", "#C74646"]),
                    legend=alt.Legend(title=None, orient="top"),
                ),
                tooltip=["Integrante:N", "Resultado:N", "Quantidade:Q", "Programadas:Q"],
            )
        )
        rotulos = barras.mark_text(dy=-10, fontWeight="bold", fontSize=13).encode(
            text=alt.Text("Quantidade:Q")
        )
        metas = (
            alt.Chart(pd.DataFrame(desempenho))
            .mark_line(color="#D5A928", strokeDash=[6, 5], point=alt.OverlayMarkDef(color="#D5A928", size=45))
            .encode(
                x=alt.X("Integrante:N", sort=nomes),
                y=alt.Y("Programadas:Q"),
                tooltip=["Integrante:N", alt.Tooltip("Programadas:Q", title="Meta")],
            )
        )
        st.altair_chart(
            (barras + rotulos + metas).properties(height=335).configure_view(strokeWidth=0).configure_axis(grid=False),
            use_container_width=True,
        )
        st.caption("Linha dourada pontilhada: total de entregas programadas para cada integrante no mês.")
    elif not nomes:
        st.info("Cadastre integrantes ativos para visualizar o desempenho.")
    else:
        renderizar_html(
            f"""
            <div style="background:{superficie};border:1px dashed {borda};border-radius:16px;
                        padding:42px 24px;text-align:center;box-shadow:0 7px 18px {sombra};">
                <div style="color:{titulo};font-size:1.05rem;font-weight:850;">Nenhuma entrega programada neste mês</div>
                <div style="color:{texto_suave};font-size:.82rem;margin-top:8px;">
                    Cadastre entregáveis para formar os indicadores ou ative os dados demonstrativos acima.
                </div>
            </div>
            """
        )

    renderizar_html('<div class="section-title">Resumo executivo</div>')
    if desempenho:
        tabela = pd.DataFrame(desempenho)
        tabela["Cumprimento"] = tabela["Cumprimento"].map(lambda valor: f"{valor:.0f}%")
        st.dataframe(tabela, use_container_width=True, hide_index=True)

    inicio_mes = referencia.replace(day=1)
    acoes_concluidas = listar_historico_acoes(inicio_mes, fim_mes)
    prioridades_ativas = listar_prioridades(apenas_ativas=True)
    if modo_demonstracao:
        acoes_concluidas = [None] * 9
        prioridades_ativas = [None] * 3
    col_acao, col_prioridade, col_aguardando = st.columns(3)
    col_acao.metric("Ações concluídas", len(acoes_concluidas))
    col_prioridade.metric("Prioridades ativas", len(prioridades_ativas))
    col_aguardando.metric("Entregas aguardando baixa", aguardando)


# ============================================================
# PÁGINA EM CONSTRUÇÃO
# ============================================================

def pagina_em_construcao(
    rotulo,
    titulo_pagina,
    subtitulo,
):
    cabecalho(
        rotulo,
        titulo_pagina,
        subtitulo,
    )

    st.info(
        "Este módulo será desenvolvido "
        "em uma etapa posterior."
    )


# ============================================================
# NAVEGAÇÃO
# ============================================================

if pagina == "Início":
    pagina_inicio()

elif pagina == "Direcionamento":
    pagina_direcionamento()

elif pagina == "Minha semana":
    pagina_minha_semana()

elif pagina == "Equipe":
    pagina_equipe()

elif pagina == "Entregáveis D-1":
    pagina_entregaveis_d1()

elif pagina == "Agenda da gerente":
    pagina_agenda_gerente()

elif pagina == "Indicadores":
    pagina_indicadores()
