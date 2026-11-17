"""Tudo sobre atividades (provas, trabalhos, projetos): criar, editar, excluir e mudar status."""
import os
import uuid
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from materias import buscar_materia
from models import PRIORIDADES, STATUS, TIPOS, Arquivo, Atividade, Materia, MembroGrupo, db
from uploads import ABRE_NO_NAVEGADOR, EXTENSOES_PERMITIDAS, apagar_arquivos_da_atividade, pasta_da_atividade

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


def destino(materia_id, atividade_id=None):
    """Para onde voltar depois de salvar: página da atividade, da matéria ou o painel.

    Quem chama avisa com "voltar=atividade" ou "voltar=materia" (na URL ou num campo
    escondido do formulário). request.values junta os dois: request.args (URL) + request.form.
    """
    voltar = request.values.get("voltar")
    if voltar == "atividade" and atividade_id:
        return redirect(url_for("atividades.ver", atividade_id=atividade_id))
    if voltar in ("materia", "atividade"):
        return redirect(url_for("materias.ver", materia_id=materia_id))
    return redirect(url_for("painel"))


def ler_formulario(materia_id=None):
    """Pega os dados do formulário e devolve (dados, erro).

    materia_id: se vier preenchido, a matéria já está decidida (atividade nova
    criada dentro de uma matéria). Se não, ela vem do formulário (edição).
    """
    form = request.form
    dados = {
        "titulo": form.get("titulo", "").strip(),
        "descricao": form.get("descricao", "").strip() or None,
        "tipo": form.get("tipo", ""),
        "prioridade": form.get("prioridade", ""),
        "status": form.get("status", "Pendente"),
        # Checkbox: se marcado, vem no formulário; se não, nem aparece
        "em_grupo": "em_grupo" in form,
        "materia_id": materia_id or form.get("materia_id", type=int),
        "data_entrega": None,
    }

    erro = None
    data_texto = form.get("data_entrega", "")
    if data_texto:
        try:
            dados["data_entrega"] = date.fromisoformat(data_texto)  # "2026-11-20" -> date
        except ValueError:
            erro = "Data de entrega inválida."

    # Segurança: a matéria PRECISA ser do usuário logado.
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


def mostrar_formulario(atividade, editando, materia=None, atividade_id=None):
    """Renderiza o formulário (usado no GET e quando dá erro no POST)."""
    return render_template(
        "atividade_form.html",
        atividade=atividade,
        editando=editando,
        materia=materia,                  # só na criação: a matéria já escolhida
        atividade_id=atividade_id,
        voltar=request.values.get("voltar", "painel"),
        materias=Materia.query.filter_by(usuario_id=current_user.id).order_by(Materia.nome).all(),
        tipos=TIPOS,
        prioridades=PRIORIDADES,
        status_opcoes=STATUS,
    )


@atividades.route("/nova/<int:materia_id>", methods=["GET", "POST"])
@login_required
def nova(materia_id):
    # A matéria vem pela URL (/atividades/nova/3). buscar_materia garante que é sua.
    materia = buscar_materia(materia_id)

    if request.method == "POST":
        dados, erro = ler_formulario(materia_id=materia.id)
        if erro:
            flash(erro, "erro")
            return mostrar_formulario(dados, editando=False, materia=materia)

        db.session.add(Atividade(**dados))
        db.session.commit()
        flash(f"Atividade \"{dados['titulo']}\" criada!", "sucesso")
        return redirect(url_for("materias.ver", materia_id=materia.id))

    # Valores que já vêm preenchidos num formulário novo
    padrao = {"tipo": "Trabalho", "prioridade": "Média", "status": "Pendente"}
    return mostrar_formulario(padrao, editando=False, materia=materia)


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
        return destino(atividade.materia_id, atividade.id)

    return mostrar_formulario(atividade, editando=True, atividade_id=atividade.id)


@atividades.route("/<int:atividade_id>/status", methods=["POST"])
@login_required
def mudar_status(atividade_id):
    """Troca só o status, direto da lista, sem abrir o formulário inteiro."""
    atividade = buscar_atividade(atividade_id)
    novo = request.form.get("status")
    if novo in STATUS:
        atividade.status = novo
        db.session.commit()
    return destino(atividade.materia_id, atividade.id)


@atividades.route("/<int:atividade_id>/excluir", methods=["POST"])
@login_required
def excluir(atividade_id):
    atividade = buscar_atividade(atividade_id)
    titulo, materia_id = atividade.titulo, atividade.materia_id
    apagar_arquivos_da_atividade(atividade.id)  # os arquivos no disco
    db.session.delete(atividade)  # checklist, arquivos e colegas no banco vão junto (cascade)
    db.session.commit()
    flash(f"Atividade \"{titulo}\" excluída.", "sucesso")
    # Sem atividade_id: ela não existe mais, então "voltar=atividade" cai na página da matéria
    return destino(materia_id)


# =====================================================================
#  Página da atividade: descrição, arquivos e colegas
# =====================================================================

