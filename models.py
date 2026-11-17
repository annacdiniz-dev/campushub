import secrets

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Valores permitidos (assim ninguém grava "pendnte" ou "urgentíssimo" no banco)
TIPOS = ["Prova", "Trabalho", "Projeto", "Outro"]
STATUS = ["Pendente", "Em andamento", "Concluído"]
PRIORIDADES = ["Baixa", "Média", "Alta"]

# Letras e números do ID de usuário. Sem 0/O, 1/I/L: são fáceis de confundir quando alguém dita o ID.
ALFABETO_ID = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def gerar_codigo_unico():
    """Sorteia um ID de 4 caracteres (ex.: "K7P2") que ainda nenhum usuário tem.

    31 caracteres possíveis em 4 posições = 31^4 ≈ 923 mil IDs diferentes.
    """
    while True:
        codigo = "".join(secrets.choice(ALFABETO_ID) for _ in range(4))
        if not Usuario.query.filter_by(codigo=codigo).first():
            return codigo


class Usuario(UserMixin, db.Model):  # UserMixin ensina o Flask-Login a lidar com o usuário
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    # Só o NOME do arquivo da foto (ex.: "3_a1b2c3.jpg"). A imagem fica em static/uploads/fotos/
    foto = db.Column(db.String(255), nullable=True)
    # ID público de 4 caracteres que a pessoa passa para os amigos (ex.: "K7P2")
    codigo = db.Column(db.String(4), unique=True, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # Atalho: usuario.materias -> lista de matérias desse usuário
    materias = db.relationship("Materia", back_populates="usuario", cascade="all, delete-orphan")

    def lista_colegas(self):
        """Os colegas deste usuário, em ordem alfabética."""
        amizades = Amizade.query.filter_by(usuario_id=self.id).all()
        return sorted((a.colega for a in amizades), key=lambda u: u.nome.lower())

    def eh_colega(self, outro_id):
        return Amizade.query.filter_by(usuario_id=self.id, colega_id=outro_id).first() is not None

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
    arquivos = db.relationship("Arquivo", back_populates="atividade", cascade="all, delete-orphan",
                               order_by="Arquivo.enviado_em")
    membros = db.relationship("MembroGrupo", back_populates="atividade", cascade="all, delete-orphan")

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


class Arquivo(db.Model):
    """Arquivo anexado a uma atividade (PDF da lista, slides, foto do quadro...)."""
    __tablename__ = "arquivos"

    id = db.Column(db.Integer, primary_key=True)
    atividade_id = db.Column(db.Integer, db.ForeignKey("atividades.id"), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)  # como a pessoa chamou ("Lista 3.pdf")
    nome_salvo = db.Column(db.String(100), nullable=False)     # nome aleatório no disco ("a1b2c3.pdf")
    tamanho = db.Column(db.Integer, nullable=False)            # em bytes
    enviado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    atividade = db.relationship("Atividade", back_populates="arquivos")

    @property
    def extensao(self):
        return self.nome_original.rsplit(".", 1)[-1].lower() if "." in self.nome_original else ""

    @property
    def tamanho_legivel(self):
        """1536 -> "1,5 KB"; 2097152 -> "2,0 MB"."""
        if self.tamanho < 1024:
            return f"{self.tamanho} B"
        if self.tamanho < 1024 * 1024:
            return f"{self.tamanho / 1024:.1f} KB".replace(".", ",")
        return f"{self.tamanho / 1024 / 1024:.1f} MB".replace(".", ",")


class Amizade(db.Model):
    """"usuario" tem "colega" na lista dele.

    A amizade vale para os dois lados, então ela é guardada em DUAS linhas:
    (Anna -> Bruno) e (Bruno -> Anna). Assim cada um acha os seus colegas com uma busca simples.
    """
    __tablename__ = "amizades"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    colega_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    # Duas colunas apontam para "usuarios", então dizemos qual coluna esse atalho usa
    colega = db.relationship("Usuario", foreign_keys=[colega_id])

    # Impede a mesma amizade duplicada
    __table_args__ = (db.UniqueConstraint("usuario_id", "colega_id", name="uq_amizade"),)


class MembroGrupo(db.Model):
    """Um colega que faz parte do grupo de uma atividade."""
    __tablename__ = "membros_grupo"

    id = db.Column(db.Integer, primary_key=True)
    atividade_id = db.Column(db.Integer, db.ForeignKey("atividades.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    atividade = db.relationship("Atividade", back_populates="membros")
    usuario = db.relationship("Usuario")

    __table_args__ = (db.UniqueConstraint("atividade_id", "usuario_id", name="uq_membro"),)
