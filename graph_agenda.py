from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

import msal
import requests


GRAPH_URL = "https://graph.microsoft.com/v1.0/me/calendar/getSchedule"
SCOPES = ["Calendars.ReadBasic"]
TIME_ZONE = "E. South America Standard Time"
CACHE_PATH = Path(__file__).with_name(".m365_token_cache.bin")

STATUS_PT = {
    "busy": ("Ocupado", "Ocupado"),
    "tentative": ("Provisório", "Provisório"),
    "oof": ("Fora do escritório", "Fora do escritório"),
    "workingElsewhere": ("Trabalhando em outro local", "Outro local"),
    "free": ("Disponível", "Disponível"),
    "unknown": ("Indisponibilidade", "Indefinido"),
}


class IntegracaoMicrosoftErro(RuntimeError):
    pass


def _carregar_cache():
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        try:
            cache.deserialize(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return cache


def _salvar_cache(cache):
    if cache.has_state_changed:
        CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")


def _aplicacao(tenant_id, client_id):
    cache = _carregar_cache()
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )
    return app, cache


def obter_token(tenant_id, client_id, interativo=False):
    if not tenant_id or not client_id:
        raise IntegracaoMicrosoftErro("Informe o ID do diretório e o ID do aplicativo.")
    app, cache = _aplicacao(tenant_id, client_id)
    contas = app.get_accounts()
    resultado = app.acquire_token_silent(SCOPES, account=contas[0]) if contas else None
    if not resultado and interativo:
        try:
            resultado = app.acquire_token_interactive(
                scopes=SCOPES,
                prompt="select_account",
                port=8400,
            )
        except Exception as erro:
            raise IntegracaoMicrosoftErro(f"Falha ao abrir a autenticação Microsoft: {erro}") from erro
    _salvar_cache(cache)
    if resultado and "access_token" in resultado:
        return resultado["access_token"], resultado.get("id_token_claims", {})
    if resultado:
        detalhe = resultado.get("error_description") or resultado.get("error")
        raise IntegracaoMicrosoftErro(f"A Microsoft não autorizou a conexão: {detalhe}")
    return None, {}


def conexao_ativa(tenant_id, client_id):
    try:
        token, claims = obter_token(tenant_id, client_id, interativo=False)
        return bool(token), claims
    except IntegracaoMicrosoftErro:
        return False, {}


def desconectar():
    try:
        CACHE_PATH.unlink(missing_ok=True)
    except OSError as erro:
        raise IntegracaoMicrosoftErro(f"Não foi possível encerrar a conexão: {erro}") from erro


def _iso_graph(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def consultar_disponibilidade(token, email_gerente, data_inicio: date, data_fim: date):
    if not email_gerente or "@" not in email_gerente:
        raise IntegracaoMicrosoftErro("Informe o e-mail corporativo da gerente.")
    inicio = datetime.combine(data_inicio, time.min)
    fim = datetime.combine(data_fim + timedelta(days=1), time.min)
    corpo = {
        "schedules": [email_gerente.strip()],
        "startTime": {"dateTime": inicio.isoformat(timespec="seconds"), "timeZone": TIME_ZONE},
        "endTime": {"dateTime": fim.isoformat(timespec="seconds"), "timeZone": TIME_ZONE},
        "availabilityViewInterval": 30,
    }
    try:
        resposta = requests.post(
            GRAPH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": f'outlook.timezone="{TIME_ZONE}"',
            },
            json=corpo,
            timeout=30,
        )
    except requests.RequestException as erro:
        raise IntegracaoMicrosoftErro(f"Falha de comunicação com o Microsoft 365: {erro}") from erro
    if resposta.status_code != 200:
        try:
            detalhe = resposta.json().get("error", {}).get("message", resposta.text)
        except (ValueError, json.JSONDecodeError):
            detalhe = resposta.text
        raise IntegracaoMicrosoftErro(
            f"Microsoft 365 retornou o código {resposta.status_code}: {detalhe}"
        )
    valores = resposta.json().get("value", [])
    if not valores:
        return []
    erro_agenda = valores[0].get("error")
    if erro_agenda:
        raise IntegracaoMicrosoftErro(erro_agenda.get("message", "Agenda não localizada."))
    eventos = []
    itens = valores[0].get("scheduleItems", [])
    for indice, item in enumerate(itens):
        status = item.get("status", "unknown")
        if status == "free":
            continue
        inicio_item = _iso_graph(item["start"]["dateTime"])
        fim_item = _iso_graph(item["end"]["dateTime"])
        titulo, tipo = STATUS_PT.get(status, STATUS_PT["unknown"])
        assinatura = "|".join(
            [email_gerente.lower(), inicio_item.isoformat(), fim_item.isoformat(), str(indice)]
        )
        eventos.append(
            {
                "titulo": titulo,
                "tipo": tipo,
                "data_evento": inicio_item.date().isoformat(),
                "hora_inicio": inicio_item.strftime("%H:%M"),
                "hora_fim": fim_item.strftime("%H:%M"),
                "objetivo": "Disponibilidade importada do calendário corporativo.",
                "chave_externa": "m365:" + hashlib.sha256(assinatura.encode()).hexdigest(),
            }
        )
    return eventos
