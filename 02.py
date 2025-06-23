import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget, QLabel
)
from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtCore import Qt
from googletrans import Translator

def load_dict(file):
    d_en2zh = {}
    with open(file, encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue
            en, zh = parts
            en, zh = en.strip(), zh.strip()
            if en and zh:
                d_en2zh[en.lower()] = zh
    return d_en2zh

class NightDict(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('离线英译中词典（支持在线谷歌翻译）')
        self.resize(520, 260)
        self.dict_en2zh = load_dict('dict.txt')
        self.translator = Translator()

        # 美观字体
        font = QFont('微软雅黑', 12)
        self.setFont(font)

        # 夜间配色
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#23272e"))
        palette.setColor(QPalette.WindowText, QColor("#e6e6e6"))
        palette.setColor(QPalette.Base, QColor("#262b33"))
        palette.setColor(QPalette.AlternateBase, QColor("#262b33"))
        palette.setColor(QPalette.Text, QColor("#e6e6e6"))
        palette.setColor(QPalette.Button, QColor("#353b43"))
        palette.setColor(QPalette.ButtonText, QColor("#e6e6e6"))
        palette.setColor(QPalette.Highlight, QColor("#3e81c8"))
        palette.setColor(QPalette.HighlightedText, QColor("#fff"))
        self.setPalette(palette)

        # UI 组件
        title = QLabel("🌙 离线英译中词典（夜间模式）")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #90caf9; margin-bottom:8px;")

        self.input = QLineEdit(self)
        self.input.setPlaceholderText('请输入英文单词或短语...')
        self.input.setStyleSheet("""
            background: #262b33;
            color: #fff;
            border: 1px solid #353b43;
            padding: 6px 8px;
            border-radius: 6px;
        """)

        self.btn = QPushButton('查询', self)
        self.btn.setStyleSheet("""
            background: #353b43;
            color: #90caf9;
            padding: 6px 16px;
            border-radius: 6px;
        """)

        self.output = QTextBrowser(self)
        self.output.setStyleSheet("""
            background: #262b33;
            color: #e6e6e6;
            border: 1px solid #353b43;
            border-radius: 6px;
            font-size: 15px;
        """)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        layout.addWidget(self.output)
        layout.setSpacing(12)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # 事件绑定
        self.btn.clicked.connect(self.lookup)
        self.input.returnPressed.connect(self.lookup)

    def lookup(self):
        text = self.input.text().strip()
        if not text:
            self.output.setText("请输入要查询的英文内容")
            return
        result = self.dict_en2zh.get(text.lower())
        if result:
            self.output.setText(result)
        else:
            self.output.setText("未找到本地词条，正在使用Google翻译...\n")
            QApplication.processEvents()  # 立即刷新GUI
            try:
                translation = self.translator.translate(text, src='en', dest='zh-cn').text
                self.output.append(f"【Google翻译】\n{translation}")
            except Exception as e:
                self.output.append(f"【Google翻译失败】\n{e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = NightDict()
    win.show()
    sys.exit(app.exec_())