@atividades.route("/<int:atividade_id>")
@login_required
def ver(atividade_id):
    atividade = buscar_atividade(atividade_id)
    dias = (atividade.data_entrega - date.today()).days if atividade.data_entrega else None
    # Colegas que ainda NÃO estão no grupo: são as opções do botão "Adicionar colega"
    no_grupo = {m.usuario_id for m in atividade.membros}
    disponiveis = [c for c in current_user.lista_colegas() if c.id not in no_grupo]
    return render_template("atividade.html", atividade=atividade, dias=dias, status_opcoes=STATUS,
                           extensoes=sorted(EXTENSOES_PERMITIDAS), disponiveis=disponiveis)


@atividades.route("/<int:atividade_id>/descricao", methods=["POST"])
@login_required
def salvar_descricao(atividade_id):
    atividade = buscar_atividade(atividade_id)
    atividade.descricao = request.form.get("descricao", "").strip() or None
    db.session.commit()
    flash("Descrição salva!", "sucesso")
    return redirect(url_for("atividades.ver", atividade_id=atividade.id))


@atividades.route("/<int:atividade_id>/arquivos", methods=["POST"])
@login_required
def enviar_arquivo(atividade_id):
    atividade = buscar_atividade(atividade_id)
    voltar = redirect(url_for("atividades.ver", atividade_id=atividade.id))

    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Escolha um arquivo primeiro.", "erro")
        return voltar

    nome_original = os.path.basename(arquivo.filename)[:255]
    extensao = nome_original.rsplit(".", 1)[-1].lower() if "." in nome_original else ""
    if extensao not in EXTENSOES_PERMITIDAS:
        flash(f"Tipo de arquivo não aceito (.{extensao or '?'}).", "erro")
        return voltar

    # Mesmo cuidado da foto de perfil: no disco o arquivo ganha um nome aleatório
    nome_salvo = f"{uuid.uuid4().hex}.{extensao}"
    caminho = os.path.join(pasta_da_atividade(atividade.id), nome_salvo)
    arquivo.save(caminho)

    db.session.add(Arquivo(atividade_id=atividade.id, nome_original=nome_original,
                           nome_salvo=nome_salvo, tamanho=os.path.getsize(caminho)))
    db.session.commit()
    flash(f"\"{nome_original}\" adicionado!", "sucesso")
    return voltar


def buscar_arquivo(atividade, arquivo_id):
    """O arquivo precisa ser DESSA atividade (que por sua vez já foi conferida como sua)."""
    arquivo = Arquivo.query.filter_by(id=arquivo_id, atividade_id=atividade.id).first()
    if arquivo is None:
        abort(404)
    return arquivo


@atividades.route("/<int:atividade_id>/arquivos/<int:arquivo_id>")
@login_required
def abrir_arquivo(atividade_id, arquivo_id):
    atividade = buscar_atividade(atividade_id)
    arquivo = buscar_arquivo(atividade, arquivo_id)
    # PDF e imagem abrem no navegador; o resto é baixado com o nome original
    return send_from_directory(
        pasta_da_atividade(atividade.id),
        arquivo.nome_salvo,
        as_attachment=arquivo.extensao not in ABRE_NO_NAVEGADOR,
        download_name=arquivo.nome_original,
    )


@atividades.route("/<int:atividade_id>/arquivos/<int:arquivo_id>/excluir", methods=["POST"])
@login_required
def excluir_arquivo(atividade_id, arquivo_id):
    atividade = buscar_atividade(atividade_id)
    arquivo = buscar_arquivo(atividade, arquivo_id)
    caminho = os.path.join(pasta_da_atividade(atividade.id), arquivo.nome_salvo)
    if os.path.exists(caminho):
        os.remove(caminho)
    db.session.delete(arquivo)
    db.session.commit()
    flash(f"\"{arquivo.nome_original}\" removido.", "sucesso")
    return redirect(url_for("atividades.ver", atividade_id=atividade.id))


@atividades.route("/<int:atividade_id>/grupo", methods=["POST"])
@login_required
def adicionar_ao_grupo(atividade_id):
    atividade = buscar_atividade(atividade_id)
    usuario_id = request.form.get("usuario_id", type=int)
    ja_no_grupo = {m.usuario_id for m in atividade.membros}

    # Regra: só entra no grupo quem JÁ é seu colega (adicionado na página Colegas)
    if not atividade.em_grupo:
        flash("Essa atividade não está marcada como em grupo.", "erro")
    elif not usuario_id or not current_user.eh_colega(usuario_id):
        flash("Só dá para adicionar quem já é seu colega.", "erro")
    elif usuario_id in ja_no_grupo:
        flash("Essa pessoa já está no grupo.", "erro")
    else:
        membro = MembroGrupo(atividade_id=atividade.id, usuario_id=usuario_id)
        db.session.add(membro)
        db.session.commit()
        flash(f"{membro.usuario.nome} entrou no grupo!", "sucesso")
    return redirect(url_for("atividades.ver", atividade_id=atividade.id))


@atividades.route("/<int:atividade_id>/grupo/<int:membro_id>/remover", methods=["POST"])
@login_required
def remover_do_grupo(atividade_id, membro_id):
    atividade = buscar_atividade(atividade_id)
    membro = MembroGrupo.query.filter_by(id=membro_id, atividade_id=atividade.id).first_or_404()
    nome = membro.usuario.nome
    db.session.delete(membro)
    db.session.commit()
    flash(f"{nome} saiu do grupo.", "sucesso")
    return redirect(url_for("atividades.ver", atividade_id=atividade.id))
