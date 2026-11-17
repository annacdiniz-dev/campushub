"""Envio de e-mails pelo Gmail (SMTP).

A conta e a "senha de app" do Gmail ficam em variáveis de ambiente
(no PythonAnywhere: no arquivo WSGI), NUNCA no código:
    EMAIL_USUARIO     -> ex.: campushub.avisos@gmail.com
    EMAIL_SENHA_APP   -> a senha de app de 16 letras gerada no Google

Sem essas variáveis (no seu computador, por exemplo), o e-mail não é enviado:
ele é mostrado no terminal, para dar para testar mesmo assim.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def envio_configurado():
    return bool(os.environ.get("EMAIL_USUARIO") and os.environ.get("EMAIL_SENHA_APP"))


def enviar_email(para, assunto, texto, html=None):
    """Envia um e-mail. Devolve True se enviou, False se não deu (sem quebrar o site)."""
    if not envio_configurado():
        print("\n" + "=" * 60)
        print("E-MAIL (não enviado: Gmail ainda não configurado)")
        print(f"Para: {para}\nAssunto: {assunto}\n\n{texto}")
        print("=" * 60 + "\n", flush=True)
        return False

    remetente = os.environ["EMAIL_USUARIO"]
    mensagem = EmailMessage()
    mensagem["From"] = f"CampusHub <{remetente}>"
    mensagem["To"] = para
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)               # versão só texto (para quem não abre HTML)
    if html:
        mensagem.add_alternative(html, subtype="html")  # versão bonita

    try:
        # SMTP_SSL = conexão já criptografada com o servidor do Gmail (porta 465)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=20) as servidor:
            servidor.login(remetente, os.environ["EMAIL_SENHA_APP"])
            servidor.send_message(mensagem)
        return True
    except (smtplib.SMTPException, OSError) as erro:
        print(f"Falha ao enviar e-mail para {para}: {erro}", flush=True)
        return False
