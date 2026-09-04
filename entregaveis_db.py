from calendar import monthrange
from datetime import date, datetime, timedelta
from database import INTEGRITY_ERROR, conectar_banco


DIAS_SEMANA = {
    "Segunda": 0,
    "Terça": 1,
    "Quarta": 2,
    "Quinta": 3,
    "Sexta": 4,
    "Sábado": 5,
    "Domingo": 6,
}


def _texto(valor):
    if valor is None:
        return None
    valor = str(valor).strip()
    return valor or None


def criar_tabelas_entregaveis(conexao):
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS entregaveis_modelos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prioridade_id INTEGER,
            responsavel_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT,
            periodicidade TEXT NOT NULL
                CHECK (periodicidade IN ('Pontual', 'Diária', 'Semanal', 'Mensal')),
            data_inicio TEXT NOT NULL,
            data_fim TEXT,
            dias_semana TEXT,
            dia_mes INTEGER,
            horario_limite TEXT,
            ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prioridade_id) REFERENCES prioridades(id) ON DELETE SET NULL,
            FOREIGN KEY (responsavel_id) REFERENCES integrantes(id) ON DELETE RESTRICT
        );
        """
    )
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS entregaveis_ocorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modelo_id INTEGER NOT NULL,
            responsavel_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            data_prevista TEXT NOT NULL,
            status TEXT CHECK (status IN ('Entregue', 'Não entregue') OR status IS NULL),
            evidencia TEXT,
            justificativa TEXT,
            confirmado_por_id INTEGER,
            confirmado_em TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (modelo_id, data_prevista),
            FOREIGN KEY (modelo_id) REFERENCES entregaveis_modelos(id) ON DELETE CASCADE,
            FOREIGN KEY (responsavel_id) REFERENCES integrantes(id) ON DELETE RESTRICT,
            FOREIGN KEY (confirmado_por_id) REFERENCES integrantes(id) ON DELETE SET NULL
        );
        """
    )
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS historico_entregaveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ocorrencia_id INTEGER NOT NULL,
            status_anterior TEXT,
            status_novo TEXT NOT NULL,
            observacao TEXT,
            registrado_por_id INTEGER,
            registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ocorrencia_id) REFERENCES entregaveis_ocorrencias(id) ON DELETE CASCADE,
            FOREIGN KEY (registrado_por_id) REFERENCES integrantes(id) ON DELETE SET NULL
        );
        """
    )
    conexao.execute(
        """
        CREATE TABLE IF NOT EXISTS avisos_equipe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL CHECK (tipo IN ('Aviso', 'Bullet point')),
            titulo TEXT NOT NULL,
            descricao TEXT,
            data_inicio TEXT NOT NULL,
            data_fim TEXT,
            ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Migração incremental: preserva bancos criados nas versões anteriores.
    colunas_avisos = {
        linha["name"]
        for linha in conexao.execute("PRAGMA table_info(avisos_equipe);").fetchall()
    }
    novas_colunas = {
        "responsavel_id": "INTEGER",
        "prazo": "TEXT",
        "status": "TEXT DEFAULT 'A planejar'",
        "criticidade": "TEXT DEFAULT 'Normal'",
        "concluido_em": "TEXT",
    }
    for coluna, definicao in novas_colunas.items():
        if coluna not in colunas_avisos:
            conexao.execute(
                f"ALTER TABLE avisos_equipe ADD COLUMN {coluna} {definicao};"
            )
    conexao.execute(
        """
        UPDATE avisos_equipe
        SET status = 'A planejar'
        WHERE tipo = 'Bullet point'
          AND (status IS NULL OR status = 'Pendente');
        """
    )
    conexao.execute(
        """
        UPDATE avisos_equipe
        SET concluido_em = COALESCE(concluido_em, atualizado_em, criado_em)
        WHERE tipo = 'Bullet point' AND status = 'Concluído';
        """
    )
    conexao.execute(
        "CREATE INDEX IF NOT EXISTS idx_entregaveis_data ON entregaveis_ocorrencias(data_prevista);"
    )
    conexao.execute(
        "CREATE INDEX IF NOT EXISTS idx_entregaveis_responsavel ON entregaveis_ocorrencias(responsavel_id);"
    )


def inicializar_modulo_entregaveis():
    with conectar_banco() as conexao:
        criar_tabelas_entregaveis(conexao)
        conexao.commit()


