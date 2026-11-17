import secrets

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from datas import hoje

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
    # Proteção do login: senhas erradas seguidas e até quando a conta fica bloqueada
    tentativas_falhas = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    # LGPD: quando a pessoa aceitou a Política de Privacidade
    aceitou_termos_em = db.Column(db.DateTime, nullable=True)
    # Quer receber os lembretes de entrega por e-mail? (dá para desligar no perfil ou pelo link do e-mail)
    lembretes_email = db.Column(db.Boolean, nullable=False, default=True)

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
    lembretes = db.relationship("LembreteEnviado", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(f"tipo IN {tuple(TIPOS)}", name="ck_tipo"),
        db.CheckConstraint(f"status IN {tuple(STATUS)}", name="ck_status"),
        db.CheckConstraint(f"prioridade IN {tuple(PRIORIDADES)}", name="ck_prioridade"),
    )

    @property
    def atrasada(self):
        """Passou da data de entrega e ainda não foi concluída."""
        return bool(self.data_entrega) and self.data_entrega < hoje() and self.status != "Concluído"


def ordenar_atividades(atividades):
    """Ordem "inteligente" das listas de atividades:

    1. Atrasadas (a mais antiga primeiro — é a mais urgente)
    2. Com data de entrega, da mais próxima para a mais distante
    3. Sem data de entrega
    4. Concluídas por último (a entregue mais recentemente primeiro)

    sorted() compara as tuplas da "chave" item por item: primeiro o grupo (0 a 3), depois a data.
    """
    def chave(a):
        if a.status == "Concluído":
            # Número negativo da data: inverte a ordem (mais recente primeiro)
            return (3, -(a.data_entrega.toordinal() if a.data_entrega else 0))
        if a.atrasada:
            return (0, a.data_entrega.toordinal())
        if a.data_entrega:
            return (1, a.data_entrega.toordinal())
        return (2, 0)

    return sorted(atividades, key=chave)


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


class CodigoSenha(db.Model):
    """Código de 6 números enviado por e-mail para redefinir a senha ("Esqueci minha senha")."""
    __tablename__ = "codigos_senha"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    # Guardamos o código "embaralhado", igual à senha: quem olhar o banco não vê o código
    codigo_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False)
    expira_em = db.Column(db.DateTime, nullable=False)
    tentativas = db.Column(db.Integer, nullable=False, default=0)  # códigos errados digitados
    usado = db.Column(db.Boolean, nullable=False, default=False)

    def confere(self, codigo):
        return check_password_hash(self.codigo_hash, codigo)


class LembreteEnviado(db.Model):
    """Anota cada lembrete mandado, para ninguém receber o mesmo e-mail duas vezes.

    A data de entrega faz parte da anotação: se a pessoa mudar a data, os lembretes
    da data nova são outros (e chegam de novo, na hora certa).
    """
    __tablename__ = "lembretes_enviados"

    id = db.Column(db.Integer, primary_key=True)
    atividade_id = db.Column(db.Integer, db.ForeignKey("atividades.id", ondelete="CASCADE"), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)        # "7dias" ou "1dia"
    data_entrega = db.Column(db.Date, nullable=False)
    enviado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    __table_args__ = (db.UniqueConstraint("atividade_id", "tipo", "data_entrega", name="uq_lembrete"),)


class SolicitacaoAmizade(db.Model):
    """Pedido de amizade esperando resposta: "de" quer ser colega de "para".

    Quando "para" aceita, o pedido some e vira Amizade (nos dois sentidos).
    """
    __tablename__ = "solicitacoes_amizade"

    id = db.Column(db.Integer, primary_key=True)
    de_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    para_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    de = db.relationship("Usuario", foreign_keys=[de_id])
    para = db.relationship("Usuario", foreign_keys=[para_id])

    __table_args__ = (db.UniqueConstraint("de_id", "para_id", name="uq_solicitacao"),)
