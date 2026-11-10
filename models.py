from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Valores permitidos (assim ninguém grava "pendnte" ou "urgentíssimo" no banco)
TIPOS = ["Prova", "Trabalho", "Projeto", "Outro"]
STATUS = ["Pendente", "Em andamento", "Concluído"]
PRIORIDADES = ["Baixa", "Média", "Alta"]


class Usuario(UserMixin, db.Model):  # UserMixin ensina o Flask-Login a lidar com o usuário
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # Atalho: usuario.materias -> lista de matérias desse usuário
    materias = db.relationship("Materia", back_populates="usuario", cascade="all, delete-orphan")

    def definir_senha(self, senha):
        """Embaralha a senha antes de guardar (nunca salvamos a senha original)."""
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        """Confere se a senha digitada bate com a embaralhada."""
        return check_password_hash(self.senha_hash, senha)


class Materia(db.Model):
    __tablename__ = "materias"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    cor = db.Column(db.String(7), nullable=False, default="#6C63FF")  # cor em hexadecimal
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    professor = db.Column(db.String(100), nullable=True)
    semestre = db.Column(db.String(20), nullable=True)

    usuario = db.relationship("Usuario", back_populates="materias")
    atividades = db.relationship("Atividade", back_populates="materia", cascade="all, delete-orphan")


class Atividade(db.Model):
    __tablename__ = "atividades"

    id = db.Column(db.Integer, primary_key=True)
    materia_id = db.Column(db.Integer, db.ForeignKey("materias.id"), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    tipo = db.Column(db.String(20), nullable=False, default="Trabalho")
    em_grupo = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="Pendente")
    prioridade = db.Column(db.String(20), nullable=False, default="Média")
    data_entrega = db.Column(db.Date, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    materia = db.relationship("Materia", back_populates="atividades")
    checklist = db.relationship("ChecklistItem", back_populates="atividade", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"tipo IN {tuple(TIPOS)}", name="ck_tipo"),
        db.CheckConstraint(f"status IN {tuple(STATUS)}", name="ck_status"),
        db.CheckConstraint(f"prioridade IN {tuple(PRIORIDADES)}", name="ck_prioridade"),
    )

    @property
    def progresso(self):
        """Porcentagem do checklist concluída (0 a 100)."""
        if not self.checklist:
            return 0
        feitos = sum(1 for item in self.checklist if item.concluido)
        return round(feitos / len(self.checklist) * 100)


class ChecklistItem(db.Model):
    __tablename__ = "checklist_itens"

    id = db.Column(db.Integer, primary_key=True)
    atividade_id = db.Column(db.Integer, db.ForeignKey("atividades.id"), nullable=False)
    texto = db.Column(db.String(200), nullable=False)
    concluido = db.Column(db.Boolean, nullable=False, default=False)

    atividade = db.relationship("Atividade", back_populates="checklist")
