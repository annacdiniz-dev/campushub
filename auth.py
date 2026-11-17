"""Tudo sobre contas: cadastro, login, logout, "esqueci minha senha" e privacidade."""
import secrets
from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from datas import agora_utc
from emails import enviar_email
from models import CodigoSenha, Usuario, db, gerar_codigo_unico

# Blueprint = um "pedaço" do site agrupado num arquivo próprio
auth = Blueprint("auth", __name__)

SENHA_MINIMA = 8
MAX_TENTATIVAS_LOGIN = 4                 # senhas erradas seguidas antes de bloquear
TEMPO_BLOQUEIO = timedelta(minutes=15)
VALIDADE_CODIGO = timedelta(minutes=15)  # o código de "esqueci a senha" vale 15 minutos
MAX_TENTATIVAS_CODIGO = 5


def validar_nova_senha(senha, confirmar):
    """Devolve a mensagem de erro, ou None se a senha estiver ok."""
    if len(senha) < SENHA_MINIMA:
        return f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres."
    if senha != confirmar:
        return "As senhas não são iguais."
    return None


@auth.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("painel"))

    # GET = a pessoa só abriu a página. POST = ela enviou o formulário.
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar", "")

        # Validações: se algo estiver errado, avisa e mostra o formulário de novo
        erro = None
        if not nome or not email or not senha:
            erro = "Preencha todos os campos."
        elif "aceito" not in request.form:
            erro = "Para criar a conta, aceite a Política de Privacidade."
        elif Usuario.query.filter_by(email=email).first():
            erro = "Já existe uma conta com esse e-mail."
        else:
            erro = validar_nova_senha(senha, confirmar)

        if erro:
            flash(erro, "erro")
            return render_template("cadastro.html", nome=nome, email=email)

        usuario = Usuario(nome=nome, email=email, codigo=gerar_codigo_unico(), aceitou_termos_em=agora_utc())
        usuario.definir_senha(senha)
        db.session.add(usuario)
        db.session.commit()

        login_user(usuario)  # já entra logado depois de criar a conta
        flash(f"Conta criada! Bem-vindo(a), {nome}.", "sucesso")
        return redirect(url_for("painel"))

    return render_template("cadastro.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("painel"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = Usuario.query.filter_by(email=email).first()
        agora = agora_utc()

        # Conta bloqueada por muitas senhas erradas? Nem confere a senha.
        if usuario and usuario.bloqueado_ate and usuario.bloqueado_ate > agora:
            minutos = int((usuario.bloqueado_ate - agora).total_seconds() // 60) + 1
            flash(f"Muitas tentativas erradas. Tente de novo em {minutos} min ou use \"Esqueci minha senha\".", "erro")
            return render_template("login.html", email=email)

        # Mesma mensagem para e-mail ou senha errados (não entrega qual dos dois errou)
        if not usuario or not usuario.verificar_senha(senha):
            if usuario:
                usuario.tentativas_falhas += 1
                restantes = MAX_TENTATIVAS_LOGIN - usuario.tentativas_falhas
                if restantes <= 0:
                    # Bloqueia por um tempo: impede que alguém fique testando senhas sem parar
                    usuario.bloqueado_ate = agora + TEMPO_BLOQUEIO
                    usuario.tentativas_falhas = 0
                db.session.commit()
            flash("E-mail ou senha incorretos.", "erro")
            return render_template("login.html", email=email)

        # Acertou: zera o contador
        usuario.tentativas_falhas = 0
        usuario.bloqueado_ate = None
        db.session.commit()
        login_user(usuario, remember=bool(request.form.get("lembrar")))
        # Veio de um link (ex.: o "Abrir no CampusHub" do e-mail)? O Flask-Login guardou o
        # destino em ?next=/atividades/7. Só aceitamos caminhos DENTRO do site ("/algo"),
        # nunca um site de fora ("//site-falso.com"): isso evita golpes de redirecionamento.
        destino = request.args.get("next", "")
        if destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
            return redirect(destino)
        return redirect(url_for("painel"))

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("home"))


# =====================================================================
#  Esqueci minha senha: 1) pede o e-mail  2) manda um código  3) troca a senha
# =====================================================================

@auth.route("/esqueci-senha", methods=["GET", "POST"])
def esqueci_senha():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        agora = agora_utc()

        if usuario:
            ultimo = (CodigoSenha.query.filter_by(usuario_id=usuario.id)
                      .order_by(CodigoSenha.criado_em.desc()).first())
            # No máximo um código por minuto (evita encher a caixa de e-mail de alguém)
            if not ultimo or (agora - ultimo.criado_em) > timedelta(minutes=1):
                # Códigos antigos deixam de valer
                CodigoSenha.query.filter_by(usuario_id=usuario.id, usado=False).update({"usado": True})
                codigo = f"{secrets.randbelow(1_000_000):06d}"  # 6 números, ex.: "048213"
                db.session.add(CodigoSenha(
                    usuario_id=usuario.id,
                    codigo_hash=generate_password_hash(codigo),
                    criado_em=agora,
                    expira_em=agora + VALIDADE_CODIGO,
                ))
                db.session.commit()
                enviar_email(
                    usuario.email,
                    "Seu código para redefinir a senha · CampusHub",
                    f"Olá, {usuario.nome.split()[0]}!\n\n"
                    f"Seu código para criar uma senha nova no CampusHub é: {codigo}\n\n"
                    f"Ele vale por 15 minutos. Se não foi você que pediu, é só ignorar este e-mail: "
                    f"sua senha continua a mesma.",
                    html=render_template("emails/codigo_senha.html", nome=usuario.nome.split()[0], codigo=codigo),
                )

        # A mensagem é SEMPRE a mesma, exista a conta ou não.
        # Assim ninguém usa essa página para descobrir quais e-mails têm conta no site.
        flash("Se existir uma conta com esse e-mail, enviamos um código para ele.", "sucesso")
        return redirect(url_for("auth.redefinir_senha", email=email))

    return render_template("esqueci_senha.html")


@auth.route("/redefinir-senha", methods=["GET", "POST"])
def redefinir_senha():
    email = request.values.get("email", "").strip().lower()

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip().replace(" ", "")
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar", "")

        usuario = Usuario.query.filter_by(email=email).first()
        registro = None
        if usuario:
            registro = (CodigoSenha.query.filter_by(usuario_id=usuario.id, usado=False)
                        .order_by(CodigoSenha.criado_em.desc()).first())

        erro = None
        if not registro or registro.expira_em < agora_utc() or registro.tentativas >= MAX_TENTATIVAS_CODIGO:
            erro = "Código inválido ou vencido. Peça um novo."
        elif not registro.confere(codigo):
            registro.tentativas += 1
            db.session.commit()
            erro = "Código incorreto."
        else:
            erro = validar_nova_senha(senha, confirmar)

        if erro:
            flash(erro, "erro")
            return render_template("redefinir_senha.html", email=email)

        usuario.definir_senha(senha)
        registro.usado = True
        usuario.tentativas_falhas = 0   # senha nova = desbloqueia a conta
        usuario.bloqueado_ate = None
        db.session.commit()
        flash("Senha alterada! Já pode entrar com a senha nova.", "sucesso")
        return redirect(url_for("auth.login"))

    return render_template("redefinir_senha.html", email=email)


@auth.route("/privacidade")
def privacidade():
    return render_template("privacidade.html")
