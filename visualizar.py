# visualizar.py

import os
import re
import base64
from aqt import mw
from aqt.qt import *
from aqt.utils import showWarning, showInfo
from aqt.webview import QWebEngineView

class VisualizarCards(QDialog):
    def __init__(self, parent):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.parent = parent
        self.cards_preview_list = []
        self.cards_visible = True  # Estado inicial: lista de cards visível
        self.setup_ui()
        self.view_cards_dialog()

    def setup_ui(self):
        self.setWindowTitle("Visualizar Cards")
        self.resize(800, 400)
        
        # Layout principal
        main_layout = QVBoxLayout()
        
        # Botão Mostrar/Ocultar
        self.toggle_cards_button = QPushButton("Ocultar Cards", self)
        self.toggle_cards_button.clicked.connect(self.toggle_cards_visibility)
        main_layout.addWidget(self.toggle_cards_button)
        
        # Usar QSplitter para permitir arrastar lateralmente
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Lista de cards (Card 1, Card 2, etc.)
        self.card_list_widget = QListWidget()
        self.card_list_widget.currentItemChanged.connect(self.update_card_preview)
        self.card_list_widget.setMaximumWidth(200)  # Tamanho máximo inicial
        self.card_list_widget.setMinimumWidth(100)  # Tamanho mínimo para evitar colapso total
        self.splitter.addWidget(self.card_list_widget)
        
        # Área de pré-visualização (frente e verso)
        self.card_preview_webview = QWebEngineView()
        settings = self.card_preview_webview.settings()
        for attr in [QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, 
                     QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, 
                     QWebEngineSettings.WebAttribute.AllowRunningInsecureContent]:
            settings.setAttribute(attr, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        self.card_preview_webview.setMinimumWidth(300)  # Tamanho mínimo para a pré-visualização
        self.splitter.addWidget(self.card_preview_webview)
        
        # Definir tamanhos iniciais para o splitter (lista: 200px, pré-visualização: resto)
        self.splitter.setSizes([200, 600])
        
        # Adicionar o splitter ao layout principal
        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)

    def generate_card_previews(self):
        linhas = self.parent.txt_entrada.toPlainText().strip().split('\n')
        if not linhas:
            return []
        delimitadores = [chk.simbolo for chk in self.parent.chk_delimitadores.values() if chk.isChecked()]
        if not delimitadores or not self.parent.lista_decks.currentItem() or not self.parent.lista_notetypes.currentItem():
            return []
        modelo = mw.col.models.by_name(self.parent.lista_notetypes.currentItem().text())
        campos = [fld['name'] for fld in modelo['flds']]
        num_fields = len(campos)
        
        # Preparação de tags: sempre usar as tags linha por linha
        tags_lines = self.parent.txt_tags.toPlainText().strip().splitlines()
        
        cards_preview_list = []
        card_index = 0  # Para numeração de cards
        media_dir = mw.col.media.dir()

        def get_mime_type(file_name):
            ext = os.path.splitext(file_name)[1].lower()
            return {
                '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
                '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.mp4': 'video/mp4',
                '.webm': 'video/webm'
            }.get(ext, 'application/octet-stream')

        def replace_media_src(match, media_type="img"):
            file_name = match.group(1)
            full_path = os.path.join(media_dir, file_name)
            if not os.path.exists(full_path):
                print(f"Arquivo não encontrado: {full_path}")
                return match.group(0)
            try:
                with open(full_path, 'rb') as f:
                    base64_data = base64.b64encode(f.read()).decode('utf-8')
                mime_type = get_mime_type(file_name)
                return f'<{media_type} src="data:{mime_type};base64,{base64_data}"' + (" controls width=\"320\" height=\"240\"" if media_type == "video" else "")
            except Exception as e:
                print(f"Erro ao codificar {media_type} em base64: {str(e)}")
                return match.group(0)
        
        for i, linha in enumerate(linhas):
            if not linha.strip():
                continue
                
            # Usar a linha específica de tags para este card
            tags_for_card = []
            if i < len(tags_lines):
                tags_for_card = [tag.strip() for tag in tags_lines[i].split(',') if tag.strip()]
            
            # Remover números das tags se necessário
            tags_for_card = [tag.strip().rstrip('0123456789') for tag in tags_for_card if tag.strip()]
            
            for delim in delimitadores:
                if delim in linha:
                    partes = linha.split(delim)
                    card_html = """
                    <html><body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 10px;">
                    <table style="width: 100%; border-collapse: separate; border-spacing: 0; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; margin-bottom: 20px;">
                    """
                    for j, campo in enumerate(partes[:num_fields]):  # Limita ao número de campos do tipo de nota
                        campo_formatado = campo.strip().replace('\n', '<br>')
                        for tag, type_ in [('<img', 'img'), ('<source', 'source'), ('<video', 'video')]:
                            if tag in campo_formatado:
                                campo_formatado = re.sub(rf'{tag} src="([^"]+)"', lambda m: replace_media_src(m, type_), campo_formatado)
                        card_html += f"""
                        <tr><td style="background-color: #444; color: white; padding: 12px; text-align: center; font-weight: bold; font-size: 16px; border-top-left-radius: 8px; border-top-right-radius: 8px;">{campos[j]}</td></tr>
                        <tr><td style="padding: 15px; border: 1px solid #ddd; background-color: white; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">{campo_formatado}</td></tr>
                        """
                    card_html += "</table>"
                    
                    # Adicionar as tags ao HTML
                    if tags_for_card:
                        if self.parent.chk_num_tags.isChecked():
                            # Adicionar número ao final de cada tag baseado no índice do card
                            tags_str = ', '.join(f"{tag}{card_index + 1}" for tag in tags_for_card)
                        else:
                            # Usar tags sem numeração
                            tags_str = ', '.join(tags_for_card)
                        
                        card_html += f"<p><b>Tags:</b> {tags_str}</p>"
                    
                    card_html += "</body></html>"
                    cards_preview_list.append(card_html)
                    card_index += 1
                    break
                    
        return cards_preview_list

    def view_cards_dialog(self):
        linhas = self.parent.txt_entrada.toPlainText().strip().split('\n')
        delimitadores = [chk.simbolo for chk in self.parent.chk_delimitadores.values() if chk.isChecked()]
        if not linhas or not delimitadores or not self.parent.lista_decks.currentItem() or not self.parent.lista_notetypes.currentItem():
            showWarning("Digite conteúdo, selecione um delimitador, deck e modelo para visualizar!")
            return
        self.cards_preview_list = self.generate_card_previews()
        if not self.cards_preview_list:
            showWarning("Nenhum card válido para visualizar!")
            return
        self.card_list_widget.addItems([f"Card {i+1}" for i in range(len(self.cards_preview_list))])
        if self.cards_preview_list:
            self.card_list_widget.setCurrentRow(0)

    def update_card_preview(self, current, previous):
        if current:  # Atualiza a pré-visualização apenas se houver um item selecionado
            index = self.card_list_widget.row(current)
            if index < len(self.cards_preview_list):
                self.card_preview_webview.setHtml(self.cards_preview_list[index])
                self.card_preview_webview.page().runJavaScript("""
                    document.body.style.transition = 'background-color 0.5s';
                    document.body.style.backgroundColor = '#fff9e6';
                    setTimeout(() => document.body.style.backgroundColor = '#f9f9f9', 500);
                """)
        else:
            self.card_preview_webview.setHtml("")  # Limpa a pré-visualização se não houver seleção

    def toggle_cards_visibility(self):
        self.cards_visible = not self.cards_visible
        self.toggle_cards_button.setText("Mostrar Cards" if not self.cards_visible else "Ocultar Cards")
        self.card_list_widget.setVisible(self.cards_visible)
        # Não limpa a pré-visualização, apenas oculta/mostra a lista lateral

    def update_preview(self):
        # Atualiza a lista de cards e a pré-visualização quando há qualquer alteração
        self.cards_preview_list = self.generate_card_previews()
        current_row = self.card_list_widget.currentRow()
        self.card_list_widget.clear()
        if self.cards_preview_list:
            self.card_list_widget.addItems([f"Card {i+1}" for i in range(len(self.cards_preview_list))])
            # Tenta manter o mesmo card selecionado, se possível
            if current_row >= 0 and current_row < len(self.cards_preview_list):
                self.card_list_widget.setCurrentRow(current_row)
            else:
                self.card_list_widget.setCurrentRow(0)  # Seleciona o primeiro card se a posição anterior não for válida
        else:
            self.card_preview_webview.setHtml("")  # Limpa a pré-visualização se não houver cards