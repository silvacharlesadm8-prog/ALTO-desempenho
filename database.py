from pathlib import Path
import os
import sqlite3

try:
    import sqlitecloud
except ImportError:
    sqlitecloud = None


# ============================================================
# CAMINHOS
# ============================================================

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_PROJETO / "dados"
CAMINHO_BANCO = PASTA_DADOS / "sge_geo.db"


def _obter_url_nuvem():
    """Obtém a conexão permanente sem expor a credencial no código."""
    url = os.getenv("SQLITECLOUD_URL", "").strip()
    if url:
        return url

    try:
        import streamlit as st

        return str(st.secrets.get("SQLITECLOUD_URL", "")).strip()
    except Exception:
        return ""


def usando_banco_nuvem():
    return bool(_obter_url_nuvem())


INTEGRITY_ERROR = (
    sqlite3.IntegrityError,
    *((sqlitecloud.IntegrityError,) if sqlitecloud is not None else ()),
)

DATABASE_ERROR = (
    sqlite3.Error,
    *((sqlitecloud.Error,) if sqlitecloud is not None else ()),
)


# ============================================================
# CONEXÃO
# ============================================================

def conectar_banco():
    url_nuvem = _obter_url_nuvem()

    if url_nuvem:
        if sqlitecloud is None:
            raise RuntimeError(
                "Banco permanente configurado, mas a dependência sqlitecloud "
                "não foi instalada. Execute: pip install -r requirements.txt"
            )

        conexao = sqlitecloud.connect(url_nuvem)
        conexao.row_factory = sqlitecloud.Row
        conexao.execute("PRAGMA foreign_keys = ON;")
        return conexao

    PASTA_DADOS.mkdir(
        parents=True,
        exist_ok=True,
    )

    conexao = sqlite3.connect(
        CAMINHO_BANCO,
        timeout=30,
    )

    conexao.row_factory = sqlite3.Row

    conexao.execute("PRAGMA foreign_keys = ON;")
    conexao.execute("PRAGMA journal_mode = WAL;")
    conexao.execute("PRAGMA busy_timeout = 30000;")

    return conexao


# ============================================================
# UTILITÁRIOS
# ============================================================

def normalizar_texto(valor):
    if valor is None:
        return None

    valor = str(valor).strip()

    return valor if valor else None


def converter_linha(linha):
    return dict(linha) if linha is not None else None


# ============================================================
# CRIAÇÃO DAS TABELAS
# ============================================================

def criar_tabelas(conexao):
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS integrantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT,
            cargo TEXT,
            funcao_equipe TEXT,
            perfil_acesso TEXT NOT NULL DEFAULT 'Integrante',
            ativo INTEGER NOT NULL DEFAULT 1
                CHECK (ativo IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS prioridades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            resultado_esperado TEXT NOT NULL,
            justificativa_estrategica TEXT,
            responsavel_id INTEGER,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL,
            nivel_prioridade TEXT NOT NULL DEFAULT 'Média'
                CHECK (
                    nivel_prioridade IN (
                        'Alta',
                        'Média',
                        'Baixa'
                    )
                ),
            ativa INTEGER NOT NULL DEFAULT 1
                CHECK (ativa IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (responsavel_id)
                REFERENCES integrantes(id)
                ON UPDATE CASCADE
                ON DELETE SET NULL
        );
        """
    )

    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integrante_id INTEGER,
            modulo TEXT NOT NULL,
            acao TEXT NOT NULL,
            descricao TEXT,
            registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (integrante_id)
                REFERENCES integrantes(id)
                ON UPDATE CASCADE
                ON DELETE SET NULL
        );
        """
    )

    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS historico_prioridades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prioridade_id INTEGER NOT NULL,
            acao TEXT NOT NULL,
            descricao TEXT,
            registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (prioridade_id)
                REFERENCES prioridades(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )

    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT,
            descricao TEXT,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS agenda_gerente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            data_evento TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fim TEXT,
            local_link TEXT,
            participantes TEXT,
            objetivo TEXT,
            status TEXT NOT NULL DEFAULT 'Agendado',
            decisao_necessaria INTEGER NOT NULL DEFAULT 0 CHECK (decisao_necessaria IN (0, 1)),
            origem TEXT NOT NULL DEFAULT 'Manual',
            ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def criar_indices(conexao):
    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_integrantes_nome
        ON integrantes(nome);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_integrantes_ativo
        ON integrantes(ativo);
        """
    )

    conexao.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_integrantes_email_unico
        ON integrantes(LOWER(email))
        WHERE email IS NOT NULL
          AND TRIM(email) <> '';
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_prioridades_ativa
        ON prioridades(ativa);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_prioridades_periodo
        ON prioridades(data_inicio, data_fim);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_prioridades_responsavel
        ON prioridades(responsavel_id);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_historico_integrante
        ON historico(integrante_id);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_historico_prioridade
        ON historico_prioridades(prioridade_id);
        """
    )


