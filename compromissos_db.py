from database import DATABASE_ERROR, conectar_banco


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
# TABELA DE COMPROMISSOS
# ============================================================

def criar_tabela_compromissos(conexao):
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS compromissos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            prioridade_id INTEGER,
            responsavel_id INTEGER NOT NULL,
            criado_por_id INTEGER,

            titulo TEXT NOT NULL,
            resultado_esperado TEXT NOT NULL,
            observacao TEXT,

            data_inicio TEXT NOT NULL,
            data_prazo TEXT NOT NULL,

            origem TEXT NOT NULL DEFAULT 'Equipe'
                CHECK (
                    origem IN (
                        'Gerente',
                        'Equipe'
                    )
                ),

            status TEXT NOT NULL DEFAULT 'Programado'
                CHECK (
                    status IN (
                        'Programado',
                        'Entregue',
                        'Não entregue'
                    )
                ),

            evidencia TEXT,
            justificativa TEXT,

            ativo INTEGER NOT NULL DEFAULT 1
                CHECK (ativo IN (0, 1)),

            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (prioridade_id)
                REFERENCES prioridades(id)
                ON UPDATE CASCADE
                ON DELETE SET NULL,

            FOREIGN KEY (responsavel_id)
                REFERENCES integrantes(id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT,

            FOREIGN KEY (criado_por_id)
                REFERENCES integrantes(id)
                ON UPDATE CASCADE
                ON DELETE SET NULL
        );
        """
    )


# ============================================================
# HISTÓRICO DOS COMPROMISSOS
# ============================================================

def criar_tabela_historico_compromissos(conexao):
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS historico_compromissos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compromisso_id INTEGER NOT NULL,
            acao TEXT NOT NULL,
            descricao TEXT,
            registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (compromisso_id)
                REFERENCES compromissos(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )


# ============================================================
# ÍNDICES
# ============================================================

def criar_indices_compromissos(conexao):
    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_compromissos_responsavel
        ON compromissos(responsavel_id);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_compromissos_prioridade
        ON compromissos(prioridade_id);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_compromissos_prazo
        ON compromissos(data_prazo);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_compromissos_status
        ON compromissos(status);
        """
    )

    conexao.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_historico_compromissos
        ON historico_compromissos(compromisso_id);
        """
    )


# ============================================================
# INICIALIZAÇÃO DO MÓDULO
# ============================================================

def inicializar_modulo_compromissos():
    with conectar_banco() as conexao:
        criar_tabela_compromissos(conexao)
        criar_tabela_historico_compromissos(conexao)
        criar_indices_compromissos(conexao)
        conexao.commit()


# ============================================================
# HISTÓRICO
# ============================================================

def registrar_historico_compromisso(
    conexao,
    compromisso_id,
    acao,
    descricao,
):
    conexao.execute(
        """
        INSERT INTO historico_compromissos (
            compromisso_id,
            acao,
            descricao
        )
        VALUES (?, ?, ?);
        """,
        (
            compromisso_id,
            acao,
            descricao,
        ),
    )


def listar_historico_compromisso(compromisso_id):
    with conectar_banco() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                id,
                acao,
                descricao,
                registrado_em
            FROM historico_compromissos
            WHERE compromisso_id = ?
            ORDER BY id DESC;
            """,
            (compromisso_id,),
        ).fetchall()

    return [
        dict(linha)
        for linha in linhas
    ]


# ============================================================
# CADASTRO
# ============================================================

