import os
from datetime import date, timedelta

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required
from sqlalchemy import inspect, text

from atividades import atividades
from auth import auth
from materias import materias
from colegas import colegas
from models import STATUS, Atividade, Materia, Usuario, db, gerar_codigo_unico
from perfil import perfil

app = Flask(__name__)

# Endereço do banco: um arquivo SQLite dentro da pasta "instance/"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campushub.db"
# Chave usada para assinar o login (cookies). Em produção vem de variável de ambiente.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")
# Tamanho máximo de qualquer envio (arquivo de atividade, foto...): 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

db.init_app(app)

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
app.register_blueprint(auth)       # cadastro, login, logout (auth.py)
app.register_blueprint(materias)   # matérias (materias.py)
app.register_blueprint(atividades) # provas, trabalhos, projetos (atividades.py)
app.register_blueprint(perfil)     # editar foto, nome e e-mail (perfil.py)
app.register_blueprint(colegas)    # adicionar colegas pelo ID (colegas.py)

# Cria as tabelas que ainda não existem no banco
with app.app_context():
    db.create_all()

    # Mini "migração": o create_all() cria tabelas NOVAS, mas não adiciona colunas
    # novas numa tabela que já existe. Como a tabela "usuarios" já existia antes
    # da coluna "foto", adicionamos ela na mão (só se ainda não estiver lá).
    colunas = [c["name"] for c in inspect(db.engine).get_columns("usuarios")]
    if "foto" not in colunas:
        db.session.execute(text("ALTER TABLE usuarios ADD COLUMN foto VARCHAR(255)"))
        db.session.commit()

    # Mesma coisa para o ID de 4 caracteres...
    if "codigo" not in colunas:
        db.session.execute(text("ALTER TABLE usuarios ADD COLUMN codigo VARCHAR(4)"))
        # ...com um índice UNIQUE: o próprio banco recusa dois usuários com o mesmo ID
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_codigo ON usuarios (codigo)"))
        db.session.commit()
    # Quem criou a conta antes dos IDs existirem ganha um agora
    for usuario in Usuario.query.filter_by(codigo=None).all():
        usuario.codigo = gerar_codigo_unico()
        db.session.commit()  # um por vez, para o sorteio já enxergar os IDs anteriores


@app.errorhandler(413)
def envio_grande_demais(erro):
    """Erro 413 = o envio passou do MAX_CONTENT_LENGTH. Volta para a página de onde veio."""
    flash("Arquivo grande demais. O limite é 10 MB.", "erro")
    return redirect(request.referrer or url_for("painel"))


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("painel"))
    return render_template("home.html")


@app.route("/painel")
@login_required  # só entra quem está logado
def painel():
    # Todas as atividades do usuário logado (passando pelas matérias dele)
    atividades = (
        Atividade.query.join(Materia)
        .filter(Materia.usuario_id == current_user.id)
        .all()
    )

    hoje = date.today()
    em_7_dias = hoje + timedelta(days=7)

    # Números dos cartões do topo
    resumo = {
        "pendentes": sum(1 for a in atividades if a.status == "Pendente"),
        "andamento": sum(1 for a in atividades if a.status == "Em andamento"),
        "concluidas": sum(1 for a in atividades if a.status == "Concluído"),
        "semana": sum(
            1 for a in atividades
            if a.data_entrega and hoje <= a.data_entrega <= em_7_dias and a.status != "Concluído"
        ),
    }

    # Próximas entregas não concluídas, da mais próxima para a mais distante
    proximos = sorted(
        (a for a in atividades if a.data_entrega and a.data_entrega >= hoje and a.status != "Concluído"),
        key=lambda a: a.data_entrega,
    )[:5]

    return render_template(
        "painel.html",
        resumo=resumo,
        proximos=proximos,
        atividades=atividades,
        hoje=hoje,              # para calcular "faltam X dias" nos próximos prazos
        status_opcoes=STATUS,
    )


if __name__ == "__main__":
    app.run(debug=True)