def cadastrar_modelo_entregavel(
    prioridade_id,
    responsavel_id,
    titulo,
    descricao,
    periodicidade,
    data_inicio,
    data_fim=None,
    dias_semana=None,
    dia_mes=None,
    horario_limite=None,
):
    titulo = _texto(titulo)
    descricao = _texto(descricao)
    horario_limite = _texto(horario_limite)
    if not titulo:
        return False, "Informe o nome do entregável."
    if periodicidade not in {"Pontual", "Diária", "Semanal", "Mensal"}:
        return False, "Periodicidade inválida."
    if periodicidade == "Semanal" and not dias_semana:
        return False, "Selecione pelo menos um dia da semana."
    if periodicidade == "Mensal" and not dia_mes:
        return False, "Informe o dia do mês."
    inicio = data_inicio.isoformat() if isinstance(data_inicio, date) else str(data_inicio)
    fim = data_fim.isoformat() if isinstance(data_fim, date) else data_fim
    dias = ",".join(dias_semana or []) or None
    try:
        with conectar_banco() as conexao:
            cursor = conexao.execute(
                """
                INSERT INTO entregaveis_modelos (
                    prioridade_id, responsavel_id, titulo, descricao,
                    periodicidade, data_inicio, data_fim, dias_semana,
                    dia_mes, horario_limite
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (prioridade_id, responsavel_id, titulo, descricao,
                 periodicidade, inicio, fim, dias, dia_mes, horario_limite),
            )
            modelo_id = cursor.lastrowid
            conexao.commit()
        gerar_ocorrencias_modelo(modelo_id, date.fromisoformat(inicio).year, date.fromisoformat(inicio).month)
        return True, "Entregável cadastrado com sucesso."
    except INTEGRITY_ERROR:
        return False, "Não foi possível cadastrar o entregável. Verifique os dados."
    except Exception as erro:
        return False, f"Erro inesperado: {erro}"


def listar_modelos(apenas_ativos=True):
    consulta = """
        SELECT m.*, i.nome AS responsavel_nome, p.titulo AS prioridade_titulo
        FROM entregaveis_modelos m
        JOIN integrantes i ON i.id = m.responsavel_id
        LEFT JOIN prioridades p ON p.id = m.prioridade_id
    """
    parametros = []
    if apenas_ativos:
        consulta += " WHERE m.ativo = ?"
        parametros.append(1)
    consulta += " ORDER BY m.titulo COLLATE NOCASE;"
    with conectar_banco() as conexao:
        return [dict(linha) for linha in conexao.execute(consulta, parametros).fetchall()]


def buscar_modelo_por_id(modelo_id):
    with conectar_banco() as conexao:
        linha = conexao.execute(
            """
            SELECT m.*, i.nome AS responsavel_nome, p.titulo AS prioridade_titulo
            FROM entregaveis_modelos m
            JOIN integrantes i ON i.id = m.responsavel_id
            LEFT JOIN prioridades p ON p.id = m.prioridade_id
            WHERE m.id = ?;
            """,
            (modelo_id,),
        ).fetchone()
    return dict(linha) if linha else None


def atualizar_modelo_entregavel(
    modelo_id,
    prioridade_id,
    responsavel_id,
    titulo,
    descricao,
    periodicidade,
    data_inicio,
    data_fim=None,
    dias_semana=None,
    dia_mes=None,
    horario_limite=None,
    ativo=True,
):
    titulo = _texto(titulo)
    descricao = _texto(descricao)
    horario_limite = _texto(horario_limite)
    if not titulo:
        return False, "Informe o nome do entregável."
    if periodicidade not in {"Pontual", "Diária", "Semanal", "Mensal"}:
        return False, "Periodicidade inválida."
    if periodicidade == "Semanal" and not dias_semana:
        return False, "Selecione pelo menos um dia da semana."
    if periodicidade == "Mensal" and not dia_mes:
        return False, "Informe o dia do mês."
    inicio = data_inicio.isoformat() if isinstance(data_inicio, date) else str(data_inicio)
    fim = data_fim.isoformat() if isinstance(data_fim, date) else data_fim
    dias = ",".join(dias_semana or []) or None
    try:
        with conectar_banco() as conexao:
            existe = conexao.execute(
                "SELECT id FROM entregaveis_modelos WHERE id = ?;",
                (modelo_id,),
            ).fetchone()
            if not existe:
                return False, "Entregável não encontrado."
            conexao.execute(
                """
                UPDATE entregaveis_modelos
                SET prioridade_id = ?, responsavel_id = ?, titulo = ?,
                    descricao = ?, periodicidade = ?, data_inicio = ?,
                    data_fim = ?, dias_semana = ?, dia_mes = ?,
                    horario_limite = ?, ativo = ?, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    prioridade_id, responsavel_id, titulo, descricao,
                    periodicidade, inicio, fim, dias, dia_mes,
                    horario_limite, 1 if ativo else 0, modelo_id,
                ),
            )
            # Baixas já realizadas são evidências históricas e permanecem intactas.
            # Somente previsões ainda sem baixa são recalculadas.
            conexao.execute(
                "DELETE FROM entregaveis_ocorrencias WHERE modelo_id = ? AND status IS NULL;",
                (modelo_id,),
            )
            conexao.commit()
        if ativo:
            inicio_data = date.fromisoformat(inicio)
            gerar_ocorrencias_modelo(modelo_id, inicio_data.year, inicio_data.month)
        return True, "Entregável atualizado com sucesso."
    except INTEGRITY_ERROR:
        return False, "Não foi possível atualizar o entregável. Verifique os dados."
    except Exception as erro:
        return False, f"Erro inesperado: {erro}"


