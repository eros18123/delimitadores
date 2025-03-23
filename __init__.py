# __init__.py

from aqt import mw
from aqt.qt import QAction
from .dialog import CustomDialog

def abrir_janela():
    dialogo = CustomDialog(parent=mw)
    dialogo.show()

# Add the action to the Tools menu in Anki
acao = QAction(" 🙂 Adicionar Cards com Delimitadores", mw)
acao.triggered.connect(abrir_janela)
mw.form.menuTools.addAction(acao)