def inserir_configuracoes_iniciais(conexao):
    configuracoes = [
        (
            "nome_sistema",
            "ALTO DESEMPENHO",
            "Nome apresentado no aplicativo",
        ),
        (
            "versao_sistema",
            "0.17",
            "Versão atual da aplicação",
        ),
        (
            "regra_entregavel",
            "Entregue ou Não entregue",
            "Regra binária de avaliação dos entregáveis",
        ),
        (
            "metodologia_acompanhamento",
            "D-1",
            "Período de confirmação dos entregáveis",
        ),
    ]

    conexao.executemany(
        """
        INSERT OR IGNORE INTO configuracoes (
            chave,
            valor,
            descricao
        )
        VALUES (?, ?, ?);
        """,
        configuracoes,
    )

    conexao.execute(
        """
        UPDATE configuracoes
        SET
            valor = '0.17',
            atualizado_em = CURRENT_TIMESTAMP
        WHERE chave = 'versao_sistema';
        """
    )


def inicializar_banco():
    with conectar_banco() as conexao:
        criar_tabelas(conexao)
        colunas_agenda = {
            linha["name"]
            for linha in conexao.execute("PRAGMA table_info(agenda_gerente);").fetchall()
        }
        if "chave_externa" not in colunas_agenda:
            conexao.execute("ALTER TABLE agenda_gerente ADD COLUMN chave_externa TEXT;")
        criar_indices(conexao)
        conexao.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_agenda_chave_externa_total "
            "ON agenda_gerente(chave_externa);"
        )
        inserir_configuracoes_iniciais(conexao)
        conexao.commit()


# ============================================================
# HISTÓRICO
# ============================================================

def registrar_historico(
    conexao,
    integrante_id,
    modulo,
    acao,
    descricao,
):
    conexao.execute(
        """
        INSERT INTO historico (
            integrante_id,
            modulo,
            acao,
            descricao
        )
        VALUES (?, ?, ?, ?);
        """,
        (
            integrante_id,
            modulo,
            acao,
            descricao,
        ),
    )


def registrar_historico_prioridade(
    conexao,
    prioridade_id,
    acao,
    descricao,
):
    conexao.execute(
        """
        INSERT INTO historico_prioridades (
            prioridade_id,
            acao,
            descricao
        )
        VALUES (?, ?, ?);
        """,
        (
            prioridade_id,
            acao,
            descricao,
        ),
    )


# ============================================================
# INTEGRANTES — CADASTRO
# ============================================================

def cadastrar_integrante(
    nome,
    email,
    cargo,
    funcao_equipe,
    perfil_acesso,
):
    nome = normalizar_texto(nome)
    email = normalizar_texto(email)
    cargo = normalizar_texto(cargo)
    funcao_equipe = normalizar_texto(funcao_equipe)
    perfil_acesso = normalizar_texto(perfil_acesso)

    if not nome:
        return False, "Informe o nome do integrante."

    if email:
        email = email.lower()

    if perfil_acesso not in {
        "Gerente",
        "Administrador",
        "Integrante",
    }:
        return False, "Perfil de acesso inválido."

    try:
        with conectar_banco() as conexao:
            cursor = conexao.execute(
                """
                INSERT INTO integrantes (
                    nome,
                    email,
                    cargo,
                    funcao_equipe,
                    perfil_acesso,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?, 1);
                """,
                (
                    nome,
                    email,
                    cargo,
                    funcao_equipe,
                    perfil_acesso,
                ),
            )

            integrante_id = cursor.lastrowid

            registrar_historico(
                conexao,
                integrante_id,
                "Equipe",
                "Cadastro",
                f"Integrante cadastrado: {nome}.",
            )

            conexao.commit()

        return True, "Integrante cadastrado com sucesso."

    except sqlite3.IntegrityError as erro:
        if "email" in str(erro).lower():
            return False, "Este e-mail já está cadastrado."

        return False, "Não foi possível cadastrar o integrante."

    except Exception as erro:
        return False, f"Erro inesperado: {erro}"


