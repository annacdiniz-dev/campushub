import os

from flask import Flask, render_template

from models import db

app = Flask(__name__)

# Endereço do banco: um arquivo SQLite dentro da pasta "instance/"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campushub.db"
# Chave usada para assinar o login (cookies). Em produção vem de variável de ambiente.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "chave-de-desenvolvimento")

db.init_app(app)

# Cria as tabelas que ainda não existem no banco
with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("home.html")


if __name__ == "__main__":
    app.run(debug=True)