def cadastrar_compromisso(
    prioridade_id,
    responsavel_id,
    criado_por_id,
    titulo,
    resultado_esperado,
    observacao,
    data_inicio,
    data_prazo,
    origem,
):
    titulo = normalizar_texto(titulo)
    resultado_esperado = normalizar_texto(
        resultado_esperado
    )
    observacao = normalizar_texto(observacao)

    if not titulo:
        return False, "Informe o título do compromisso."

    if not resultado_esperado:
        return False, "Informe o resultado esperado."

    if responsavel_id is None:
        return False, "Selecione o responsável."

    if data_prazo < data_inicio:
        return False, (
            "A data do prazo não pode ser anterior "
            "à data de início."
        )

    if origem not in {
        "Gerente",
        "Equipe",
    }:
        return False, "Origem do compromisso inválida."

    try:
        with conectar_banco() as conexao:
            responsavel = conexao.execute(
                """
                SELECT id, nome, ativo
                FROM integrantes
                WHERE id = ?;
                """,
                (responsavel_id,),
            ).fetchone()

            if responsavel is None:
                return False, "Responsável não encontrado."

            if responsavel["ativo"] != 1:
                return False, (
                    "Não é possível atribuir um compromisso "
                    "a um integrante inativo."
                )

            if prioridade_id is not None:
                prioridade = conexao.execute(
                    """
                    SELECT id, ativa
                    FROM prioridades
                    WHERE id = ?;
                    """,
                    (prioridade_id,),
                ).fetchone()

                if prioridade is None:
                    return False, "Prioridade não encontrada."

                if prioridade["ativa"] != 1:
                    return False, (
                        "Não é possível vincular o compromisso "
                        "a uma prioridade encerrada."
                    )

            cursor = conexao.execute(
                """
                INSERT INTO compromissos (
                    prioridade_id,
                    responsavel_id,
                    criado_por_id,
                    titulo,
                    resultado_esperado,
                    observacao,
                    data_inicio,
                    data_prazo,
                    origem,
                    status,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Programado', 1);
                """,
                (
                    prioridade_id,
                    responsavel_id,
                    criado_por_id,
                    titulo,
                    resultado_esperado,
                    observacao,
                    str(data_inicio),
                    str(data_prazo),
                    origem,
                ),
            )

            compromisso_id = cursor.lastrowid

            registrar_historico_compromisso(
                conexao=conexao,
                compromisso_id=compromisso_id,
                acao="Cadastro",
                descricao=(
                    f"Compromisso cadastrado: {titulo}. "
                    f"Responsável: {responsavel['nome']}."
                ),
            )

            conexao.commit()

        return True, "Compromisso cadastrado com sucesso."

    except Exception as erro:
        return False, f"Erro ao cadastrar compromisso: {erro}"


# ============================================================
# CONSULTA
# ============================================================

def listar_compromissos(
    responsavel_id=None,
    data_inicio=None,
    data_fim=None,
    apenas_ativos=True,
):
    consulta = """
        SELECT
            c.id,
            c.prioridade_id,
            p.titulo AS prioridade_titulo,

            c.responsavel_id,
            responsável.nome AS responsavel_nome,

            c.criado_por_id,
            criador.nome AS criado_por_nome,

            c.titulo,
            c.resultado_esperado,
            c.observacao,
            c.data_inicio,
            c.data_prazo,
            c.origem,
            c.status,
            c.evidencia,
            c.justificativa,
            c.ativo,
            c.criado_em,
            c.atualizado_em

        FROM compromissos AS c

        LEFT JOIN prioridades AS p
            ON p.id = c.prioridade_id

        INNER JOIN integrantes AS responsável
            ON responsável.id = c.responsavel_id

        LEFT JOIN integrantes AS criador
            ON criador.id = c.criado_por_id

        WHERE 1 = 1
    """

    parametros = []

    if apenas_ativos:
        consulta += " AND c.ativo = ?"
        parametros.append(1)

    if responsavel_id is not None:
        consulta += " AND c.responsavel_id = ?"
        parametros.append(responsavel_id)

    if data_inicio is not None:
        consulta += " AND c.data_prazo >= ?"
        parametros.append(str(data_inicio))

    if data_fim is not None:
        consulta += " AND c.data_prazo <= ?"
        parametros.append(str(data_fim))

    consulta += """
        ORDER BY
            c.data_prazo ASC,
            c.titulo COLLATE NOCASE ASC;
    """

    with conectar_banco() as conexao:
        linhas = conexao.execute(
            consulta,
            parametros,
        ).fetchall()

    return [
        dict(linha)
        for linha in linhas
    ]


def buscar_compromisso_por_id(compromisso_id):
    with conectar_banco() as conexao:
        linha = conexao.execute(
            """
            SELECT
                c.id,
                c.prioridade_id,
                p.titulo AS prioridade_titulo,
                c.responsavel_id,
                i.nome AS responsavel_nome,
                c.criado_por_id,
                c.titulo,
                c.resultado_esperado,
                c.observacao,
                c.data_inicio,
                c.data_prazo,
                c.origem,
                c.status,
                c.evidencia,
                c.justificativa,
                c.ativo,
                c.criado_em,
                c.atualizado_em

            FROM compromissos AS c

            LEFT JOIN prioridades AS p
                ON p.id = c.prioridade_id

            INNER JOIN integrantes AS i
                ON i.id = c.responsavel_id

            WHERE c.id = ?;
            """,
            (compromisso_id,),
        ).fetchone()

    return converter_linha(linha)


# ============================================================
# ATUALIZAÇÃO
# ============================================================

