import os

from flask import Flask, redirect, render_template, url_for
from flask_login import LoginManager, current_user, login_required

from auth import auth
from models import Usuario, db

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


# Conecta as rotas de cadastro/login/logout (arquivo auth.py)
app.register_blueprint(auth)

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
    return render_template("painel.html")


if __name__ == "__main__":
    app.run(debug=True)
