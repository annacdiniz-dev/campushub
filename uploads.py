"""Guardar e apagar no disco os arquivos anexados às atividades.

Ficam em instance/uploads/atividades/<id da atividade>/ — FORA da pasta static.
Assim ninguém baixa um arquivo só adivinhando o endereço: o download passa
por uma rota que confere se o arquivo é mesmo de quem está pedindo.
"""
import os
import shutil

from flask import current_app

# Tipos de arquivo aceitos (documentos, planilhas, apresentações, imagens, código, zip)
EXTENSOES_PERMITIDAS = {
    "pdf", "doc", "docx", "odt", "txt", "md", "rtf",
    "ppt", "pptx", "odp", "xls", "xlsx", "ods", "csv",
    "png", "jpg", "jpeg", "webp", "gif",
    "zip", "py", "java", "c", "cpp", "ipynb",
}
# Esses o navegador consegue mostrar direto (o resto é baixado)
ABRE_NO_NAVEGADOR = {"pdf", "png", "jpg", "jpeg", "webp", "gif", "txt"}


def pasta_da_atividade(atividade_id):
    pasta = os.path.join(current_app.instance_path, "uploads", "atividades", str(atividade_id))
    os.makedirs(pasta, exist_ok=True)
    return pasta


def apagar_arquivos_da_atividade(atividade_id):
    """Apaga do disco a pasta inteira da atividade (usado ao excluir atividade ou matéria)."""
    pasta = os.path.join(current_app.instance_path, "uploads", "atividades", str(atividade_id))
    shutil.rmtree(pasta, ignore_errors=True)
