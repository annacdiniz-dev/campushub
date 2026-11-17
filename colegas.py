"""Colegas: buscar pelo ID, mandar solicitação de amizade, aceitar/recusar e ver a lista."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from emails import enviar_email
from lembretes import site_url
from models import Amizade, SolicitacaoAmizade, Usuario, db

colegas = Blueprint("colegas", __name__, url_prefix="/colegas")


def limpar_id(texto):
    """Deixa o ID digitado no formato do banco: "  #k7p2 " -> "K7P2"."""
    return texto.strip().upper().replace("#", "").replace(" ", "")


def solicitacao_entre(de_id, para_id):
    return SolicitacaoAmizade.query.filter_by(de_id=de_id, para_id=para_id).first()


def virar_amigos(a_id, b_id):
    """Cria a amizade nos dois sentidos e apaga os pedidos que existirem entre os dois."""
    db.session.add(Amizade(usuario_id=a_id, colega_id=b_id))
    db.session.add(Amizade(usuario_id=b_id, colega_id=a_id))
    SolicitacaoAmizade.query.filter(
        db.or_(
            db.and_(SolicitacaoAmizade.de_id == a_id, SolicitacaoAmizade.para_id == b_id),
            db.and_(SolicitacaoAmizade.de_id == b_id, SolicitacaoAmizade.para_id == a_id),
        )
    ).delete()


@colegas.route("/")
@login_required
def listar():
    # A busca vem pela URL (/colegas/?busca=K7P2), igual a uma pesquisa no Google
    busca = limpar_id(request.args.get("busca", ""))
    encontrado = Usuario.query.filter_by(codigo=busca).first() if busca else None

    # Como está a relação com quem foi encontrado (para mostrar o botão certo)
    situacao = None
    if encontrado:
        if encontrado.id == current_user.id:
            situacao = "eu"
        elif current_user.eh_colega(encontrado.id):
            situacao = "colega"
        elif solicitacao_entre(current_user.id, encontrado.id):
            situacao = "enviada"      # eu já pedi; esperando a pessoa
        elif solicitacao_entre(encontrado.id, current_user.id):
            situacao = "recebida"     # a pessoa já me pediu; posso aceitar
        else:
            situacao = "nada"

    recebidas = (SolicitacaoAmizade.query.filter_by(para_id=current_user.id)
                 .order_by(SolicitacaoAmizade.criado_em.desc()).all())
    enviadas = (SolicitacaoAmizade.query.filter_by(de_id=current_user.id)
                .order_by(SolicitacaoAmizade.criado_em.desc()).all())

    return render_template(
        "colegas.html",
        busca=busca,
        encontrado=encontrado,
        situacao=situacao,
        meus_colegas=current_user.lista_colegas(),
        recebidas=recebidas,
        enviadas=enviadas,
    )


@colegas.route("/solicitar", methods=["POST"])
@login_required
def solicitar():
    """Manda o pedido de amizade para o dono do ID."""
    outro = Usuario.query.filter_by(codigo=limpar_id(request.form.get("codigo", ""))).first()

    if outro is None:
        flash("Nenhum usuário com esse ID.", "erro")
    elif outro.id == current_user.id:
        flash("Esse ID é o seu!", "erro")
    elif current_user.eh_colega(outro.id):
        flash(f"{outro.nome} já é seu colega.", "erro")
    elif solicitacao_entre(current_user.id, outro.id):
        flash(f"Você já mandou uma solicitação para {outro.nome}. Agora é esperar!", "erro")
    elif solicitacao_entre(outro.id, current_user.id):
        # A outra pessoa já tinha pedido: os dois querem, então já viram colegas
        virar_amigos(current_user.id, outro.id)
        db.session.commit()
        flash(f"{outro.nome} também tinha te adicionado: agora vocês são colegas!", "sucesso")
    else:
        db.session.add(SolicitacaoAmizade(de_id=current_user.id, para_id=outro.id))
        db.session.commit()
        # Avisa a pessoa por e-mail (além do aviso dentro do site)
        enviar_email(
            outro.email,
            f"{current_user.nome} quer ser seu colega no CampusHub",
            f"Olá, {outro.nome.split()[0]}!\n\n"
            f"{current_user.nome} (ID {current_user.codigo}) te mandou uma solicitação de amizade no CampusHub.\n"
            f"Para aceitar ou recusar, entre em: {site_url()}/colegas/\n",
        )
        flash(f"Solicitação enviada para {outro.nome}! Quando aceitar, vocês viram colegas.", "sucesso")
    return redirect(url_for("colegas.listar"))


def buscar_solicitacao(solicitacao_id, *, sou="para"):
    """Só deixa mexer na solicitação quem faz parte dela (quem recebeu, ou quem enviou)."""
    filtro = {"id": solicitacao_id, ("para_id" if sou == "para" else "de_id"): current_user.id}
    return SolicitacaoAmizade.query.filter_by(**filtro).first_or_404()


@colegas.route("/solicitacoes/<int:solicitacao_id>/aceitar", methods=["POST"])
@login_required
def aceitar(solicitacao_id):
    pedido = buscar_solicitacao(solicitacao_id, sou="para")
    nome = pedido.de.nome
    virar_amigos(pedido.de_id, current_user.id)
    db.session.commit()
    flash(f"Agora você e {nome} são colegas!", "sucesso")
    return redirect(url_for("colegas.listar"))


@colegas.route("/solicitacoes/<int:solicitacao_id>/recusar", methods=["POST"])
@login_required
def recusar(solicitacao_id):
    pedido = buscar_solicitacao(solicitacao_id, sou="para")
    db.session.delete(pedido)
    db.session.commit()
    flash("Solicitação recusada.", "sucesso")
    return redirect(url_for("colegas.listar"))


@colegas.route("/solicitacoes/<int:solicitacao_id>/cancelar", methods=["POST"])
@login_required
def cancelar(solicitacao_id):
    pedido = buscar_solicitacao(solicitacao_id, sou="de")
    db.session.delete(pedido)
    db.session.commit()
    flash("Solicitação cancelada.", "sucesso")
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
