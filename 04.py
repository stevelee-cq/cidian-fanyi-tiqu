import sys
import urllib.parse
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget, QLabel, QHBoxLayout
)
from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
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
        self.setWindowTitle('离线英译中词典（集成必应翻译网页）')
        self.resize(800, 540)
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

        self.close_web_btn = QPushButton('关闭在线翻译网页', self)
        self.close_web_btn.setStyleSheet("""
            background: #c62828;
            color: #fff;
            padding: 6px 12px;
            border-radius: 6px;
        """)
        self.close_web_btn.setVisible(False)  # 默认隐藏

        self.output = QTextBrowser(self)
        self.output.setStyleSheet("""
            background: #262b33;
            color: #e6e6e6;
            border: 1px solid #353b43;
            border-radius: 6px;
            font-size: 15px;
            min-height: 90px;
            max-height: 120px;
        """)

        self.webview = QWebEngineView(self)
        self.webview.setVisible(False)  # 默认隐藏

        # 主界面布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(title)
        main_layout.addWidget(self.input)
        main_layout.addWidget(self.btn)
        main_layout.addWidget(self.output)
        # 单独一行：关闭按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.close_web_btn)
        btn_row.addStretch(1)
        main_layout.addLayout(btn_row)
        main_layout.addWidget(self.webview)
        main_layout.setSpacing(12)
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # 事件绑定
        self.btn.clicked.connect(self.lookup)
        self.input.returnPressed.connect(self.lookup)
        self.close_web_btn.clicked.connect(self.hide_webview)

    def hide_webview(self):
        self.webview.setVisible(False)
        self.close_web_btn.setVisible(False)
        self.output.append("已关闭在线翻译网页。")

    def lookup(self):
        text = self.input.text().strip()
        self.webview.setVisible(False)
        self.close_web_btn.setVisible(False)
        if not text:
            self.output.setText("请输入要查询的英文内容")
            return
        result = self.dict_en2zh.get(text.lower())
        if result:
            self.output.setText(result)
            return

        self.output.setText("未找到本地词条，正在使用Google翻译...\n")
        QApplication.processEvents()
        show_web = False
        translation = None

        try:
            translation = self.translator.translate(text, src='en', dest='zh-cn').text
            self.output.append(f"【Google翻译】\n{translation}")
            if translation.strip().lower() == text.strip().lower():
                show_web = True
        except Exception as e:
            self.output.append(f"【Google翻译失败】\n{e}")
            show_web = True

        if show_web:
            self.output.append("正在加载必应在线翻译网页，请稍候...")
            QApplication.processEvents()
            url = f"https://cn.bing.com/translator?from=en&to=zh-Hans&text={urllib.parse.quote(text)}"
            self.webview.load(QUrl(url))
            self.webview.setVisible(True)
            self.close_web_btn.setVisible(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = NightDict()
    win.show()
    sys.exit(app.exec_())