# ============================================================
# INTEGRANTES — CONSULTA
# ============================================================

def listar_integrantes(apenas_ativos=False):
    consulta = """
        SELECT
            id,
            nome,
            email,
            cargo,
            funcao_equipe,
            perfil_acesso,
            ativo,
            criado_em,
            atualizado_em
        FROM integrantes
    """

    parametros = []

    if apenas_ativos:
        consulta += " WHERE ativo = ?"
        parametros.append(1)

    consulta += """
        ORDER BY
            ativo DESC,
            nome COLLATE NOCASE ASC;
    """

    with conectar_banco() as conexao:
        linhas = conexao.execute(
            consulta,
            parametros,
        ).fetchall()

    return [dict(linha) for linha in linhas]


def buscar_integrante_por_id(integrante_id):
    with conectar_banco() as conexao:
        linha = conexao.execute(
            """
            SELECT
                id,
                nome,
                email,
                cargo,
                funcao_equipe,
                perfil_acesso,
                ativo,
                criado_em,
                atualizado_em
            FROM integrantes
            WHERE id = ?;
            """,
            (integrante_id,),
        ).fetchone()

    return converter_linha(linha)


# ============================================================
# INTEGRANTES — ATUALIZAÇÃO
# ============================================================

def atualizar_integrante(
    integrante_id,
    nome,
    email,
    cargo,
    funcao_equipe,
    perfil_acesso,
    ativo,
):
    nome = normalizar_texto(nome)
    email = normalizar_texto(email)
    cargo = normalizar_texto(cargo)
    funcao_equipe = normalizar_texto(funcao_equipe)
    perfil_acesso = normalizar_texto(perfil_acesso)

    if not nome:
        return False, "Informe o nome do integrante."

    if email:
        email = email.lower()

    if perfil_acesso not in {
        "Gerente",
        "Administrador",
        "Integrante",
    }:
        return False, "Perfil de acesso inválido."

    try:
        with conectar_banco() as conexao:
            existente = conexao.execute(
                """
                SELECT id
                FROM integrantes
                WHERE id = ?;
                """,
                (integrante_id,),
            ).fetchone()

            if existente is None:
                return False, "Integrante não encontrado."

            conexao.execute(
                """
                UPDATE integrantes
                SET
                    nome = ?,
                    email = ?,
                    cargo = ?,
                    funcao_equipe = ?,
                    perfil_acesso = ?,
                    ativo = ?,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    nome,
                    email,
                    cargo,
                    funcao_equipe,
                    perfil_acesso,
                    1 if ativo else 0,
                    integrante_id,
                ),
            )

            situacao = "Ativo" if ativo else "Inativo"

            registrar_historico(
                conexao,
                integrante_id,
                "Equipe",
                "Atualização",
                (
                    f"Cadastro atualizado: {nome}. "
                    f"Situação definida como {situacao}."
                ),
            )

            conexao.commit()

        return True, "Cadastro atualizado com sucesso."

    except sqlite3.IntegrityError as erro:
        if "email" in str(erro).lower():
            return False, "Este e-mail já está cadastrado."

        return False, "Não foi possível atualizar o integrante."

    except Exception as erro:
        return False, f"Erro inesperado: {erro}"


def listar_historico_integrante(integrante_id):
    with conectar_banco() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                id,
                modulo,
                acao,
                descricao,
                registrado_em
            FROM historico
            WHERE integrante_id = ?
            ORDER BY id DESC;
            """,
            (integrante_id,),
        ).fetchall()

    return [dict(linha) for linha in linhas]


