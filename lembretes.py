"""Lembretes de entrega por e-mail: 7 dias antes e 1 dia antes.

Quem chama isto é o script enviar_lembretes.py, que o PythonAnywhere roda
sozinho uma vez por dia (tarefa agendada).
"""
import os

from flask import render_template
from itsdangerous import BadSignature, URLSafeSerializer

from datas import hoje
from emails import enviar_email
from models import Atividade, LembreteEnviado, Materia, Usuario, db

def site_url():
    """Endereço do site, para montar os links dos e-mails (pode ser trocado no .env)."""
    return os.environ.get("SITE_URL", "https://mycampushub.pythonanywhere.com").rstrip("/")

# A frase muda conforme o status da atividade
MENSAGEM_POR_STATUS = {
    "Pendente": "Você precisa começar!",
    "Em andamento": "Você precisa terminar!",
    "Concluído": "Que bom que você já concluiu! 🎉",
}


# ---------- Link "não quero mais receber" ----------
# O link leva um código ASSINADO com a SECRET_KEY: ninguém consegue fabricar o link
# de outra pessoa (para desligar os lembretes dela), porque não sabe a chave.

def _assinador(secret_key):
    return URLSafeSerializer(secret_key, salt="desligar-lembretes")


def token_desligar(secret_key, usuario_id):
    return _assinador(secret_key).dumps(usuario_id)


def ler_token_desligar(secret_key, token):
    """Devolve o id do usuário, ou None se o link for falso/alterado."""
    try:
        return _assinador(secret_key).loads(token)
    except BadSignature:
        return None


# ---------- O envio ----------

def tipo_de_lembrete(dias):
    """Qual lembrete cabe para uma entrega daqui a `dias` dias (ou None)."""
    if dias == 1:
        return "1dia"
    # 2 a 7 dias: o "lembrete da semana". Normalmente sai com 7 dias; mas se a atividade
    # foi cadastrada já em cima da hora (ex.: faltando 4 dias), sai no dia seguinte, com a conta certa.
    if 2 <= dias <= 7:
        return "7dias"
    return None


def montar_email(atividade, dias, tipo, secret_key):
    materia = atividade.materia
    usuario = materia.usuario
    primeiro_nome = usuario.nome.split()[0]
    mensagem = MENSAGEM_POR_STATUS.get(atividade.status, "")
    link = f"{site_url()}/atividades/{atividade.id}"
    link_desligar = f"{site_url()}/perfil/lembretes/desligar/{token_desligar(secret_key, usuario.id)}"

    if tipo == "1dia":
        assunto = f"⏰ Entrega amanhã: {atividade.titulo}"
        quando = "amanhã"
    else:
        assunto = f"📚 Entrega em {dias} dias: {atividade.titulo}"
        quando = f"em {dias} dias"
    data = atividade.data_entrega.strftime("%d/%m")

    texto = (
        f"Olá, {primeiro_nome}!\n\n"
        f"Você tem uma entrega {quando} ({data}):\n\n"
        f"  {materia.nome}\n  {atividade.titulo} ({atividade.tipo})\n\n"
        f"{mensagem}\n\n"
        f"Abrir no CampusHub: {link}\n\n"
        f"Não quer mais receber lembretes? {link_desligar}"
    )
    html = render_template(
        "emails/lembrete.html",
        nome=primeiro_nome, atividade=atividade, materia=materia, quando=quando, data=data,
        mensagem=mensagem, concluida=atividade.status == "Concluído",
        link=link, link_desligar=link_desligar,
    )
    return usuario.email, assunto, texto, html


def enviar_lembretes_do_dia(secret_key):
    """Olha todas as atividades com data e manda os lembretes que tocam hoje.
    Devolve quantos e-mails foram enviados."""
    dia = hoje()
    enviados = 0

    atividades = (
        Atividade.query.join(Materia).join(Usuario)
        .filter(Atividade.data_entrega.isnot(None), Atividade.data_entrega > dia, Usuario.lembretes_email.is_(True))
        .all()
    )
    for atividade in atividades:
        dias = (atividade.data_entrega - dia).days
        tipo = tipo_de_lembrete(dias)
        if tipo is None:
            continue

        ja_foi = LembreteEnviado.query.filter_by(
            atividade_id=atividade.id, tipo=tipo, data_entrega=atividade.data_entrega
        ).first()
        if ja_foi:
            continue

        para, assunto, texto, html = montar_email(atividade, dias, tipo, secret_key)
        if enviar_email(para, assunto, texto, html=html):
            # Só anota se o e-mail saiu MESMO; se falhou, tenta de novo amanhã
            db.session.add(LembreteEnviado(atividade_id=atividade.id, tipo=tipo, data_entrega=atividade.data_entrega))
            db.session.commit()
            enviados += 1

    return enviados
