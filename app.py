import os
from datetime import timedelta

# Antes de tudo: lê os segredos do arquivo .env (senha do Gmail, SECRET_KEY...)
from config_env import carregar_env
carregar_env()

from flask import Flask, flash, has_request_context, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import inspect, text

from atividades import atividades
from auth import auth
from colegas import colegas
from datas import hoje
from materias import materias
from models import (STATUS, Atividade, Materia, SolicitacaoAmizade, Usuario, db, gerar_codigo_unico,
                    ordenar_atividades)
from perfil import perfil

app = Flask(__name__)

# Endereço do banco: um arquivo SQLite dentro da pasta "instance/"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campushub.db"
# Chave usada para assinar o login (cookies). Em produção vem de variável de ambiente.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")
# Tamanho máximo de qualquer envio (arquivo de atividade, foto...): 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
# O "token" anti-CSRF de cada página vale por 8 horas (o padrão é 1 hora: curto para quem
# deixa a aba do CampusHub aberta estudando)
app.config["WTF_CSRF_TIME_LIMIT"] = 8 * 60 * 60
# E-mail de contato mostrado na Política de Privacidade (o mesmo Gmail que envia os avisos)
app.config["CONTATO_EMAIL"] = os.environ.get("EMAIL_USUARIO")

db.init_app(app)

# Proteção contra CSRF: todo formulário POST precisa mandar um código secreto (csrf_token)
# que só as páginas do CampusHub têm. Um site malicioso não consegue saber esse código,
# então não consegue enviar formulários "em nome" de quem está logado.
csrf = CSRFProtect(app)

# Login: quem não estiver logado e tentar abrir página protegida vai para /login
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Entre na sua conta para acessar essa página."
login_manager.login_message_category = "erro"


@login_manager.user_loader
def carregar_usuario(usuario_id):
    """A cada página, o Flask-Login usa isso para descobrir quem está logado."""
    return db.session.get(Usuario, int(usuario_id))


# Conecta os "pedaços" do site
app.register_blueprint(auth)       # cadastro, login, senha, privacidade (auth.py)
app.register_blueprint(materias)   # matérias (materias.py)
app.register_blueprint(atividades) # provas, trabalhos, projetos (atividades.py)
app.register_blueprint(perfil)     # foto, nome, e-mail, dados e excluir conta (perfil.py)
app.register_blueprint(colegas)    # adicionar colegas pelo ID (colegas.py)


def adicionar_coluna_se_faltar(tabela, coluna, tipo_sql):
    """Mini "migração": o create_all() cria tabelas NOVAS, mas não adiciona colunas
    novas numa tabela que já existe. Então, se a coluna ainda não estiver lá, criamos na mão."""
    colunas = [c["name"] for c in inspect(db.engine).get_columns(tabela)]
    if coluna not in colunas:
        db.session.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo_sql}"))
        db.session.commit()


with app.app_context():
    db.create_all()  # cria as tabelas que ainda não existem

    adicionar_coluna_se_faltar("usuarios", "foto", "VARCHAR(255)")
    adicionar_coluna_se_faltar("usuarios", "codigo", "VARCHAR(4)")
    adicionar_coluna_se_faltar("usuarios", "tentativas_falhas", "INTEGER NOT NULL DEFAULT 0")
    adicionar_coluna_se_faltar("usuarios", "bloqueado_ate", "DATETIME")
    adicionar_coluna_se_faltar("usuarios", "aceitou_termos_em", "DATETIME")
    adicionar_coluna_se_faltar("usuarios", "lembretes_email", "BOOLEAN NOT NULL DEFAULT 1")
    # Índice UNIQUE: o próprio banco recusa dois usuários com o mesmo ID
    db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_codigo ON usuarios (codigo)"))
    db.session.commit()

    # Quem criou a conta antes dos IDs existirem ganha um agora
    for usuario in Usuario.query.filter_by(codigo=None).all():
        usuario.codigo = gerar_codigo_unico()
        db.session.commit()  # um por vez, para o sorteio já enxergar os IDs anteriores


@app.context_processor
def dados_de_todas_as_paginas():
    """O que for devolvido aqui fica disponível em TODOS os templates.
    Usado pelo botão flutuante "+", que lista as matérias para criar uma atividade.

    has_request_context(): quando os lembretes são montados pela tarefa agendada, não existe
    uma pessoa acessando o site (nem "current_user") — aí não há menu para montar."""
    if has_request_context() and current_user and current_user.is_authenticated:
        return {
            "materias_menu": sorted(current_user.materias, key=lambda m: m.nome.lower()),
            # Número vermelho no "Colegas" do menu: solicitações de amizade esperando resposta
            "solicitacoes_pendentes": SolicitacaoAmizade.query.filter_by(para_id=current_user.id).count(),
        }
    return {}


@app.errorhandler(413)
def envio_grande_demais(erro):
    """Erro 413 = o envio passou do MAX_CONTENT_LENGTH. Volta para a página de onde veio."""
    flash("Arquivo grande demais. O limite é 10 MB.", "erro")
    return redirect(request.referrer or url_for("painel"))


@app.errorhandler(CSRFError)
def csrf_invalido(erro):
    """Formulário sem o código anti-CSRF (ou com a página aberta há muito tempo)."""
    flash("A página ficou aberta por muito tempo. Tente de novo.", "erro")
    return redirect(request.referrer or url_for("home"))


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("painel"))
    return render_template("home.html")


@app.route("/painel")
@login_required  # só entra quem está logado
def painel():
    # Todas as atividades do usuário logado (passando pelas matérias dele), em ordem inteligente
    atividades = ordenar_atividades(
        Atividade.query.join(Materia).filter(Materia.usuario_id == current_user.id).all()
    )

    dia = hoje()
    em_7_dias = dia + timedelta(days=7)

    # Números dos cartões do topo
    resumo = {
        "pendentes": sum(1 for a in atividades if a.status == "Pendente"),
        "andamento": sum(1 for a in atividades if a.status == "Em andamento"),
        "concluidas": sum(1 for a in atividades if a.status == "Concluído"),
        "semana": sum(
            1 for a in atividades
            if a.data_entrega and dia <= a.data_entrega <= em_7_dias and a.status != "Concluído"
        ),
        "atrasadas": sum(1 for a in atividades if a.atrasada),
    }

    # Próximas entregas não concluídas, da mais próxima para a mais distante
    proximos = sorted(
        (a for a in atividades if a.data_entrega and a.data_entrega >= dia and a.status != "Concluído"),
        key=lambda a: a.data_entrega,
    )[:5]

    return render_template(
        "painel.html",
        resumo=resumo,
        proximos=proximos,
        atividades=atividades,
        hoje=dia,               # para calcular "faltam X dias" nos próximos prazos
        status_opcoes=STATUS,
    )


if __name__ == "__main__":
    app.run(debug=True)
