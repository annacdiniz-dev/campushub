import os
from datetime import date, timedelta

from flask import Flask, redirect, render_template, url_for
from flask_login import LoginManager, current_user, login_required

from auth import auth
from materias import materias
from models import Atividade, Materia, Usuario, db

app = Flask(__name__)

# Endereço do banco: um arquivo SQLite dentro da pasta "instance/"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campushub.db"
# Chave usada para assinar o login (cookies). Em produção vem de variável de ambiente.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")

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

# Cria as tabelas que ainda não existem no banco
with app.app_context():
    db.create_all()


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
        materias=current_user.materias,
    )


if __name__ == "__main__":
    app.run(debug=True)