def alterar_situacao_modelo(modelo_id, ativo):
    with conectar_banco() as conexao:
        cursor = conexao.execute(
            """
            UPDATE entregaveis_modelos
            SET ativo = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (1 if ativo else 0, modelo_id),
        )
        if cursor.rowcount == 0:
            return False, "Entregável não encontrado."
        if not ativo:
            conexao.execute(
                "DELETE FROM entregaveis_ocorrencias WHERE modelo_id = ? AND status IS NULL;",
                (modelo_id,),
            )
        conexao.commit()
    mensagem = "Entregável reativado com sucesso." if ativo else "Entregável inativado com sucesso."
    return True, mensagem


def excluir_modelo_entregavel(modelo_id):
    """Exclui o entregável e todas as ocorrências/históricos vinculados."""
    with conectar_banco() as conexao:
        modelo = conexao.execute(
            "SELECT titulo FROM entregaveis_modelos WHERE id = ?;",
            (modelo_id,),
        ).fetchone()
        if not modelo:
            return False, "Entregável não encontrado."
        total_ocorrencias = conexao.execute(
            "SELECT COUNT(*) AS total FROM entregaveis_ocorrencias WHERE modelo_id = ?;",
            (modelo_id,),
        ).fetchone()["total"]
        conexao.execute(
            "DELETE FROM entregaveis_modelos WHERE id = ?;",
            (modelo_id,),
        )
        conexao.commit()
    return True, f"Entregável excluído com sucesso. {total_ocorrencias} ocorrência(s) removida(s)."


def contar_ocorrencias_modelo(modelo_id):
    with conectar_banco() as conexao:
        linha = conexao.execute(
            "SELECT COUNT(*) AS total FROM entregaveis_ocorrencias WHERE modelo_id = ?;",
            (modelo_id,),
        ).fetchone()
    return int(linha["total"] if linha else 0)


def _datas_do_modelo(modelo, ano, mes):
    primeiro = date(ano, mes, 1)
    ultimo = date(ano, mes, monthrange(ano, mes)[1])
    inicio = max(primeiro, date.fromisoformat(modelo["data_inicio"]))
    fim_modelo = date.fromisoformat(modelo["data_fim"]) if modelo["data_fim"] else ultimo
    fim = min(ultimo, fim_modelo)
    if inicio > fim:
        return []
    periodicidade = modelo["periodicidade"]
    if periodicidade == "Pontual":
        data_pontual = date.fromisoformat(modelo["data_inicio"])
        return [data_pontual] if primeiro <= data_pontual <= ultimo else []
    if periodicidade == "Mensal":
        dia = min(int(modelo["dia_mes"]), ultimo.day)
        candidata = date(ano, mes, dia)
        return [candidata] if inicio <= candidata <= fim else []
    datas = []
    atual = inicio
    dias_validos = set()
    if periodicidade == "Semanal":
        nomes = (modelo["dias_semana"] or "").split(",")
        dias_validos = {DIAS_SEMANA[nome] for nome in nomes if nome in DIAS_SEMANA}
    while atual <= fim:
        if periodicidade == "Diária" or atual.weekday() in dias_validos:
            datas.append(atual)
        atual += timedelta(days=1)
    return datas


def gerar_ocorrencias_modelo(modelo_id, ano, mes):
    with conectar_banco() as conexao:
        modelo = conexao.execute(
            "SELECT * FROM entregaveis_modelos WHERE id = ? AND ativo = 1;",
            (modelo_id,),
        ).fetchone()
        if not modelo:
            return 0
        quantidade = 0
        for data_prevista in _datas_do_modelo(dict(modelo), ano, mes):
            cursor = conexao.execute(
                """
                INSERT OR IGNORE INTO entregaveis_ocorrencias (
                    modelo_id, responsavel_id, titulo, data_prevista
                ) VALUES (?, ?, ?, ?);
                """,
                (modelo["id"], modelo["responsavel_id"], modelo["titulo"], data_prevista.isoformat()),
            )
            # O SQLite local retorna 0/1 em rowcount. Alguns drivers do
            # SQLite Cloud retornam None ou -1 mesmo quando a operação foi
            # executada corretamente. A contagem é apenas informativa e não
            # pode impedir a abertura do painel.
            linhas_afetadas = getattr(cursor, "rowcount", 0)
            quantidade += max(int(linhas_afetadas or 0), 0)
        conexao.commit()
    return quantidade


def gerar_ocorrencias_mes(ano, mes):
    total = 0
    for modelo in listar_modelos(apenas_ativos=True):
        total += gerar_ocorrencias_modelo(modelo["id"], ano, mes)
    return total


def listar_ocorrencias_mes(ano, mes, responsavel_id=None):
    inicio = date(ano, mes, 1).isoformat()
    fim = date(ano, mes, monthrange(ano, mes)[1]).isoformat()
    consulta = """
        SELECT o.*, i.nome AS responsavel_nome, i.cargo,
               m.periodicidade, m.horario_limite,
               p.titulo AS prioridade_titulo
        FROM entregaveis_ocorrencias o
        JOIN integrantes i ON i.id = o.responsavel_id
        JOIN entregaveis_modelos m ON m.id = o.modelo_id
        LEFT JOIN prioridades p ON p.id = m.prioridade_id
        WHERE o.data_prevista BETWEEN ? AND ?
    """
    parametros = [inicio, fim]
    if responsavel_id:
        consulta += " AND o.responsavel_id = ?"
        parametros.append(responsavel_id)
    consulta += " ORDER BY o.data_prevista, i.nome COLLATE NOCASE, o.titulo COLLATE NOCASE;"
    with conectar_banco() as conexao:
        return [dict(linha) for linha in conexao.execute(consulta, parametros).fetchall()]


def confirmar_entregavel(ocorrencia_id, status, confirmado_por_id, evidencia=None, justificativa=None):
    evidencia = _texto(evidencia)
    justificativa = _texto(justificativa)
    if status not in {"Entregue", "Não entregue"}:
        return False, "Selecione Entregue ou Não entregue."
    if status == "Não entregue" and not justificativa:
        return False, "Informe a justificativa da não entrega."
    with conectar_banco() as conexao:
        atual = conexao.execute(
            "SELECT status FROM entregaveis_ocorrencias WHERE id = ?;",
            (ocorrencia_id,),
        ).fetchone()
        if not atual:
            return False, "Entrega não encontrada."
        conexao.execute(
            """
            UPDATE entregaveis_ocorrencias
            SET status = ?, evidencia = ?, justificativa = ?,
                confirmado_por_id = ?, confirmado_em = CURRENT_TIMESTAMP,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (status, evidencia, justificativa, confirmado_por_id, ocorrencia_id),
        )
        conexao.execute(
            """
            INSERT INTO historico_entregaveis (
                ocorrencia_id, status_anterior, status_novo,
                observacao, registrado_por_id
            ) VALUES (?, ?, ?, ?, ?);
            """,
            (ocorrencia_id, atual["status"], status,
             evidencia if status == "Entregue" else justificativa,
             confirmado_por_id),
        )
        conexao.commit()
    return True, "Baixa registrada com sucesso."


