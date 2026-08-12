from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Usuario(db.Model):

    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    senha_hash = db.Column(db.String(255), nullable=False)

    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class Materia(db.Model):

    __tablename__ = "materias"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    nome = db.Column(db.String(100), nullable=False)

    cor = db.Column(db.String(7), nullable=False) 

    ativa = db.Column(db.Boolean, nullable=False, default=True) 

    professor = db.Column(db.String(100), nullable=True)

    semestre = db.Column(db.String(20), nullable=True)

class Atividade(db.Model):

    __tablename__ = "atividades"

    id = db.Column(db.Integer, primary_key=True)

    materia_id = db.Column(db.Integer, db.ForeignKey("materias.id"), nullable=False)

    titulo = db.Column(db.String(100), nullable=False)

    descricao = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="Pendente")

    prioridade = db.Column(db.String(20), nullable=False, default="Média") 

    data_entrega = db.Column(db.Date, nullable=True) 

    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

