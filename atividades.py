"""Tudo sobre atividades (provas, trabalhos, projetos): criar, editar, excluir e mudar status."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import PRIORIDADES, STATUS, TIPOS, Atividade, Materia, db

atividades = Blueprint("atividades", __name__, url_prefix="/atividades")


def buscar_atividade(atividade_id):
    """Busca a atividade SÓ entre as do usuário logado.

    A atividade não guarda o dono direto: ela pertence a uma matéria,
    e a matéria pertence ao usuário. Por isso o join com Materia.
    """
    return (
        Atividade.query.join(Materia)
        .filter(Atividade.id == atividade_id, Materia.usuario_id == current_user.id)
        .first_or_404()
    )


def materias_do_usuario():
    return Materia.query.filter_by(usuario_id=current_user.id).order_by(Materia.nome).all()


def ler_formulario():
    """Pega os dados do formulário e devolve (dados, erro)."""
    form = request.form
    dados = {
        "titulo": form.get("titulo", "").strip(),
        "descricao": form.get("descricao", "").strip() or None,
        "tipo": form.get("tipo", ""),
        "prioridade": form.get("prioridade", ""),
        "status": form.get("status", "Pendente"),
        # Checkbox: se marcado, vem no formulário; se não, nem aparece
        "em_grupo": "em_grupo" in form,
        "materia_id": form.get("materia_id", type=int),
        "data_entrega": None,
    }

    erro = None
    data_texto = form.get("data_entrega", "")
    if data_texto:
        try:
            dados["data_entrega"] = date.fromisoformat(data_texto)  # "2026-11-20" -> date
        except ValueError:
            erro = "Data de entrega inválida."

    # Segurança: a matéria escolhida PRECISA ser do usuário logado.
    # Sem isso, alguém poderia editar o HTML e mandar o id da matéria de outra pessoa.
    materia = Materia.query.filter_by(id=dados["materia_id"], usuario_id=current_user.id).first()

    if not dados["titulo"]:
        erro = "Dê um título para a atividade."
    elif materia is None:
        erro = "Escolha uma matéria válida."
    elif dados["tipo"] not in TIPOS:
        erro = "Tipo inválido."
    elif dados["prioridade"] not in PRIORIDADES:
        erro = "Prioridade inválida."
    elif dados["status"] not in STATUS:
        erro = "Status inválido."
    return dados, erro


def mostrar_formulario(atividade, editando, atividade_id=None):
    """Renderiza o formulário (usado no GET e quando dá erro no POST)."""
    return render_template(
        "atividade_form.html",
        atividade=atividade,
        editando=editando,
        atividade_id=atividade_id,
        materias=materias_do_usuario(),
        tipos=TIPOS,
        prioridades=PRIORIDADES,
        status_opcoes=STATUS,
    )


@atividades.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    # Sem matéria não dá para criar atividade: manda criar uma primeiro
    if not materias_do_usuario():
        flash("Cadastre uma matéria antes de criar atividades.", "erro")
        return redirect(url_for("materias.nova"))

    if request.method == "POST":
        dados, erro = ler_formulario()
        if erro:
            flash(erro, "erro")
            return mostrar_formulario(dados, editando=False)

        db.session.add(Atividade(**dados))
        db.session.commit()
        flash(f"Atividade \"{dados['titulo']}\" criada!", "sucesso")
        return redirect(url_for("painel"))

    # Valores que já vêm preenchidos num formulário novo
    padrao = {"tipo": "Trabalho", "prioridade": "Média", "status": "Pendente"}
    return mostrar_formulario(padrao, editando=False)


@atividades.route("/<int:atividade_id>/editar", methods=["GET", "POST"])
@login_required
def editar(atividade_id):
    atividade = buscar_atividade(atividade_id)

    if request.method == "POST":
        dados, erro = ler_formulario()
        if erro:
            flash(erro, "erro")
            return mostrar_formulario(dados, editando=True, atividade_id=atividade.id)

        for campo, valor in dados.items():
            setattr(atividade, campo, valor)
        db.session.commit()
        flash("Atividade atualizada!", "sucesso")
        return redirect(url_for("painel"))

    return mostrar_formulario(atividade, editando=True, atividade_id=atividade.id)


@atividades.route("/<int:atividade_id>/status", methods=["POST"])
@login_required
def mudar_status(atividade_id):
    """Troca só o status, direto do painel, sem abrir o formulário inteiro."""
    atividade = buscar_atividade(atividade_id)
    novo = request.form.get("status")
    if novo in STATUS:
        atividade.status = novo
        db.session.commit()
    return redirect(url_for("painel"))


@atividades.route("/<int:atividade_id>/excluir", methods=["POST"])
@login_required
def excluir(atividade_id):
    atividade = buscar_atividade(atividade_id)
    titulo = atividade.titulo
    db.session.delete(atividade)  # os itens do checklist vão junto (cascade)
    db.session.commit()
    flash(f"Atividade \"{titulo}\" excluída.", "sucesso")
    return redirect(url_for("painel"))
