"""Página "Editar perfil": trocar foto, nome e e-mail."""
import os
import re
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Usuario, db

perfil = Blueprint("perfil", __name__, url_prefix="/perfil")

EXTENSOES_FOTO = {"png", "jpg", "jpeg", "webp", "gif"}
# Formato básico de e-mail: algo@algo.algo (sem espaços)
EMAIL_VALIDO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def pasta_fotos():
    """Onde as fotos ficam guardadas: static/uploads/fotos/ (cria a pasta se não existir)."""
    pasta = os.path.join(current_app.static_folder, "uploads", "fotos")
    os.makedirs(pasta, exist_ok=True)
    return pasta


def apagar_foto_atual():
    """Apaga do disco a foto atual do usuário (se tiver), para não acumular arquivos velhos."""
    if current_user.foto:
        caminho = os.path.join(pasta_fotos(), current_user.foto)
        if os.path.exists(caminho):
            os.remove(caminho)


@perfil.route("/")
@login_required
def editar():
    return render_template("perfil.html")


@perfil.route("/foto", methods=["POST"])
@login_required
def trocar_foto():
    # Arquivos enviados não vêm em request.form, e sim em request.files
    arquivo = request.files.get("foto")
    if not arquivo or not arquivo.filename:
        flash("Escolha uma imagem primeiro.", "erro")
        return redirect(url_for("perfil.editar"))

    extensao = arquivo.filename.rsplit(".", 1)[-1].lower() if "." in arquivo.filename else ""
    if extensao not in EXTENSOES_FOTO or not arquivo.mimetype.startswith("image/"):
        flash("Envie uma imagem PNG, JPG, WEBP ou GIF.", "erro")
        return redirect(url_for("perfil.editar"))

    # Segurança: NUNCA usamos o nome que veio do computador da pessoa
    # (poderia ser "../../app.py"). Criamos um nome novo e aleatório.
    nome_arquivo = f"{current_user.id}_{uuid.uuid4().hex[:12]}.{extensao}"
    arquivo.save(os.path.join(pasta_fotos(), nome_arquivo))

    apagar_foto_atual()
    current_user.foto = nome_arquivo
    db.session.commit()
    flash("Foto atualizada!", "sucesso")
    return redirect(url_for("perfil.editar"))


@perfil.route("/foto/remover", methods=["POST"])
@login_required
def remover_foto():
    apagar_foto_atual()
    current_user.foto = None
    db.session.commit()
    flash("Foto removida.", "sucesso")
    return redirect(url_for("perfil.editar"))


@perfil.route("/nome", methods=["POST"])
@login_required
def trocar_nome():
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("O nome não pode ficar vazio.", "erro")
    elif len(nome) > 100:
        flash("Nome muito longo (máximo de 100 caracteres).", "erro")
    else:
        current_user.nome = nome
        db.session.commit()
        flash("Nome atualizado!", "sucesso")
    return redirect(url_for("perfil.editar"))


@perfil.route("/email", methods=["POST"])
@login_required
def trocar_email():
    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")

    # Pedimos a senha atual: se alguém pegar seu computador logado,
    # não consegue trocar o e-mail da conta (e "roubar" ela) sem saber a senha.
    if not current_user.verificar_senha(senha):
        flash("Senha atual incorreta.", "erro")
    elif not EMAIL_VALIDO.fullmatch(email):
        flash("Digite um e-mail válido.", "erro")
    elif email == current_user.email:
        flash("Esse já é o seu e-mail.", "erro")
    elif Usuario.query.filter_by(email=email).first():
        flash("Já existe uma conta com esse e-mail.", "erro")
    else:
        current_user.email = email
        db.session.commit()
        flash("E-mail atualizado!", "sucesso")
    return redirect(url_for("perfil.editar"))


@perfil.app_errorhandler(413)
def arquivo_grande_demais(erro):
    """Erro 413 = o envio passou do MAX_CONTENT_LENGTH (2 MB, definido no app.py)."""
    flash("Imagem grande demais. O limite é 2 MB.", "erro")
    return redirect(url_for("perfil.editar"))
