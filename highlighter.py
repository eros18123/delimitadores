# highlighter.py

import re
from aqt.qt import QSyntaxHighlighter, QTextCharFormat, Qt

class HtmlTagHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Formato para tags HTML (qualquer coisa entre < e >) - Vermelho
        tag_format = QTextCharFormat()
        tag_format.setForeground(Qt.GlobalColor.red)
        self.highlighting_rules.append((re.compile(r'<[^>]+>'), tag_format))

        # Formato para ponto e vírgula (;) - Fundo amarelo e letra preta
        semicolon_format = QTextCharFormat()
        semicolon_format.setBackground(Qt.GlobalColor.yellow)  # Fundo amarelo
        semicolon_format.setForeground(Qt.GlobalColor.black)  # Letra preta
        self.highlighting_rules.append((re.compile(r';'), semicolon_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                self.setFormat(start, end - start, format)