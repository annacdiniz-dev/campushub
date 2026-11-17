"""Datas e horas no fuso do Brasil.

O servidor do PythonAnywhere roda no horário UTC (3 horas à frente de Brasília).
Se usássemos date.today() direto, das 21h à meia-noite o servidor já estaria
no "amanhã" — e uma atividade viraria "atrasada" antes da hora.
"""
from datetime import datetime, timedelta, timezone

# Horário de Brasília: UTC-3 (o Brasil não tem mais horário de verão desde 2019)
BRASILIA = timezone(timedelta(hours=-3), "BRT")


def agora_brasil():
    return datetime.now(BRASILIA)


def hoje():
    """A data de hoje no Brasil."""
    return agora_brasil().date()


def agora_utc():
    """Agora em UTC, sem fuso (é assim que guardamos horários no banco)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def saudacao():
    """Bom dia / Boa tarde / Boa noite, conforme a hora no Brasil."""
    hora = agora_brasil().hour
    if 5 <= hora < 12:
        return "Bom dia"
    if 12 <= hora < 18:
        return "Boa tarde"
    return "Boa noite"
