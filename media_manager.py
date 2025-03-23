# media_manager.py

import os
import subprocess  # Para abrir o arquivo com o player padrão
from aqt.qt import *
from aqt.utils import showInfo, showWarning
from aqt.webview import QWebEngineView

class MediaManagerDialog(QDialog):
    def __init__(self, parent, media_files, txt_entrada, mw_instance):
        super().__init__(parent)
        self.media_files = media_files
        self.txt_entrada = txt_entrada
        self.mw = mw_instance  # Receber a instância de mw
        self.media_dir = self.mw.col.media.dir()  # Diretório de mídia do Anki
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Gerenciar Mídia")
        self.resize(400, 300)
        layout = QVBoxLayout()

        # Lista de arquivos de mídia
        self.media_list = QListWidget()
        self.media_list.addItems(self.media_files)
        self.media_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.media_list)

        # Botões
        btn_layout = QHBoxLayout()
        delete_btn = QPushButton("Excluir Arquivo", self)
        delete_btn.clicked.connect(self.delete_file)
        btn_layout.addWidget(delete_btn)

        rename_btn = QPushButton("Renomear Arquivo", self)
        rename_btn.clicked.connect(self.rename_file)
        btn_layout.addWidget(rename_btn)

        # Botão para visualizar mídia
        preview_btn = QPushButton("Visualizar Mídia", self)
        preview_btn.clicked.connect(self.preview_media)
        btn_layout.addWidget(preview_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def delete_file(self):
        selected_item = self.media_list.currentItem()
        if not selected_item:
            showWarning("Selecione um arquivo para excluir!")
            return

        file_name = selected_item.text()
        file_path = os.path.join(self.media_dir, file_name)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.media_files.remove(file_name)
                self.media_list.takeItem(self.media_list.currentRow())
                # Atualizar o texto para remover referências ao arquivo excluído
                current_text = self.txt_entrada.toPlainText()
                updated_text = current_text.replace(file_name, "")
                self.txt_entrada.setPlainText(updated_text)
                showInfo(f"Arquivo '{file_name}' excluído com sucesso!")
            except Exception as e:
                showWarning(f"Erro ao excluir o arquivo: {str(e)}")
        else:
            showWarning(f"Arquivo '{file_name}' não encontrado na pasta de mídia!")

    def rename_file(self):
        selected_item = self.media_list.currentItem()
        if not selected_item:
            showWarning("Selecione um arquivo para renomear!")
            return

        old_name = selected_item.text()
        new_name, ok = QInputDialog.getText(self, "Renomear Arquivo", "Digite o novo nome:", text=old_name)
        if not ok or not new_name:
            return

        # Verificar se o novo nome já existe
        if new_name in self.media_files and new_name != old_name:
            showWarning(f"O nome '{new_name}' já existe na lista de arquivos!")
            return

        old_path = os.path.join(self.media_dir, old_name)
        new_path = os.path.join(self.media_dir, new_name)
        if os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
                # Atualizar a lista de arquivos
                index = self.media_files.index(old_name)
                self.media_files[index] = new_name
                selected_item.setText(new_name)
                # Atualizar o texto no QTextEdit
                current_text = self.txt_entrada.toPlainText()
                updated_text = current_text.replace(old_name, new_name)
                self.txt_entrada.setPlainText(updated_text)
                showInfo(f"Arquivo renomeado de '{old_name}' para '{new_name}' com sucesso!")
            except Exception as e:
                showWarning(f"Erro ao renomear o arquivo: {str(e)}")
        else:
            showWarning(f"Arquivo '{old_name}' não encontrado na pasta de mídia!")

    def preview_media(self):
        selected_item = self.media_list.currentItem()
        if not selected_item:
            showWarning("Selecione um arquivo para visualizar!")
            return

        file_name = selected_item.text()
        file_path = os.path.join(self.media_dir, file_name)
        if not os.path.exists(file_path):
            showWarning(f"Arquivo '{file_name}' não encontrado na pasta de mídia!")
            return

        ext = os.path.splitext(file_name)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg'):
            # Visualizar imagens estáticas (PNG, JPG, JPEG) em uma nova janela
            self.preview_image(file_path, file_name)
        elif ext == '.gif':
            # Visualizar GIFs animados usando QMovie
            self.preview_gif(file_path, file_name)
        elif ext in ('.mp3', '.wav', '.ogg', '.mp4', '.webm'):
            # Visualizar áudio e vídeo usando QMediaPlayer
            self.preview_audio_video(file_path, file_name, ext)
        else:
            showWarning(f"Tipo de arquivo '{ext}' não suportado para visualização!")

    def preview_image(self, file_path, file_name):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Visualizar: {file_name}")
        layout = QVBoxLayout()

        # Carregar e exibir a imagem
        image = QImage(file_path)
        if image.isNull():
            showWarning(f"Erro ao carregar a imagem '{file_name}'!")
            return

        label = QLabel()
        pixmap = QPixmap.fromImage(image)
        # Redimensionar a imagem para caber na janela, mantendo a proporção
        max_size = QSize(600, 400)
        scaled_pixmap = pixmap.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled_pixmap)
        layout.addWidget(label)

        # Botão para fechar
        #close_btn = QPushButton("Fechar", dialog)
        #close_btn.clicked.connect(dialog.accept)
        #layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def preview_gif(self, file_path, file_name):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Visualizar: {file_name}")
        layout = QVBoxLayout()

        # Carregar e exibir o GIF animado usando QMovie
        movie = QMovie(file_path)
        if not movie.isValid():
            showWarning(f"Erro ao carregar o GIF '{file_name}'!")
            return

        label = QLabel()
        label.setMovie(movie)
        # Redimensionar o GIF para caber na janela, mantendo a proporção
        movie.setScaledSize(QSize(600, 400))
        movie.start()
        layout.addWidget(label)

        # Botão para fechar
        #close_btn = QPushButton("Fechar", dialog)
        #close_btn.clicked.connect(dialog.accept)
        #layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def preview_audio_video(self, file_path, file_name, ext):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Visualizar: {file_name}")
        dialog.resize(400, 300)
        layout = QVBoxLayout()

        # Usar QMediaPlayer e QVideoWidget para reproduzir áudio e vídeo
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        except ImportError:
            showWarning("Módulos de multimídia do Qt não estão disponíveis. Certifique-se de que o Qt Multimedia está instalado.")
            return

        player = QMediaPlayer()
        audio_output = QAudioOutput()
        player.setAudioOutput(audio_output)

        # Função para abrir o arquivo com o player padrão do sistema
        def open_with_default_player():
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # macOS/Linux
                    subprocess.run(['xdg-open', file_path])
                else:
                    showWarning("Não foi possível abrir o arquivo com o player padrão do sistema.")
                dialog.accept()  # Fechar a janela de visualização
            except Exception as e:
                showWarning(f"Erro ao abrir o arquivo com o player padrão: {str(e)}")

        if ext in ('.mp4', '.webm'):
            video_widget = QVideoWidget()
            player.setVideoOutput(video_widget)
            layout.addWidget(video_widget)

            # Adicionar controles para vídeo
            play_btn = QPushButton("Tocar", dialog)
            pause_btn = QPushButton("Pausar", dialog)
            #stop_btn = QPushButton("Parar", dialog)
            default_player_btn = QPushButton("Abrir com Player Padrão", dialog)
            controls_layout = QHBoxLayout()
            controls_layout.addWidget(play_btn)
            controls_layout.addWidget(pause_btn)
            #controls_layout.addWidget(stop_btn)
            controls_layout.addWidget(default_player_btn)
            layout.addLayout(controls_layout)

            play_btn.clicked.connect(player.play)
            pause_btn.clicked.connect(player.pause)
            #stop_btn.clicked.connect(player.stop)
            default_player_btn.clicked.connect(open_with_default_player)
        else:
            # Para áudio, adicionar controles básicos
            play_btn = QPushButton("Tocar", dialog)
            pause_btn = QPushButton("Pausar", dialog)
            #stop_btn = QPushButton("Parar", dialog)
            default_player_btn = QPushButton("Abrir com Player Padrão", dialog)
            controls_layout = QHBoxLayout()
            controls_layout.addWidget(play_btn)
            controls_layout.addWidget(pause_btn)
            #controls_layout.addWidget(stop_btn)
            controls_layout.addWidget(default_player_btn)
            layout.addLayout(controls_layout)

            play_btn.clicked.connect(player.play)
            pause_btn.clicked.connect(player.pause)
            #stop_btn.clicked.connect(player.stop)
            default_player_btn.clicked.connect(open_with_default_player)

        # Configurar o arquivo de mídia
        media_url = QUrl.fromLocalFile(file_path)
        player.setSource(media_url)

        # Verificar erros
        def handle_error():
            if player.error() != QMediaPlayer.Error.NoError:
                error_msg = f"Erro ao reproduzir o arquivo: {player.errorString()}\n\nVocê pode tentar abrir o arquivo com o player padrão do sistema."
                showWarning(error_msg)

        player.errorOccurred.connect(handle_error)

        # Botão para fechar
        #close_btn = QPushButton("Fechar", dialog)
        #close_btn.clicked.connect(dialog.accept)
        #layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def get_mime_type(self, ext):
        return {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
            '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
            '.mp4': 'video/mp4', '.webm': 'video/webm'
        }.get(ext, 'application/octet-stream')