# ============================================================
# PRIORIDADES — CADASTRO
# ============================================================

def cadastrar_prioridade(
    titulo,
    resultado_esperado,
    justificativa_estrategica,
    responsavel_id,
    data_inicio,
    data_fim,
    nivel_prioridade,
):
    titulo = normalizar_texto(titulo)
    resultado_esperado = normalizar_texto(
        resultado_esperado
    )
    justificativa_estrategica = normalizar_texto(
        justificativa_estrategica
    )

    if not titulo:
        return False, "Informe o título da prioridade."

    if not resultado_esperado:
        return False, "Informe o resultado esperado."

    if data_fim < data_inicio:
        return False, (
            "A data final não pode ser anterior "
            "à data inicial."
        )

    if nivel_prioridade not in {
        "Alta",
        "Média",
        "Baixa",
    }:
        return False, "Nível de prioridade inválido."

    try:
        with conectar_banco() as conexao:
            cursor = conexao.execute(
                """
                INSERT INTO prioridades (
                    titulo,
                    resultado_esperado,
                    justificativa_estrategica,
                    responsavel_id,
                    data_inicio,
                    data_fim,
                    nivel_prioridade,
                    ativa
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1);
                """,
                (
                    titulo,
                    resultado_esperado,
                    justificativa_estrategica,
                    responsavel_id,
                    str(data_inicio),
                    str(data_fim),
                    nivel_prioridade,
                ),
            )

            prioridade_id = cursor.lastrowid

            registrar_historico_prioridade(
                conexao,
                prioridade_id,
                "Cadastro",
                f"Prioridade cadastrada: {titulo}.",
            )

            conexao.commit()

        return True, "Prioridade cadastrada com sucesso."

    except Exception as erro:
        return False, f"Erro ao cadastrar prioridade: {erro}"


# ============================================================
# PRIORIDADES — CONSULTA
# ============================================================

def listar_prioridades(apenas_ativas=False):
    consulta = """
        SELECT
            p.id,
            p.titulo,
            p.resultado_esperado,
            p.justificativa_estrategica,
            p.responsavel_id,
            i.nome AS responsavel_nome,
            p.data_inicio,
            p.data_fim,
            p.nivel_prioridade,
            p.ativa,
            p.criado_em,
            p.atualizado_em
        FROM prioridades AS p

        LEFT JOIN integrantes AS i
            ON i.id = p.responsavel_id
    """

    parametros = []

    if apenas_ativas:
        consulta += " WHERE p.ativa = ?"
        parametros.append(1)

    consulta += """
        ORDER BY
            p.ativa DESC,
            CASE p.nivel_prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                WHEN 'Baixa' THEN 3
                ELSE 4
            END,
            p.data_fim ASC,
            p.titulo COLLATE NOCASE ASC;
    """

    with conectar_banco() as conexao:
        linhas = conexao.execute(
            consulta,
            parametros,
        ).fetchall()

    return [dict(linha) for linha in linhas]


def buscar_prioridade_por_id(prioridade_id):
    with conectar_banco() as conexao:
        linha = conexao.execute(
            """
            SELECT
                p.id,
                p.titulo,
                p.resultado_esperado,
                p.justificativa_estrategica,
                p.responsavel_id,
                i.nome AS responsavel_nome,
                p.data_inicio,
                p.data_fim,
                p.nivel_prioridade,
                p.ativa,
                p.criado_em,
                p.atualizado_em
            FROM prioridades AS p

            LEFT JOIN integrantes AS i
                ON i.id = p.responsavel_id

            WHERE p.id = ?;
            """,
            (prioridade_id,),
        ).fetchone()

    return converter_linha(linha)


# ============================================================
# PRIORIDADES — ATUALIZAÇÃO
# ============================================================

