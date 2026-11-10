"""Tudo sobre contas: cadastro, login e logout."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from models import Usuario, db

# Blueprint = um "pedaço" do site agrupado num arquivo próprio
auth = Blueprint("auth", __name__)


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
        elif len(senha) < 6:
            erro = "A senha precisa ter pelo menos 6 caracteres."
        elif senha != confirmar:
            erro = "As senhas não são iguais."
        elif Usuario.query.filter_by(email=email).first():
            erro = "Já existe uma conta com esse e-mail."

        if erro:
            flash(erro, "erro")
            return render_template("cadastro.html", nome=nome, email=email)

        usuario = Usuario(nome=nome, email=email)
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

        # Mesma mensagem para e-mail ou senha errados (não entrega qual dos dois errou)
        if not usuario or not usuario.verificar_senha(senha):
            flash("E-mail ou senha incorretos.", "erro")
            return render_template("login.html", email=email)

        login_user(usuario, remember=bool(request.form.get("lembrar")))
        return redirect(url_for("painel"))

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("home"))
