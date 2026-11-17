"""Colegas: adicionar amigos pelo ID de 4 caracteres e ver a lista deles."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Amizade, Usuario, db

colegas = Blueprint("colegas", __name__, url_prefix="/colegas")


@colegas.route("/")
@login_required
def listar():
    # A busca vem pela URL (/colegas/?busca=K7P2), igual a uma pesquisa no Google.
    # .upper(): a pessoa pode digitar "k7p2" que acha "K7P2" do mesmo jeito.
    busca = request.args.get("busca", "").strip().upper().replace("#", "")
    encontrado = None
    if busca:
        encontrado = Usuario.query.filter_by(codigo=busca).first()

    return render_template(
        "colegas.html",
        busca=busca,
        encontrado=encontrado,
        meus_colegas=current_user.lista_colegas(),
    )


@colegas.route("/adicionar", methods=["POST"])
@login_required
def adicionar():
    codigo = request.form.get("codigo", "").strip().upper()
    outro = Usuario.query.filter_by(codigo=codigo).first()

    if outro is None:
        flash("Nenhum usuário com esse ID.", "erro")
    elif outro.id == current_user.id:
        flash("Esse ID é o seu!", "erro")
    elif current_user.eh_colega(outro.id):
        flash(f"{outro.nome} já é seu colega.", "erro")
    else:
        # A amizade vale para os dois lados: uma linha para cada direção
        db.session.add(Amizade(usuario_id=current_user.id, colega_id=outro.id))
        db.session.add(Amizade(usuario_id=outro.id, colega_id=current_user.id))
        db.session.commit()
        flash(f"{outro.nome} agora é seu colega!", "sucesso")
    return redirect(url_for("colegas.listar"))


@colegas.route("/<int:colega_id>/remover", methods=["POST"])
@login_required
def remover(colega_id):
    # Apaga as duas direções da amizade
    Amizade.query.filter(
        db.or_(
            db.and_(Amizade.usuario_id == current_user.id, Amizade.colega_id == colega_id),
            db.and_(Amizade.usuario_id == colega_id, Amizade.colega_id == current_user.id),
        )
    ).delete()
    db.session.commit()
    flash("Colega removido.", "sucesso")
    return redirect(url_for("colegas.listar"))
