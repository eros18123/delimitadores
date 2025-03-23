# dialog.py

import json
import os
import shutil
import re
import urllib.parse
import base64
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, showWarning
from aqt.webview import QWebEngineView
from anki.utils import strip_html
from .highlighter import HtmlTagHighlighter
from .media_manager import MediaManagerDialog
from .visualizar import VisualizarCards
from .utils import CONFIG_FILE

class CustomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.visualizar_dialog = None
        self.last_search_query = ""
        self.last_search_position = 0
        self.zoom_factor = 1.0
        self.cloze_2_count = 1
        self.initial_tags_set = False
        self.initial_numbering_set = False
        self.media_files = []  # Lista para armazenar arquivos de mídia adicionados
        self.current_line = 0  # Para rastrear a linha atual
        self.previous_text = ""  # Para rastrear o texto anterior e detectar mudanças nos nomes de mídia
        self.last_edited_line = -1  # Para rastrear a última linha editada
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        self.setWindowTitle("Adicionar Cards com Delimitadores")
        self.resize(1000, 600)
        main_layout = QVBoxLayout()
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top Widget
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Botão para adicionar mídia
        media_layout = QHBoxLayout()
        image_button = QPushButton("Adicionar Imagem, Som ou Vídeo (webm)", self)
        image_button.clicked.connect(self.add_image)
        media_layout.addWidget(image_button)
        
        # Botão para gerenciar mídia
        manage_media_button = QPushButton("Gerenciar Mídia", self)
        manage_media_button.clicked.connect(self.manage_media)
        media_layout.addWidget(manage_media_button)

        # Botão para visualizar cards
        view_cards_button = QPushButton("Visualizar Cards", self)
        view_cards_button.clicked.connect(self.view_cards_dialog)
        media_layout.addWidget(view_cards_button)

        top_layout.addLayout(media_layout)
        
        # Fields Splitter (campo de texto à esquerda, pré-visualização à direita)
        self.fields_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Widget para "Digite seus cards" e "Etiquetas"
        self.cards_tags_widget = QWidget()
        cards_tags_layout = QHBoxLayout(self.cards_tags_widget)
        
        # Cards Group (Digite seus cards)
        self.cards_group = QWidget()
        cards_layout = QVBoxLayout(self.cards_group)
        cards_header_layout = QHBoxLayout()
        cards_label = QLabel("Digite seus cards:")
        cards_header_layout.addWidget(cards_label)
        
        # Botões de Cor do Texto
        for color in ["red", "blue", "green", "yellow"]:
            btn = QPushButton("A")
            btn.setStyleSheet(f"color: {color}; background-color: black;")
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, c=color: self.apply_text_color(c))
            btn.setToolTip("Aplicar cor ao texto")
            cards_header_layout.addWidget(btn)
        
        # Botões de Cor de Fundo
        for color in ["red", "blue", "green", "yellow"]:
            btn = QPushButton("Af")
            btn.setStyleSheet(f"background-color: {color}; color: black;")
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, c=color: self.apply_background_color(c))
            btn.setToolTip("Aplicar cor de fundo ao texto")
            cards_header_layout.addWidget(btn)
        
        cards_header_layout.addStretch()
        cards_layout.addLayout(cards_header_layout)
        
        self.txt_entrada = QTextEdit()
        self.txt_entrada.setPlaceholderText("Digite seus cards aqui...")
        self.highlighter = HtmlTagHighlighter(self.txt_entrada.document())
        self.txt_entrada.textChanged.connect(self.update_tags_lines)  # Sincronizar linhas com o campo de etiquetas
        self.txt_entrada.cursorPositionChanged.connect(self.check_line_change)  # Verificar mudança de linha
        self.txt_entrada.focusOutEvent = self.focus_out_event  # Detectar perda de foco
        cards_layout.addWidget(self.txt_entrada)
        
        cards_tags_layout.addWidget(self.cards_group, stretch=2)
        
        # Etiquetas Group (ao lado de Digite seus cards)
        self.etiquetas_group = QWidget()
        etiquetas_layout = QVBoxLayout(self.etiquetas_group)
        etiquetas_header_layout = QHBoxLayout()
        self.tags_label = QLabel("Etiquetas:")
        etiquetas_header_layout.addWidget(self.tags_label)
        etiquetas_header_layout.addStretch()
        etiquetas_layout.addLayout(etiquetas_header_layout)
        self.txt_tags = QTextEdit()
        self.txt_tags.setPlaceholderText("Digite as etiquetas aqui (uma linha por card)...")
        self.txt_tags.setMaximumWidth(200)
        self.txt_tags.textChanged.connect(self.update_preview)  # Atualizar pré-visualização ao mudar tags
        etiquetas_layout.addWidget(self.txt_tags)
        self.etiquetas_group.setVisible(False)  # Escondido por padrão
        cards_tags_layout.addWidget(self.etiquetas_group, stretch=1)
        
        self.fields_splitter.addWidget(self.cards_tags_widget)
        
        # Pré-visualização embutida à direita
        self.preview_widget = QWebEngineView()
        settings = self.preview_widget.settings()
        for attr in [QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, 
                     QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, 
                     QWebEngineSettings.WebAttribute.AllowRunningInsecureContent]:
            settings.setAttribute(attr, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        self.preview_widget.setMinimumWidth(300)
        self.fields_splitter.addWidget(self.preview_widget)
        
        self.fields_splitter.setSizes([700, 300])
        top_layout.addWidget(self.fields_splitter)
        
        # Opções (Numerar Tags, Repetir Tags, Mostrar/Ocultar Etiquetas)
        options_layout = QHBoxLayout()
        options_layout.addStretch()
        self.chk_num_tags = QCheckBox("Numerar Tags")
        self.chk_repetir_tags = QCheckBox("Repetir Tags")
        self.chk_num_tags.stateChanged.connect(self.update_tag_numbers)
        self.chk_repetir_tags.stateChanged.connect(self.update_repeated_tags)
        options_layout.addWidget(self.chk_num_tags)
        options_layout.addWidget(self.chk_repetir_tags)
        
        # Botão para mostrar/ocultar etiquetas
        self.toggle_tags_button = QPushButton("Mostrar Etiquetas", self)
        self.toggle_tags_button.clicked.connect(self.toggle_tags)
        options_layout.addWidget(self.toggle_tags_button)
        
        top_layout.addLayout(options_layout)
        self.vertical_splitter.addWidget(top_widget)
        
        # Bottom Widget
        bottom_scroll = QScrollArea()
        bottom_scroll.setWidgetResizable(True)
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        # Botões de Formatação
        btn_layout = QHBoxLayout()
        botoes_formatacao = [
            ("Juntar Linhas", self.join_lines, "Juntar todas as linhas (sem atalho)"), 
            ("Destaque", self.destaque_texto, "Destacar texto (Ctrl+M)"), 
            ("B", self.apply_bold, "Negrito (Ctrl+B)"), 
            ("I", self.apply_italic, "Itálico (Ctrl+I)"), 
            ("U", self.apply_underline, "Sublinhado (Ctrl+U)"), 
            ("Concatenar", self.concatenate_text, "Concatenar texto (sem atalho)")
        ]
        for texto, funcao, tooltip in botoes_formatacao:
            btn = QPushButton(texto)
            btn.clicked.connect(funcao)
            btn.setToolTip(tooltip)  # Adicionar dica de atalho
            if texto == "Destaque":
                btn.setStyleSheet("background-color: yellow; color: black;")
            btn_layout.addWidget(btn)
        bottom_layout.addLayout(btn_layout)
        
        # Search Layout
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Pesquisar... Ctrl+P")
        search_layout.addWidget(self.search_input)
        search_button = QPushButton("Pesquisar", self)
        search_button.clicked.connect(self.search_text)
        search_layout.addWidget(search_button)
        self.replace_input = QLineEdit(self)
        self.replace_input.setPlaceholderText("Substituir tudo por... Ctrl+S")
        search_layout.addWidget(self.replace_input)
        replace_button = QPushButton("Substituir Tudo", self)
        replace_button.clicked.connect(self.replace_text)
        search_layout.addWidget(replace_button)
        zoom_in_button = QPushButton("+", self)
        zoom_in_button.clicked.connect(self.zoom_in)
        search_layout.addWidget(zoom_in_button)
        zoom_out_button = QPushButton("-", self)
        zoom_out_button.clicked.connect(self.zoom_out)
        search_layout.addWidget(zoom_out_button)
        bottom_layout.addLayout(search_layout)
        
        # Cloze Layout
        cloze_layout = QGridLayout()
        for text, func, col, tooltip in [
            ("Cloze 1 (Ctrl+D)", self.add_cloze_1, 0, "Adicionar Cloze 1 (Ctrl+D)"),
            ("Cloze 2 (Ctrl+F)", self.add_cloze_2, 1, "Adicionar Cloze 2 (Ctrl+F)"),
            ("Remover Cloze", self.remove_cloze, 2, "Remover Cloze (sem atalho)")
        ]:
            btn = QPushButton(text, self)
            btn.clicked.connect(func)
            btn.setToolTip(tooltip)
            cloze_layout.addWidget(btn, 0, col)
        bottom_layout.addLayout(cloze_layout)
        
        # Group Widget (Decks, Modelos, Delimitadores) - Com QSplitter vertical
        self.group_widget = QWidget()
        group_layout = QVBoxLayout(self.group_widget)
        
        # QSplitter vertical para "Decks/Modelos" e "Delimitadores"
        self.group_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Widget para "Decks" e "Modelos" - Agora com QSplitter horizontal
        decks_modelos_widget = QWidget()
        decks_modelos_layout = QVBoxLayout(decks_modelos_widget)
        
        # QSplitter horizontal para "Decks" e "Modelos"
        self.decks_modelos_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Widget para "Decks"
        decks_group = QGroupBox("Decks")
        decks_layout = QVBoxLayout(decks_group)
        self.scroll_decks, self.lista_decks = self.criar_lista_rolavel([d.name for d in mw.col.decks.all_names_and_ids()], 100)
        decks_layout.addWidget(self.scroll_decks)
        self.decks_search_input = QLineEdit(self)
        self.decks_search_input.setPlaceholderText("Pesquisar decks...")
        self.decks_search_input.textChanged.connect(self.filter_decks)
        decks_layout.addWidget(self.decks_search_input)

        # Adicionando campo e botão para criar deck
        self.deck_name_input = QLineEdit(self)
        self.deck_name_input.setPlaceholderText("Digite o nome do novo deck...")
        decks_layout.addWidget(self.deck_name_input)
        create_deck_button = QPushButton("Criar Deck", self)
        create_deck_button.clicked.connect(self.create_deck)
        decks_layout.addWidget(create_deck_button)
        
        self.decks_modelos_splitter.addWidget(decks_group)
        
        # Widget para "Modelos"
        modelos_group = QGroupBox("Modelos ou Tipos de Notas")
        modelos_layout = QVBoxLayout(modelos_group)
        self.scroll_notetypes, self.lista_notetypes = self.criar_lista_rolavel(mw.col.models.all_names(), 100)
        self.lista_notetypes.currentItemChanged.connect(self.update_preview)  # Atualizar pré-visualização ao mudar tipo de nota
        modelos_layout.addWidget(self.scroll_notetypes)
        self.notetypes_search_input = QLineEdit(self)
        self.notetypes_search_input.setPlaceholderText("Pesquisar tipos de notas...")
        self.notetypes_search_input.textChanged.connect(self.filter_notetypes)
        modelos_layout.addWidget(self.notetypes_search_input)
        
        self.decks_modelos_splitter.addWidget(modelos_group)
        
        # Definir tamanhos iniciais para o splitter horizontal (Decks: 200px, Modelos: 150px)
        self.decks_modelos_splitter.setSizes([200, 150])
        
        # Adicionar o splitter horizontal ao layout do decks_modelos_widget
        decks_modelos_layout.addWidget(self.decks_modelos_splitter)
        
        # Adicionar o widget de "Decks/Modelos" ao splitter vertical
        self.group_splitter.addWidget(decks_modelos_widget)
        
        # Widget para "Delimitadores"
        delimitadores_widget = QWidget()
        delimitadores_layout = QVBoxLayout(delimitadores_widget)
        self.delimitadores_label = QLabel("Delimitadores:")
        delimitadores_layout.addWidget(self.delimitadores_label)
        delimitadores = [("Tab", "\t"), ("Vírgula", ","), ("Ponto e Vírgula", ";"), ("Dois Pontos", ":"), 
                         ("Interrogação", "?"), ("Barra", "/"), ("Exclamação", "!"), ("Pipe", "|")]
        grid = QGridLayout()
        self.chk_delimitadores = {}
        for i, (nome, simbolo) in enumerate(delimitadores):
            chk = QCheckBox(nome)
            chk.simbolo = simbolo
            chk.stateChanged.connect(self.update_preview)  # Atualizar pré-visualização ao mudar delimitadores
            grid.addWidget(chk, i // 4, i % 4)
            self.chk_delimitadores[nome] = chk
        delimitadores_layout.addLayout(grid)
        
        # Adicionar o widget de "Delimitadores" ao splitter vertical
        self.group_splitter.addWidget(delimitadores_widget)
        
        # Definir tamanhos iniciais para o splitter vertical (Decks/Modelos: 150px, Delimitadores: 100px)
        self.group_splitter.setSizes([150, 100])
        
        # Adicionar o splitter vertical ao layout do group_widget
        group_layout.addWidget(self.group_splitter)
        
        bottom_layout.addWidget(self.group_widget)
        
        # Bottom Buttons
        bottom_buttons_layout = QHBoxLayout()
        self.btn_toggle = QPushButton("Ocultar Decks/Modelos/Delimitadores")
        self.btn_toggle.clicked.connect(self.toggle_group)
        bottom_buttons_layout.addWidget(self.btn_toggle)
        btn_add = QPushButton("Adicionar Cards (Ctrl+R)")
        btn_add.clicked.connect(self.add_cards)
        btn_add.setToolTip("Adicionar Cards (Ctrl+R)")
        bottom_buttons_layout.addWidget(btn_add)
        bottom_layout.addLayout(bottom_buttons_layout)
        bottom_layout.addStretch()
        
        bottom_scroll.setWidget(bottom_widget)
        self.vertical_splitter.addWidget(bottom_scroll)
        self.vertical_splitter.setSizes([300, 300])
        self.vertical_splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.vertical_splitter)
        self.setLayout(main_layout)
        
        # Atalhos
        for key, func in [
            ("Ctrl+B", self.apply_bold), 
            ("Ctrl+I", self.apply_italic), 
            ("Ctrl+U", self.apply_underline), 
            ("Ctrl+M", self.destaque_texto), 
            ("Ctrl+P", self.search_text), 
            ("Ctrl+S", self.replace_text), 
            ("Ctrl+=", self.zoom_in), 
            ("Ctrl+-", self.zoom_out), 
            ("Ctrl+D", self.add_cloze_1), 
            ("Ctrl+F", self.add_cloze_2), 
            ("Ctrl+R", self.add_cards),
        ]:
            QShortcut(QKeySequence(key), self).activated.connect(func)
        
        self.txt_entrada.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.txt_entrada.customContextMenuRequested.connect(self.show_context_menu)
        self.txt_entrada.installEventFilter(self)
        self.txt_entrada.setAcceptDrops(True)
        self.txt_entrada.dragEnterEvent = self.drag_enter_event
        self.txt_entrada.dropEvent = self.drop_event
        self.txt_entrada.focusInEvent = self.create_focus_handler(self.txt_entrada, "cards")
        self.txt_tags.focusInEvent = self.create_focus_handler(self.txt_tags, "tags")

    def toggle_tags(self):
        novo_estado = not self.etiquetas_group.isVisible()
        self.etiquetas_group.setVisible(novo_estado)
        self.toggle_tags_button.setText("Ocultar Etiquetas" if novo_estado else "Mostrar Etiquetas")

    def update_tags_lines(self):
        # Sincronizar o número de linhas no campo de etiquetas com o número de linhas no campo de cards
        linhas_cards = self.txt_entrada.toPlainText().strip().split('\n')
        linhas_tags = self.txt_tags.toPlainText().strip().split('\n')
        
        # Garantir que o número de linhas no campo de etiquetas seja o mesmo que no campo de cards
        if len(linhas_tags) < len(linhas_cards):
            self.txt_tags.setPlainText(self.txt_tags.toPlainText() + '\n' * (len(linhas_cards) - len(linhas_tags)))
        elif len(linhas_tags) > len(linhas_cards):
            self.txt_tags.setPlainText('\n'.join(linhas_tags[:len(linhas_cards)]))
        
        self.update_preview()

    def check_line_change(self):
        # Verificar se a linha atual mudou
        cursor = self.txt_entrada.textCursor()
        current_line = cursor.blockNumber()
        if current_line != self.current_line:
            self.process_media_rename()
            self.current_line = current_line
            self.last_edited_line = current_line
        self.update_preview()

    def focus_out_event(self, event):
        # Processar renomeação ao perder o foco
        self.process_media_rename()
        QTextEdit.focusOutEvent(self.txt_entrada, event)

    def process_media_rename(self):
        # Detectar mudanças nos nomes de arquivos de mídia e renomear na pasta de mídia
        current_text = self.txt_entrada.toPlainText()
        if self.previous_text != current_text:
            # Padrões para encontrar nomes de arquivos de mídia
            patterns = [
                r'<img src="([^"]+)"',
                r'<source src="([^"]+)"',
                r'<video src="([^"]+)"'
            ]
            
            # Obter nomes de arquivos de mídia no texto anterior e atual
            previous_media = set()
            current_media = set()
            for pattern in patterns:
                previous_media.update(re.findall(pattern, self.previous_text))
                current_media.update(re.findall(pattern, current_text))
            
            # Comparar e renomear arquivos
            media_dir = mw.col.media.dir()
            for old_name in previous_media:
                if old_name in self.media_files and old_name not in current_media:
                    # Procurar o novo nome correspondente
                    for new_name in current_media:
                        if new_name not in previous_media and new_name not in self.media_files:
                            # Verificar se o novo nome já existe
                            if os.path.exists(os.path.join(media_dir, new_name)):
                                showWarning(f"O nome '{new_name}' já existe na pasta de mídia!")
                                continue
                            
                            # Renomear o arquivo na pasta de mídia
                            try:
                                os.rename(
                                    os.path.join(media_dir, old_name),
                                    os.path.join(media_dir, new_name)
                                )
                                # Atualizar a lista de mídia
                                self.media_files[self.media_files.index(old_name)] = new_name
                                showInfo(f"Arquivo renomeado de '{old_name}' para '{new_name}' na pasta de mídia.")
                            except Exception as e:
                                showWarning(f"Erro ao renomear o arquivo: {str(e)}")
                            break
            
            self.previous_text = current_text

    def update_preview(self):
        # Determinar a linha atual com base na posição do cursor
        cursor = self.txt_entrada.textCursor()
        self.current_line = cursor.blockNumber()
        
        linhas = self.txt_entrada.toPlainText().strip().split('\n')
        if not linhas or self.current_line >= len(linhas):
            self.preview_widget.setHtml("")
            return
        
        # Mostrar apenas a linha atual
        linha = linhas[self.current_line]
        if not linha.strip():
            self.preview_widget.setHtml("")
            return
        
        delimitadores = [chk.simbolo for chk in self.chk_delimitadores.values() if chk.isChecked()]
        if not delimitadores or not self.lista_decks.currentItem() or not self.lista_notetypes.currentItem():
            self.preview_widget.setHtml("")
            return
        
        modelo = mw.col.models.by_name(self.lista_notetypes.currentItem().text())
        campos = [fld['name'] for fld in modelo['flds']]
        num_fields = len(campos)
        
        # Preparação de tags (uma linha por card)
        linhas_tags = self.txt_tags.toPlainText().strip().split('\n')
        tags_for_current_card = []
        if self.current_line < len(linhas_tags):
            tags_for_current_card = [tag.strip() for tag in linhas_tags[self.current_line].split(',') if tag.strip()]
        
        card_index = self.current_line
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

        cards_html = """
        <html><body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 10px;">
        <style>
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 5px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
                vertical-align: top;
                width: 33%;  /* Distribuir igualmente as colunas */
                box-sizing: border-box;
            }
            th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            ul, ol {
                margin: 5px 0;
                padding-left: 20px;
            }
        </style>
        """
        for delim in delimitadores:
            if delim in linha:
                partes = linha.split(delim)
                card_html = """
                <table style="width: 100%; border-collapse: separate; border-spacing: 0; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; margin-bottom: 20px;">
                """
                for j, campo in enumerate(partes[:num_fields]):
                    campo_formatado = campo.strip()
                    for tag, type_ in [('<img', 'img'), ('<source', 'source'), ('<video', 'video')]:
                        if tag in campo_formatado:
                            campo_formatado = re.sub(rf'{tag} src="([^"]+)"', lambda m: replace_media_src(m, type_), campo_formatado)
                    card_html += f"""
                    <tr><td style="background-color: #444; color: white; padding: 12px; text-align: center; font-weight: bold; font-size: 16px; border-top-left-radius: 8px; border-top-right-radius: 8px;">{campos[j]}</td></tr>
                    <tr><td style="padding: 15px; border: 1px solid #ddd; background-color: white; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">{campo_formatado}</td></tr>
                    """
                card_html += "</table>"
                
                if tags_for_current_card:
                    if self.chk_num_tags.isChecked():
                        tags_str = ', '.join(f"{tag}{card_index + 1}" for tag in tags_for_current_card)
                    else:
                        tags_str = ', '.join(tags_for_current_card)
                    card_html += f"<p><b>Tags:</b> {tags_str}</p>"
                
                cards_html += card_html
                break
        
        cards_html += "</body></html>"
        self.preview_widget.setHtml(cards_html)

    def apply_text_color(self, color):
        cursor = self.txt_entrada.textCursor()
        if cursor.hasSelection():
            texto = cursor.selectedText()
            cursor.insertText(f'<span style="color:{color}">{texto}</span>')
        else:
            cursor.insertText(f'<span style="color:{color}"></span>')
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 7)
            self.txt_entrada.setTextCursor(cursor)
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def apply_background_color(self, color):
        cursor = self.txt_entrada.textCursor()
        if cursor.hasSelection():
            texto = cursor.selectedText()
            cursor.insertText(f'<span style="background-color:{color}">{texto}</span>')
        else:
            cursor.insertText(f'<span style="background-color:{color}"></span>')
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 7)
            self.txt_entrada.setTextCursor(cursor)
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def add_cards(self):
        deck = self.lista_decks.currentItem()
        notetype = self.lista_notetypes.currentItem()
        if not deck or not notetype:
            showWarning("Selecione um deck e um modelo!")
            return
        delimitadores = [chk.simbolo for chk in self.chk_delimitadores.values() if chk.isChecked()]
        if not delimitadores:
            showWarning("Selecione pelo menos um delimitador!")
            return
        linhas = self.txt_entrada.toPlainText().strip().split('\n')
        if not linhas:
            showWarning("Digite algum conteúdo!")
            return
        modelo = mw.col.models.by_name(notetype.text())
        num_fields = len(modelo['flds'])
        contador = 0
        
        # Tags (uma linha por card)
        linhas_tags = self.txt_tags.toPlainText().strip().split('\n')
        
        card_index = 0
        
        for i, linha in enumerate(linhas):
            if not linha.strip():
                continue
                
            for delim in delimitadores:
                if delim in linha:
                    partes = linha.split(delim)
                    nota = mw.col.new_note(modelo)
                    for j in range(min(len(partes), num_fields)):
                        nota.fields[j] = partes[j].strip()
                    
                    # Aplicar tags específicas para este card
                    tags_for_card = []
                    if i < len(linhas_tags):
                        tags_for_card = [tag.strip() for tag in linhas_tags[i].split(',') if tag.strip()]
                    if tags_for_card:
                        if self.chk_num_tags.isChecked():
                            nota.tags.extend([f"{tag}{card_index + 1}" for tag in tags_for_card])
                        else:
                            nota.tags.extend(tags_for_card)
                    
                    try:
                        mw.col.add_note(nota, mw.col.decks.by_name(deck.text())['id'])
                        contador += 1
                        card_index += 1
                    except Exception as e:
                        print(f"Erro ao adicionar card: {str(e)}")
                    break
        
        showInfo(f"{contador} cards adicionados com sucesso!")

    def add_image(self):
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos", "", "Mídia (*.png *.jpg *.jpeg *.gif *.mp3 *.wav *.ogg *.mp4 *.webm)")
        if arquivos:
            media_dir = mw.col.media.dir()
            for caminho in arquivos:
                nome = os.path.basename(caminho)
                destino = os.path.join(media_dir, nome)
                if not os.path.exists(destino):
                    shutil.copy(caminho, destino)
                self.media_files.append(nome)  # Adicionar à lista de arquivos de mídia
                ext = os.path.splitext(nome)[1].lower()
                if ext in ('.png', '.jpg', '.jpeg', '.gif'):
                    self.txt_entrada.insertPlainText(f'<img src="{nome}">\n')
                elif ext in ('.mp3', '.wav', '.ogg'):
                    self.txt_entrada.insertPlainText(f'<audio controls=""><source src="{nome}" type="audio/mpeg"></audio>\n')
                elif ext in ('.mp4', '.webm'):
                    self.txt_entrada.insertPlainText(f'<video src="{nome}" controls width="320" height="240"></video>\n')
            self.previous_text = self.txt_entrada.toPlainText()
            self.update_preview()

    def drag_enter_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            file_paths = [url.toLocalFile() for url in mime_data.urls()]
            self.process_files(file_paths)
            event.acceptProposedAction()
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def process_files(self, file_paths):
        media_folder = mw.col.media.dir()
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            new_path = os.path.join(media_folder, file_name)
            if os.path.exists(new_path):
                base_name, ext = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(new_path):
                    file_name = f"{base_name}{counter}{ext}"
                    new_path = os.path.join(media_folder, file_name)
                    counter += 1
            shutil.copy(file_path, new_path)
            self.media_files.append(file_name)  # Adicionar à lista de arquivos de mídia
            ext = file_name.lower()
            if ext.endswith(('.png', '.xpm', '.jpg', '.jpeg', '.bmp', '.gif')):
                self.txt_entrada.insertPlainText(f'<img src="{file_name}">\n')
            elif ext.endswith(('.mp3', '.wav', '.ogg')):
                self.txt_entrada.insertPlainText(f'<audio controls=""><source src="{file_name}" type="audio/mpeg"></audio>\n')
            elif ext.endswith(('.mp4', '.webm', '.avi', '.mkv', '.mov')):
                self.txt_entrada.insertPlainText(f'<video src="{file_name}" controls width="320" height="240"></video>\n')

    def show_context_menu(self, pos):
        menu = self.txt_entrada.createStandardContextMenu()
        paste_action = QAction("Colar HTML sem Tag e sem Formatação", self)
        paste_action.triggered.connect(self.paste_html)
        menu.addAction(paste_action)
        paste_raw_action = QAction("Colar com Tags HTML", self)
        paste_raw_action.triggered.connect(self.paste_raw_html)
        menu.addAction(paste_raw_action)
        paste_excel_action = QAction("Colar do Excel com Ponto e Vírgula", self)
        paste_excel_action.triggered.connect(self.paste_excel)
        menu.addAction(paste_excel_action)
        menu.exec(self.txt_entrada.mapToGlobal(pos))


    def convert_markdown_to_html(self, text):
        # Detectar tabelas Markdown e convertê-las para HTML
        lines = text.split('\n')
        table_html = ""
        in_table = False
        headers = []
        rows = []
        table_start_idx = -1
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Detectar uma linha de tabela Markdown (ex.: | Coluna 1 | Coluna 2 |)
            if line.startswith('|') and line.endswith('|') and '|' in line[1:-1]:
                cells = [cell.strip() for cell in line[1:-1].split('|')]
                # Verificar se a próxima linha é uma linha de separação (ex.: | --- | --- |)
                if not in_table and i + 1 < len(lines) and re.match(r'^\|(?:\s*[-:]+(?:\s*\|)?)+$', lines[i + 1]):
                    in_table = True
                    table_start_idx = i
                    headers = cells
                    continue
                elif in_table:
                    rows.append(cells)
            elif in_table:
                # Fim da tabela, converter para HTML
                if headers and rows:
                    table_html += "<table>\n<thead>\n<tr>"
                    for header in headers:
                        table_html += f"<th>{header}</th>"
                    table_html += "</tr>\n</thead>\n<tbody>\n"
                    for row in rows:
                        while len(row) < len(headers):
                            row.append("")
                        table_html += "<tr>"
                        for cell in row[:len(headers)]:
                            table_html += f"<td>{cell}</td>"
                        table_html += "</tr>\n"
                    table_html += "</tbody>\n</table>"
                in_table = False
                headers = []
                rows = []
        
        # Se ainda estamos em uma tabela no final do texto
        if in_table and headers and rows:
            table_html += "<table>\n<thead>\n<tr>"
            for header in headers:
                table_html += f"<th>{header}</th>"
            table_html += "</tr>\n</thead>\n<tbody>\n"
            for row in rows:
                while len(row) < len(headers):
                    row.append("")
                table_html += "<tr>"
                for cell in row[:len(headers)]:
                    table_html += f"<td>{cell}</td>"
                table_html += "</tr>\n"
            table_html += "</tbody>\n</table>"
        
        # Substituir a tabela Markdown pelo HTML gerado
        if table_html:
            # Remover as linhas da tabela Markdown original
            new_lines = []
            in_table = False
            for i, line in enumerate(lines):
                if i == table_start_idx:
                    in_table = True
                    continue
                elif in_table and (line.strip().startswith('|') and line.strip().endswith('|') and '|' in line.strip()[1:-1] or re.match(r'^\|(?:\s*[-:]+(?:\s*\|)?)+$', line)):
                    continue
                else:
                    in_table = False
                    if line.strip():  # Só adicionar linhas não vazias
                        new_lines.append(line.rstrip())
            
            # Juntar as linhas restantes e adicionar a tabela HTML
            remaining_text = '\n'.join(new_lines).rstrip()
            if remaining_text:
                text = remaining_text + '\n' + table_html.rstrip()
            else:
                text = table_html.rstrip()
        else:
            # Se não houver tabela, apenas remover linhas em branco extras
            text = '\n'.join(line.rstrip() for line in lines if line.strip()).rstrip()
        return text

    def paste_html(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasHtml():
            html = mime_data.html()
            # Remover todas as tags HTML para obter texto puro
            cleaned_text = strip_html(html)
            # Converter Markdown para HTML (ex.: tabelas)
            cleaned_text = self.convert_markdown_to_html(cleaned_text)
            self.txt_entrada.insertPlainText(cleaned_text)
        elif mime_data.hasImage():
            image = clipboard.image()
            if not image.isNull():
                media_folder = mw.col.media.dir()
                base_name, ext, counter = "img", ".png", 1
                file_name = f"{base_name}{counter}{ext}"
                new_path = os.path.join(media_folder, file_name)
                while os.path.exists(new_path):
                    counter += 1
                    file_name = f"{base_name}{counter}{ext}"
                    new_path = os.path.join(media_folder, file_name)
                image.save(new_path)
                self.media_files.append(file_name)
                self.txt_entrada.insertPlainText(f'<img src="{file_name}">\n')
        elif mime_data.hasText():
            text = clipboard.text()
            # Converter Markdown para HTML (ex.: tabelas)
            text = self.convert_markdown_to_html(text)
            self.txt_entrada.insertPlainText(text)
        else:
            showWarning("Nenhuma imagem, texto ou HTML encontrado na área de transferência.")
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()


    def paste_excel(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasText():
            text = clipboard.text()
            # Dividir o texto em linhas
            lines = text.strip().split('\n')
            formatted_lines = []
            for line in lines:
                # Dividir cada linha em colunas usando tabulação (\t) como delimitador
                columns = line.split('\t')
                # Remover espaços em branco e juntar as colunas com ponto e vírgula
                columns = [col.strip() for col in columns]
                formatted_line = ' ; '.join(columns)
                formatted_lines.append(formatted_line)
            # Juntar as linhas formatadas com quebras de linha
            formatted_text = '\n'.join(formatted_lines)
            self.txt_entrada.insertPlainText(formatted_text)
            self.previous_text = self.txt_entrada.toPlainText()
            self.update_preview()
        else:
            showWarning("Nenhum texto encontrado na área de transferência para colar como Excel.")



    def paste_raw_html(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasHtml():
            html = mime_data.html()
            # Lista de tags estruturais ou desnecessárias a serem removidas
            tags_to_remove = [
                'html', 'body', 'head', 'meta', 'link', 'script', 'style',
                'title', 'doctype', '!DOCTYPE', 'br', 'hr', 'div', 'p', 'form', 'input', 'button', 'a'
            ]
            # Remover tags desnecessárias, mas preservar tags de formatação inline, listas e tabelas
            pattern = r'</?(?:' + '|'.join(tags_to_remove) + r')(?:\s+[^>]*)?>'
            cleaned_html = re.sub(pattern, '', html, flags=re.IGNORECASE)
            # Converter Markdown para HTML (ex.: tabelas)
            cleaned_html = self.convert_markdown_to_html(cleaned_html)
            # Proteger o conteúdo dentro de listas e tabelas
            def protect_structures(match):
                return match.group(0).replace('\n', ' PROTECTED_NEWLINE ')
            cleaned_html = re.sub(r'<ul>.*?</ul>|<ol>.*?</ol>|<li>.*?</li>|<table>.*?</table>', protect_structures, cleaned_html, flags=re.DOTALL)
            # Não adicionar <br> automaticamente; confiar na formatação natural dos elementos
            lines = cleaned_html.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line:
                    cleaned_lines.append(line)
            cleaned_html = '\n'.join(cleaned_lines)
            # Restaurar quebras de linha dentro de listas e tabelas
            cleaned_html = cleaned_html.replace(' PROTECTED_NEWLINE ', '\n')
            # Remover espaços extras, mas preservar espaços dentro de tags
            cleaned_html = re.sub(r'\s+(?![^<]*>)', ' ', cleaned_html).strip()
            self.txt_entrada.insertPlainText(cleaned_html)
        elif mime_data.hasText():
            text = clipboard.text()
            # Converter Markdown para HTML (ex.: tabelas)
            text = self.convert_markdown_to_html(text)
            self.txt_entrada.insertPlainText(text)
        else:
            showWarning("Nenhum texto ou HTML encontrado na área de transferência.")
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def eventFilter(self, obj, event):
        if obj == self.txt_entrada and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                self.paste_html()
                return True
        return super().eventFilter(obj, event)

    def criar_lista_rolavel(self, itens, altura_min=100):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(altura_min)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lista = QListWidget()
        lista.addItems(itens)
        scroll.setWidget(lista)
        return scroll, lista

    def toggle_group(self):
        novo_estado = not self.group_widget.isVisible()
        self.group_widget.setVisible(novo_estado)
        self.btn_toggle.setText("Ocultar Decks/Modelos/Delimitadores" if novo_estado else "Mostrar Decks/Modelos/Delimitadores")

    def ajustar_tamanho_scroll(self):
        self.scroll_decks.widget().adjustSize()
        self.scroll_notetypes.widget().adjustSize()
        self.scroll_decks.updateGeometry()
        self.scroll_notetypes.updateGeometry()

    def scan_media_files_from_text(self):
        # Padrões para encontrar nomes de arquivos de mídia no texto
        patterns = [
            r'<img src="([^"]+)"',
            r'<source src="([^"]+)"',
            r'<video src="([^"]+)"'
        ]
        
        current_text = self.txt_entrada.toPlainText()
        media_dir = mw.col.media.dir()
        found_media = set()
    
        # Procurar por todos os arquivos de mídia mencionados no texto
        for pattern in patterns:
            matches = re.findall(pattern, current_text)
            for file_name in matches:
                # Verificar se o arquivo existe na pasta de mídia
                file_path = os.path.join(media_dir, file_name)
                if os.path.exists(file_path) and file_name not in self.media_files:
                    found_media.add(file_name)
    
        # Adicionar os arquivos encontrados à lista self.media_files
        self.media_files.extend(found_media)
        self.media_files = list(dict.fromkeys(self.media_files))  # Remover duplicatas, mantendo a ordem

    def update_tag_numbers(self):
        linhas_tags = self.txt_tags.toPlainText().strip().split('\n')
        num_linhas_cards = len(self.txt_entrada.toPlainText().strip().splitlines())
        
        if not any(linhas_tags) and num_linhas_cards > 0:
            self.txt_tags.setPlainText('\n'.join(f"{i + 1}" for i in range(num_linhas_cards)))
            self.initial_numbering_set = True
            self.update_preview()
            return

        if self.chk_num_tags.isChecked() and not self.initial_numbering_set:
            updated_tags = []
            for i in range(num_linhas_cards):
                if i < len(linhas_tags) and linhas_tags[i].strip():
                    tags_for_card = [tag.rstrip('0123456789') for tag in linhas_tags[i].split(',') if tag.strip()]
                    numbered_tags = [f"{tag}{i + 1}" for tag in tags_for_card]
                    updated_tags.append(", ".join(numbered_tags))
                else:
                    updated_tags.append("")
            self.txt_tags.setPlainText('\n'.join(updated_tags))
            self.initial_numbering_set = True
        elif not self.chk_num_tags.isChecked():
            updated_tags = []
            for i in range(num_linhas_cards):
                if i < len(linhas_tags) and linhas_tags[i].strip():
                    tags_for_card = [tag.rstrip('0123456789') for tag in linhas_tags[i].split(',') if tag.strip()]
                    updated_tags.append(", ".join(tags_for_card))
                else:
                    updated_tags.append("")
            self.txt_tags.setPlainText('\n'.join(updated_tags))
            self.initial_numbering_set = False

        self.update_preview()

    def update_repeated_tags(self):
        if self.chk_repetir_tags.isChecked() and not self.initial_tags_set:
            linhas_tags = self.txt_tags.toPlainText().strip().split('\n')
            num_cards = len(self.txt_entrada.toPlainText().strip().splitlines())
            
            if not any(linhas_tags):
                self.txt_tags.setPlainText('\n' * (num_cards - 1))
                self.initial_tags_set = True
                self.update_preview()
                return
            
            # Pegar as tags da primeira linha não vazia
            first_non_empty = next((tags for tags in linhas_tags if tags.strip()), None)
            if not first_non_empty:
                self.txt_tags.setPlainText('\n' * (num_cards - 1))
                self.initial_tags_set = True
                self.update_preview()
                return
            
            tags = list(dict.fromkeys([tag.strip() for tag in first_non_empty.split(',') if tag.strip()]))
            if not tags:
                self.txt_tags.setPlainText('\n' * (num_cards - 1))
                self.initial_tags_set = True
                self.update_preview()
                return
            
            # Repetir as tags para todas as linhas
            self.txt_tags.setPlainText('\n'.join([", ".join(tags)] * num_cards))
            self.initial_tags_set = True
        elif not self.chk_repetir_tags.isChecked():
            self.initial_tags_set = False
            self.update_tag_numbers()

        self.update_preview()

    def search_text(self):
        search_query = self.search_input.text().strip()
        if not search_query:
            showWarning("Por favor, insira um texto para pesquisar.")
            return
        search_words = search_query.split()
        if search_query != self.last_search_query:
            self.last_search_query = search_query
            self.last_search_position = 0
        cursor = self.txt_entrada.textCursor()
        cursor.setPosition(self.last_search_position)
        self.txt_entrada.setTextCursor(cursor)
        found = False
        for word in search_words:
            if self.txt_entrada.find(word):
                self.last_search_position = self.txt_entrada.textCursor().position()
                found = True
                break
        if not found:
            self.txt_entrada.moveCursor(QTextCursor.MoveOperation.Start)
            for word in search_words:
                if self.txt_entrada.find(word):
                    self.last_search_position = self.txt_entrada.textCursor().position()
                    found = True
                    break
        if not found:
            showWarning(f"Texto '{search_query}' não encontrado.")
        self.update_preview()

    def replace_text(self):
        search_query = self.search_input.text().strip()
        replace_text = self.replace_input.text().strip()
        if not search_query:
            showWarning("Por favor, insira um texto para pesquisar.")
            return
        full_text = self.txt_entrada.toPlainText()
        replaced_text = re.sub(re.escape(search_query), replace_text, full_text, flags=re.IGNORECASE)
        self.txt_entrada.setPlainText(replaced_text)
        self.previous_text = replaced_text
        self.update_preview()
        showInfo(f"Todas as ocorrências de '{search_query}' foram {'substituídas por ' + replace_text if replace_text else 'removidas'}.")

    def zoom_in(self):
        self.txt_entrada.zoomIn(1)
        self.zoom_factor += 0.1

    def create_deck(self):
        deck_name = self.deck_name_input.text().strip()
        if not deck_name:
            showWarning("Por favor, insira um nome para o deck!")
            return
        try:
            mw.col.decks.id(deck_name)
            self.lista_decks.clear()
            self.lista_decks.addItems([d.name for d in mw.col.decks.all_names_and_ids()])
            self.deck_name_input.clear()
            showInfo(f"Deck '{deck_name}' criado com sucesso!")
        except Exception as e:
            showWarning(f"Erro ao criar o deck: {str(e)}")

    def zoom_out(self):
        if self.zoom_factor > 0.2:
            self.txt_entrada.zoomOut(1)
            self.zoom_factor -= 0.1

    def filter_list(self, list_widget, search_input, full_list):
        search_text = search_input.text().strip().lower()
        filtered = [item for item in full_list if search_text in item.lower()]
        list_widget.clear()
        list_widget.addItems(filtered)
        if filtered and search_text:
            list_widget.setCurrentRow(0)

    def filter_decks(self):
        self.filter_list(self.lista_decks, self.decks_search_input, [d.name for d in mw.col.decks.all_names_and_ids()])

    def filter_notetypes(self):
        self.filter_list(self.lista_notetypes, self.notetypes_search_input, mw.col.models.all_names())

    def create_focus_handler(self, widget, field_type):
        def focus_in_event(event):
            self.txt_entrada.setStyleSheet("")
            self.txt_tags.setStyleSheet("")
            widget.setStyleSheet(f"border: 2px solid {'blue' if field_type == 'cards' else 'green'};")
            self.tags_label.setText("Etiquetas:" if field_type == "cards" else "Etiquetas (Selecionado)")
            if isinstance(widget, QTextEdit):
                QTextEdit.focusInEvent(widget, event)
        return focus_in_event

    def concatenate_text(self):
        clipboard = QApplication.clipboard()
        copied_text = clipboard.text().strip().split("\n")
        current_widget = self.txt_entrada if self.txt_entrada.styleSheet() else self.txt_tags if self.txt_tags.styleSheet() else self.txt_entrada
        current_text = current_widget.toPlainText().strip().split("\n")
        result_lines = [f"{current_text[i] if i < len(current_text) else ''}{copied_text[i] if i < len(copied_text) else ''}".strip() for i in range(max(len(current_text), len(copied_text)))]
        current_widget.setPlainText("\n".join(result_lines))
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def add_cloze_1(self):
        cursor = self.txt_entrada.textCursor()
        selected_text = cursor.selectedText().strip()
        if not selected_text:
            showWarning("Por favor, selecione uma palavra para adicionar o cloze.")
            return
        cursor.insertText(f"{{{{c1::{selected_text}}}}}")
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def add_cloze_2(self):
        cursor = self.txt_entrada.textCursor()
        selected_text = cursor.selectedText().strip()
        if not selected_text:
            showWarning("Por favor, selecione uma palavra para adicionar o cloze.")
            return
        cursor.insertText(f"{{{{c{self.cloze_2_count}::{selected_text}}}}}")
        self.cloze_2_count += 1
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def remove_cloze(self):
        self.txt_entrada.setPlainText(re.sub(r'{{c\d+::(.*?)}}', r'\1', self.txt_entrada.toPlainText()))
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                dados = json.load(f)
                self.txt_entrada.setPlainText(dados.get('conteudo', ''))
                self.previous_text = self.txt_entrada.toPlainText()
                self.txt_tags.setPlainText(dados.get('tags', ''))
                for nome, estado in dados.get('delimitadores', {}).items():
                    if nome in self.chk_delimitadores:
                        self.chk_delimitadores[nome].setChecked(estado)
                for key, lista in [('deck_selecionado', self.lista_decks), ('modelo_selecionado', self.lista_notetypes)]:
                    if dados.get(key):
                        items = lista.findItems(dados[key], Qt.MatchFlag.MatchExactly)
                        if items:
                            lista.setCurrentItem(items[0])

    def closeEvent(self, event):
        dados = {
            'conteudo': self.txt_entrada.toPlainText(),
            'tags': self.txt_tags.toPlainText(),
            'delimitadores': {nome: chk.isChecked() for nome, chk in self.chk_delimitadores.items()},
            'deck_selecionado': self.lista_decks.currentItem().text() if self.lista_decks.currentItem() else '',
            'modelo_selecionado': self.lista_notetypes.currentItem().text() if self.lista_notetypes.currentItem() else ''
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(dados, f)
        super().closeEvent(event)

    def join_lines(self):
        texto = self.txt_entrada.toPlainText()
        if '\n' not in texto:
            if hasattr(self, 'original_text'):
                self.txt_entrada.setPlainText(self.original_text)
                del self.original_text
        else:
            self.original_text = texto
            self.txt_entrada.setPlainText(texto.replace('\n', ' '))
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def wrap_selected_text(self, tag):
        cursor = self.txt_entrada.textCursor()
        if cursor.hasSelection():
            texto = cursor.selectedText()
            cursor.insertText(f"{tag[0]}{texto}{tag[1]}")
        else:
            cursor.insertText(f"{tag[0]}{tag[1]}")
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(tag[1]))
            self.txt_entrada.setTextCursor(cursor)
        self.previous_text = self.txt_entrada.toPlainText()
        self.update_preview()

    def apply_bold(self): self.wrap_selected_text(('<b>', '</b>'))
    def apply_italic(self): self.wrap_selected_text(('<i>', '</i>'))
    def apply_underline(self): self.wrap_selected_text(('<u>', '</u>'))
    def destaque_texto(self): self.wrap_selected_text(('<mark>', '</mark>'))

    def manage_media(self):
        # Escanear o texto para encontrar arquivos de mídia referenciados
        self.scan_media_files_from_text()
        
        if not self.media_files:
            showWarning("Nenhum arquivo de mídia foi adicionado ou referenciado no texto!")
            return
        dialog = MediaManagerDialog(self, self.media_files, self.txt_entrada, mw)
        dialog.exec()

    def view_cards_dialog(self):
        if self.visualizar_dialog is None or not self.visualizar_dialog.isVisible():
            self.visualizar_dialog = VisualizarCards(self)
            self.visualizar_dialog.show()
        else:
            self.visualizar_dialog.raise_()
            self.visualizar_dialog.activateWindow()