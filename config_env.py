"""Lê o arquivo .env e coloca cada linha CHAVE=valor nas variáveis de ambiente.

O .env guarda segredos (senha do Gmail, SECRET_KEY...). Ele NÃO vai para o GitHub
(está no .gitignore): existe só no seu computador e no servidor.
Veja o .env.exemplo para saber o que colocar nele.
"""
import os


def carregar_env(caminho=None):
    caminho = caminho or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue  # pula linhas vazias e comentários
            chave, valor = linha.split("=", 1)
            # setdefault: se a variável já existir (ex.: definida no WSGI), ela vale mais que o .env
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))