def cadastrar_aviso(
    tipo,
    titulo,
    descricao,
    data_inicio,
    data_fim=None,
    responsavel_id=None,
    prazo=None,
    status=None,
    criticidade=None,
):
    titulo = _texto(titulo)
    descricao = _texto(descricao)
    if tipo not in {"Aviso", "Bullet point"} or not titulo:
        return False, "Preencha corretamente o aviso."
    inicio = data_inicio.isoformat() if isinstance(data_inicio, date) else str(data_inicio)
    fim = data_fim.isoformat() if isinstance(data_fim, date) else data_fim
    prazo_texto = prazo.isoformat() if isinstance(prazo, date) else prazo
    status = _texto(status) or "A planejar"
    criticidade = _texto(criticidade) or "Normal"
    if tipo == "Bullet point" and not responsavel_id:
        return False, "Selecione o responsável pela ação."
    if tipo == "Bullet point" and not prazo_texto:
        return False, "Informe o prazo da ação."
    if status not in {"A planejar", "Em andamento", "Concluído"}:
        return False, "Status inválido."
    if criticidade not in {"Normal", "Atenção", "Crítico"}:
        return False, "Criticidade inválida."
    with conectar_banco() as conexao:
        conexao.execute(
            """
            INSERT INTO avisos_equipe (
                tipo, titulo, descricao, data_inicio, data_fim,
                responsavel_id, prazo, status, criticidade
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                tipo, titulo, descricao, inicio, fim,
                responsavel_id, prazo_texto, status, criticidade,
            ),
        )
        conexao.commit()
    mensagem = "Ação cadastrada com sucesso." if tipo == "Bullet point" else "Aviso cadastrado com sucesso."
    return True, mensagem


def atualizar_status_acao(acao_id, status):
    if status not in {"A planejar", "Em andamento", "Concluído"}:
        return False, "Status inválido."
    concluido_em = datetime.now().isoformat(timespec="seconds") if status == "Concluído" else None
    with conectar_banco() as conexao:
        cursor = conexao.execute(
            """
            UPDATE avisos_equipe
            SET status = ?,
                concluido_em = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ? AND tipo = 'Bullet point';
            """,
            (status, concluido_em, acao_id),
        )
        conexao.commit()
    if cursor.rowcount == 0:
        return False, "Ação não encontrada."
    return True, "Status atualizado com sucesso."


def listar_avisos(data_referencia=None):
    referencia = data_referencia or date.today()
    referencia = referencia.isoformat() if isinstance(referencia, date) else str(referencia)
    with conectar_banco() as conexao:
        linhas = conexao.execute(
            """
            SELECT * FROM avisos_equipe
            WHERE ativo = 1 AND data_inicio <= ?
              AND (data_fim IS NULL OR data_fim >= ?)
              AND (
                    tipo <> 'Bullet point'
                    OR status <> 'Concluído'
                    OR date(COALESCE(concluido_em, atualizado_em, criado_em)) >= date(?)
              )
            ORDER BY tipo, criado_em DESC;
            """,
            (referencia, referencia, referencia),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def listar_historico_acoes(data_inicio=None, data_fim=None, responsavel_id=None):
    inicio = data_inicio or (date.today() - timedelta(days=30))
    fim = data_fim or date.today()
    inicio = inicio.isoformat() if isinstance(inicio, date) else str(inicio)
    fim = fim.isoformat() if isinstance(fim, date) else str(fim)
    consulta = """
        SELECT a.*, i.nome AS responsavel_nome
        FROM avisos_equipe a
        LEFT JOIN integrantes i ON i.id = a.responsavel_id
        WHERE a.tipo = 'Bullet point'
          AND a.status = 'Concluído'
          AND date(COALESCE(a.concluido_em, a.atualizado_em, a.criado_em))
              BETWEEN date(?) AND date(?)
    """
    parametros = [inicio, fim]
    if responsavel_id:
        consulta += " AND a.responsavel_id = ?"
        parametros.append(responsavel_id)
    consulta += " ORDER BY COALESCE(a.concluido_em, a.atualizado_em) DESC, a.titulo COLLATE NOCASE;"
    with conectar_banco() as conexao:
        linhas = conexao.execute(consulta, parametros).fetchall()
    return [dict(linha) for linha in linhas]
