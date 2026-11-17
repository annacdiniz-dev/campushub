"""Manda os lembretes de entrega do dia.

O PythonAnywhere roda este arquivo sozinho, uma vez por dia (aba "Tasks"):
    cd /home/mycampushub/campushub && /home/mycampushub/.virtualenvs/campushub/bin/python enviar_lembretes.py

Também dá para rodar na mão, para testar:
    python enviar_lembretes.py
"""
from app import app
from datas import agora_brasil
from lembretes import enviar_lembretes_do_dia

if __name__ == "__main__":
    # O script roda fora do site, então "entramos" no app para usar o banco e os templates
    with app.app_context():
        total = enviar_lembretes_do_dia(app.config["SECRET_KEY"])
    print(f"{agora_brasil():%d/%m/%Y %H:%M} · lembretes enviados: {total}")