def atualizar_prioridade(
    prioridade_id,
    titulo,
    resultado_esperado,
    justificativa_estrategica,
    responsavel_id,
    data_inicio,
    data_fim,
    nivel_prioridade,
    ativa,
):
    titulo = normalizar_texto(titulo)
    resultado_esperado = normalizar_texto(
        resultado_esperado
    )
    justificativa_estrategica = normalizar_texto(
        justificativa_estrategica
    )

    if not titulo:
        return False, "Informe o título da prioridade."

    if not resultado_esperado:
        return False, "Informe o resultado esperado."

    if data_fim < data_inicio:
        return False, (
            "A data final não pode ser anterior "
            "à data inicial."
        )

    if nivel_prioridade not in {
        "Alta",
        "Média",
        "Baixa",
    }:
        return False, "Nível de prioridade inválido."

    try:
        with conectar_banco() as conexao:
            existente = conexao.execute(
                """
                SELECT id
                FROM prioridades
                WHERE id = ?;
                """,
                (prioridade_id,),
            ).fetchone()

            if existente is None:
                return False, "Prioridade não encontrada."

            conexao.execute(
                """
                UPDATE prioridades
                SET
                    titulo = ?,
                    resultado_esperado = ?,
                    justificativa_estrategica = ?,
                    responsavel_id = ?,
                    data_inicio = ?,
                    data_fim = ?,
                    nivel_prioridade = ?,
                    ativa = ?,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    titulo,
                    resultado_esperado,
                    justificativa_estrategica,
                    responsavel_id,
                    str(data_inicio),
                    str(data_fim),
                    nivel_prioridade,
                    1 if ativa else 0,
                    prioridade_id,
                ),
            )

            situacao = (
                "Ativa"
                if ativa
                else "Encerrada"
            )

            registrar_historico_prioridade(
                conexao,
                prioridade_id,
                "Atualização",
                (
                    f"Prioridade atualizada: {titulo}. "
                    f"Situação definida como {situacao}."
                ),
            )

            conexao.commit()

        return True, "Prioridade atualizada com sucesso."

    except Exception as erro:
        return False, f"Erro ao atualizar prioridade: {erro}"


def listar_historico_prioridade(prioridade_id):
    with conectar_banco() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                id,
                acao,
                descricao,
                registrado_em
            FROM historico_prioridades
            WHERE prioridade_id = ?
            ORDER BY id DESC;
            """,
            (prioridade_id,),
        ).fetchall()

    return [dict(linha) for linha in linhas]


# ============================================================
# AGENDA DA GERENTE
# ============================================================

