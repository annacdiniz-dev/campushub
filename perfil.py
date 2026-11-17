"""Página "Editar perfil": foto, nome, e-mail e os direitos da LGPD (baixar dados e excluir conta)."""
import json
import os
import re
import uuid

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user

from datas import agora_brasil
from models import Amizade, CodigoSenha, MembroGrupo, SolicitacaoAmizade, Usuario, db, ordenar_atividades
from lembretes import ler_token_desligar
from uploads import apagar_arquivos_da_atividade

perfil = Blueprint("perfil", __name__, url_prefix="/perfil")

EXTENSOES_FOTO = {"png", "jpg", "jpeg", "webp", "gif"}
TAMANHO_MAX_FOTO = 2 * 1024 * 1024  # 2 MB
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

    # Foto tem limite próprio (2 MB), menor que o geral do site (10 MB).
    # seek(0, 2) pula para o fim do arquivo; tell() diz em que posição está = tamanho.
    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)  # volta para o começo, senão o save() salvaria um arquivo vazio
    if tamanho > TAMANHO_MAX_FOTO:
        flash("Imagem grande demais. O limite é 2 MB.", "erro")
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


# =====================================================================
#  LGPD: baixar meus dados e excluir conta
# =====================================================================

@perfil.route("/meus-dados")
@login_required
def baixar_dados():
    """Gera um arquivo .json com TUDO que o CampusHub guarda sobre a pessoa (direito de acesso da LGPD)."""
    u = current_user
    dados = {
        "gerado_em": agora_brasil().strftime("%d/%m/%Y %H:%M"),
        "conta": {
            "nome": u.nome,
            "email": u.email,
            "id_campushub": u.codigo,
            "conta_criada_em": u.criado_em.strftime("%d/%m/%Y %H:%M") if u.criado_em else None,
            "tem_foto": bool(u.foto),
        },
        "colegas": [{"nome": c.nome, "id_campushub": c.codigo} for c in u.lista_colegas()],
        "materias": [
            {
                "nome": m.nome,
                "professor": m.professor,
                "semestre": m.semestre,
                "cor": m.cor,
                "atividades": [
                    {
                        "titulo": a.titulo,
                        "tipo": a.tipo,
                        "status": a.status,
                        "prioridade": a.prioridade,
                        "em_grupo": a.em_grupo,
                        "data_entrega": a.data_entrega.strftime("%d/%m/%Y") if a.data_entrega else None,
                        "descricao": a.descricao,
                        "arquivos": [arq.nome_original for arq in a.arquivos],
                        "grupo": [mb.usuario.nome for mb in a.membros],
                    }
                    for a in ordenar_atividades(m.atividades)
                ],
            }
            for m in u.materias
        ],
    }
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2)
    # Content-Disposition: attachment -> o navegador baixa o arquivo em vez de mostrar na tela
    return Response(conteudo, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=meus-dados-campushub.json"})


@perfil.route("/excluir-conta", methods=["POST"])
@login_required
def excluir_conta():
    """Apaga a conta e TUDO ligado a ela (direito de eliminação da LGPD)."""
    if not current_user.verificar_senha(request.form.get("senha", "")):
        flash("Senha incorreta. A conta NÃO foi excluída.", "erro")
        return redirect(url_for("perfil.editar"))

    usuario = db.session.get(Usuario, current_user.id)

    # 1) Arquivos no disco: anexos das atividades e a foto
    for materia in usuario.materias:
        for atividade in materia.atividades:
            apagar_arquivos_da_atividade(atividade.id)
    apagar_foto_atual()

    # 2) Ligações com outras pessoas: amizades (os dois lados) e participação em grupos de outros
    Amizade.query.filter(db.or_(Amizade.usuario_id == usuario.id, Amizade.colega_id == usuario.id)).delete()
    MembroGrupo.query.filter_by(usuario_id=usuario.id).delete()
    CodigoSenha.query.filter_by(usuario_id=usuario.id).delete()
    SolicitacaoAmizade.query.filter(
        db.or_(SolicitacaoAmizade.de_id == usuario.id, SolicitacaoAmizade.para_id == usuario.id)
    ).delete()

    # 3) A conta: as matérias vão junto (cascade), e com elas atividades, arquivos e grupos
    logout_user()
    db.session.delete(usuario)
    db.session.commit()

    flash("Sua conta e todos os seus dados foram excluídos. Sentiremos sua falta!", "sucesso")
    return redirect(url_for("home"))


# =====================================================================
#  Lembretes por e-mail: ligar/desligar
# =====================================================================

@perfil.route("/lembretes", methods=["POST"])
@login_required
def trocar_lembretes():
    current_user.lembretes_email = "lembretes" in request.form  # checkbox marcado = ligado
    db.session.commit()
    flash("Lembretes por e-mail ligados!" if current_user.lembretes_email else "Lembretes por e-mail desligados.", "sucesso")
    return redirect(url_for("perfil.editar"))


@perfil.route("/lembretes/desligar/<token>", methods=["GET", "POST"])
def desligar_pelo_email(token):
    """O link "Não quero mais receber" do e-mail. Funciona sem login.

    Abrir o link (GET) só MOSTRA a página com um botão; quem desliga é o clique (POST).
    Motivo: alguns programas de e-mail "abrem" os links sozinhos para checar se são
    seguros — se o GET já desligasse, os lembretes sumiriam sem a pessoa pedir.
    """
    usuario_id = ler_token_desligar(current_app.config["SECRET_KEY"], token)
    usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None:
        flash("Esse link não é válido.", "erro")
        return redirect(url_for("home"))

    if request.method == "POST":
        usuario.lembretes_email = False
        db.session.commit()
        return render_template("lembretes_desligar.html", feito=True)
    return render_template("lembretes_desligar.html", feito=False)
