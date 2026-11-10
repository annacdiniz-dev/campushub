"""Tudo sobre matérias: listar, criar, editar e excluir."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Materia, db

materias = Blueprint("materias", __name__, url_prefix="/materias")

COR_PADRAO = "#6C63FF"


def buscar_materia(materia_id):
    """Busca a matéria SÓ entre as do usuário logado. Se não for dele: erro 404."""
    return Materia.query.filter_by(id=materia_id, usuario_id=current_user.id).first_or_404()


def ler_formulario():
    """Pega os dados do formulário e devolve (dados, erro)."""
    dados = {
        "nome": request.form.get("nome", "").strip(),
        "cor": request.form.get("cor", COR_PADRAO).strip(),
        "professor": request.form.get("professor", "").strip() or None,
        "semestre": request.form.get("semestre", "").strip() or None,
    }
    erro = None
    if not dados["nome"]:
        erro = "Dê um nome para a matéria."
    elif not re.fullmatch(r"#[0-9A-Fa-f]{6}", dados["cor"]):
        erro = "Cor inválida."
    return dados, erro


@materias.route("/")
@login_required
def listar():
    lista = Materia.query.filter_by(usuario_id=current_user.id).order_by(Materia.nome).all()
    return render_template("materias.html", materias=lista)


@materias.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    if request.method == "POST":
        dados, erro = ler_formulario()
        if erro:
            flash(erro, "erro")
            return render_template("materia_form.html", materia=dados, editando=False)

        db.session.add(Materia(usuario_id=current_user.id, **dados))
        db.session.commit()
        flash(f"Matéria \"{dados['nome']}\" criada!", "sucesso")
        return redirect(url_for("materias.listar"))

    return render_template("materia_form.html", materia={"cor": COR_PADRAO}, editando=False)


@materias.route("/<int:materia_id>/editar", methods=["GET", "POST"])
@login_required
def editar(materia_id):
    materia = buscar_materia(materia_id)

    if request.method == "POST":
        dados, erro = ler_formulario()
        if erro:
            flash(erro, "erro")
            return render_template("materia_form.html", materia=dados, editando=True, materia_id=materia.id)

        for campo, valor in dados.items():
            setattr(materia, campo, valor)  # materia.nome = ..., materia.cor = ...
        db.session.commit()
        flash("Matéria atualizada!", "sucesso")
        return redirect(url_for("materias.listar"))

    return render_template("materia_form.html", materia=materia, editando=True, materia_id=materia.id)


@materias.route("/<int:materia_id>/excluir", methods=["POST"])
@login_required
def excluir(materia_id):
    materia = buscar_materia(materia_id)
    nome = materia.nome
    db.session.delete(materia)  # as atividades dela vão junto (cascade)
    db.session.commit()
    flash(f"Matéria \"{nome}\" excluída.", "sucesso")
    return redirect(url_for("materias.listar"))