def cadastrar_evento_agenda(
    titulo,
    tipo,
    data_evento,
    hora_inicio,
    hora_fim=None,
    local_link=None,
    participantes=None,
    objetivo=None,
    decisao_necessaria=False,
):
    titulo = normalizar_texto(titulo)
    tipo = normalizar_texto(tipo)
    hora_inicio = normalizar_texto(hora_inicio)
    if not titulo or not tipo or not data_evento or not hora_inicio:
        return False, "Preencha título, tipo, data e horário inicial."
    data_texto = data_evento.isoformat() if hasattr(data_evento, "isoformat") else str(data_evento)
    try:
        with conectar_banco() as conexao:
            conexao.execute(
                """
                INSERT INTO agenda_gerente (
                    titulo, tipo, data_evento, hora_inicio, hora_fim,
                    local_link, participantes, objetivo, decisao_necessaria
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    titulo, tipo, data_texto, hora_inicio,
                    normalizar_texto(hora_fim), normalizar_texto(local_link),
                    normalizar_texto(participantes), normalizar_texto(objetivo),
                    1 if decisao_necessaria else 0,
                ),
            )
            conexao.commit()
        return True, "Compromisso adicionado à agenda."
    except Exception as erro:
        return False, f"Erro ao cadastrar compromisso: {erro}"


def listar_eventos_agenda(data_inicio, data_fim):
    inicio = data_inicio.isoformat() if hasattr(data_inicio, "isoformat") else str(data_inicio)
    fim = data_fim.isoformat() if hasattr(data_fim, "isoformat") else str(data_fim)
    with conectar_banco() as conexao:
        linhas = conexao.execute(
            """
            SELECT * FROM agenda_gerente
            WHERE ativo = 1 AND data_evento BETWEEN ? AND ?
            ORDER BY data_evento, hora_inicio, titulo COLLATE NOCASE;
            """,
            (inicio, fim),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def atualizar_status_evento_agenda(evento_id, status):
    if status not in {"Agendado", "Realizado", "Cancelado"}:
        return False, "Status inválido."
    with conectar_banco() as conexao:
        cursor = conexao.execute(
            """
            UPDATE agenda_gerente
            SET status = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ? AND ativo = 1;
            """,
            (status, evento_id),
        )
        conexao.commit()
    return (True, "Status da agenda atualizado.") if cursor.rowcount else (False, "Compromisso não encontrado.")


def excluir_evento_agenda(evento_id):
    with conectar_banco() as conexao:
        cursor = conexao.execute(
            "UPDATE agenda_gerente SET ativo = 0, atualizado_em = CURRENT_TIMESTAMP WHERE id = ?;",
            (evento_id,),
        )
        conexao.commit()
    return (True, "Compromisso removido da agenda.") if cursor.rowcount else (False, "Compromisso não encontrado.")


def obter_configuracao(chave, padrao=""):
    with conectar_banco() as conexao:
        linha = conexao.execute(
            "SELECT valor FROM configuracoes WHERE chave = ?;",
            (chave,),
        ).fetchone()
    return linha["valor"] if linha else padrao


def salvar_configuracao(chave, valor, descricao=""):
    with conectar_banco() as conexao:
        conexao.execute(
            """
            INSERT INTO configuracoes (chave, valor, descricao)
            VALUES (?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                valor = excluded.valor,
                descricao = excluded.descricao,
                atualizado_em = CURRENT_TIMESTAMP;
            """,
            (chave, normalizar_texto(valor), normalizar_texto(descricao)),
        )
        conexao.commit()


def sincronizar_eventos_microsoft(eventos, data_inicio, data_fim):
    """Substitui somente os blocos Microsoft 365 do período informado."""
    inicio = data_inicio.isoformat() if hasattr(data_inicio, "isoformat") else str(data_inicio)
    fim = data_fim.isoformat() if hasattr(data_fim, "isoformat") else str(data_fim)
    try:
        with conectar_banco() as conexao:
            conexao.execute(
                """
                UPDATE agenda_gerente
                SET ativo = 0, atualizado_em = CURRENT_TIMESTAMP
                WHERE origem = 'Microsoft 365' AND data_evento BETWEEN ? AND ?;
                """,
                (inicio, fim),
            )
            for evento in eventos:
                conexao.execute(
                    """
                    INSERT INTO agenda_gerente (
                        titulo, tipo, data_evento, hora_inicio, hora_fim,
                        local_link, participantes, objetivo, status,
                        decisao_necessaria, origem, ativo, chave_externa
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, 'Agendado', 0,
                              'Microsoft 365', 1, ?)
                    ON CONFLICT(chave_externa) DO UPDATE SET
                        titulo = excluded.titulo,
                        tipo = excluded.tipo,
                        data_evento = excluded.data_evento,
                        hora_inicio = excluded.hora_inicio,
                        hora_fim = excluded.hora_fim,
                        objetivo = excluded.objetivo,
                        status = 'Agendado',
                        ativo = 1,
                        atualizado_em = CURRENT_TIMESTAMP;
                    """,
                    (
                        evento["titulo"], evento["tipo"], evento["data_evento"],
                        evento["hora_inicio"], evento["hora_fim"],
                        evento.get("objetivo", ""), evento["chave_externa"],
                    ),
                )
            conexao.commit()
        return True, f"Agenda sincronizada: {len(eventos)} bloco(s) de disponibilidade encontrado(s)."
    except Exception as erro:
        return False, f"Não foi possível gravar a agenda sincronizada: {erro}"


# ============================================================
# TESTE
# ============================================================

if __name__ == "__main__":
    try:
        inicializar_banco()

        print("")
        print("DATABASE.PY ATUALIZADO COM SUCESSO")
        print(f"Local do banco: {CAMINHO_BANCO}")
        print("")
        print("Funções disponíveis:")
        print("- cadastrar_integrante")
        print("- atualizar_integrante")
        print("- cadastrar_prioridade")
        print("- atualizar_prioridade")
        print("- listar_prioridades")
        print("")

    except Exception as erro:
        print("")
        print("ERRO AO ATUALIZAR O BANCO")
        print(str(erro))
        print("")