def atualizar_compromisso(
    compromisso_id,
    prioridade_id,
    responsavel_id,
    titulo,
    resultado_esperado,
    observacao,
    data_inicio,
    data_prazo,
    origem,
    ativo,
):
    titulo = normalizar_texto(titulo)
    resultado_esperado = normalizar_texto(
        resultado_esperado
    )
    observacao = normalizar_texto(observacao)

    if not titulo:
        return False, "Informe o título do compromisso."

    if not resultado_esperado:
        return False, "Informe o resultado esperado."

    if responsavel_id is None:
        return False, "Selecione o responsável."

    if data_prazo < data_inicio:
        return False, (
            "A data do prazo não pode ser anterior "
            "à data de início."
        )

    if origem not in {
        "Gerente",
        "Equipe",
    }:
        return False, "Origem do compromisso inválida."

    try:
        with conectar_banco() as conexao:
            compromisso = conexao.execute(
                """
                SELECT id
                FROM compromissos
                WHERE id = ?;
                """,
                (compromisso_id,),
            ).fetchone()

            if compromisso is None:
                return False, "Compromisso não encontrado."

            responsavel = conexao.execute(
                """
                SELECT id, nome, ativo
                FROM integrantes
                WHERE id = ?;
                """,
                (responsavel_id,),
            ).fetchone()

            if responsavel is None:
                return False, "Responsável não encontrado."

            if responsavel["ativo"] != 1:
                return False, (
                    "Não é possível atribuir o compromisso "
                    "a um integrante inativo."
                )

            conexao.execute(
                """
                UPDATE compromissos
                SET
                    prioridade_id = ?,
                    responsavel_id = ?,
                    titulo = ?,
                    resultado_esperado = ?,
                    observacao = ?,
                    data_inicio = ?,
                    data_prazo = ?,
                    origem = ?,
                    ativo = ?,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    prioridade_id,
                    responsavel_id,
                    titulo,
                    resultado_esperado,
                    observacao,
                    str(data_inicio),
                    str(data_prazo),
                    origem,
                    1 if ativo else 0,
                    compromisso_id,
                ),
            )

            registrar_historico_compromisso(
                conexao,
                compromisso_id,
                "Atualização",
                (
                    f"Compromisso atualizado: {titulo}. "
                    f"Responsável: {responsavel['nome']}."
                ),
            )

            conexao.commit()

        return True, "Compromisso atualizado com sucesso."

    except Exception as erro:
        return False, f"Erro ao atualizar compromisso: {erro}"


# ============================================================
# CONFIRMAÇÃO DE ENTREGA
# ============================================================

def confirmar_compromisso(
    compromisso_id,
    entregue,
    evidencia=None,
    justificativa=None,
):
    evidencia = normalizar_texto(evidencia)
    justificativa = normalizar_texto(justificativa)

    if entregue and not evidencia:
        return False, (
            "Informe a evidência para confirmar "
            "a entrega."
        )

    if not entregue and not justificativa:
        return False, (
            "Informe a justificativa para registrar "
            "a não entrega."
        )

    status = (
        "Entregue"
        if entregue
        else "Não entregue"
    )

    try:
        with conectar_banco() as conexao:
            compromisso = conexao.execute(
                """
                SELECT id, titulo
                FROM compromissos
                WHERE id = ?
                  AND ativo = 1;
                """,
                (compromisso_id,),
            ).fetchone()

            if compromisso is None:
                return False, (
                    "Compromisso não encontrado "
                    "ou inativo."
                )

            conexao.execute(
                """
                UPDATE compromissos
                SET
                    status = ?,
                    evidencia = ?,
                    justificativa = ?,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    status,
                    evidencia if entregue else None,
                    justificativa if not entregue else None,
                    compromisso_id,
                ),
            )

            registrar_historico_compromisso(
                conexao,
                compromisso_id,
                "Confirmação",
                (
                    f"Compromisso classificado como "
                    f"{status}: {compromisso['titulo']}."
                ),
            )

            conexao.commit()

        return True, (
            "Entrega confirmada com sucesso."
            if entregue
            else "Não entrega registrada com sucesso."
        )

    except DATABASE_ERROR as erro:
        return False, f"Erro ao confirmar compromisso: {erro}"


# ============================================================
# TESTE DO MÓDULO
# ============================================================

if __name__ == "__main__":
    try:
        inicializar_modulo_compromissos()

        with conectar_banco() as conexao:
            tabelas = conexao.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN (
                      'compromissos',
                      'historico_compromissos'
                  )
                ORDER BY name;
                """
            ).fetchall()

        print("")
        print("MÓDULO DE COMPROMISSOS CRIADO COM SUCESSO")
        print("Tabelas encontradas:")

        for tabela in tabelas:
            print(f"- {tabela['name']}")

        print("")

    except Exception as erro:
        print("")
        print("ERRO NO MÓDULO DE COMPROMISSOS")
        print(str(erro))
        print("")
