import sys
import requests
import re
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

def baidu_web_translate(text):
    # 百度翻译网页版接口（无需apikey，模拟GET即可）
    try:
        session = requests.Session()
        url = "https://fanyi.baidu.com/#en/zh/" + requests.utils.quote(text)
        # 获取页面html内容
        html = session.get(url, timeout=5, headers={
            "User-Agent": "Mozilla/5.0"
        }).text
        # 用正则粗暴提取翻译结果（适配当前网页版，如百度更新可能失效）
        m = re.search(r'<p class="ordinary-output target-output clearfix"[^>]*>(.*?)</p>', html)
        if m:
            result = m.group(1)
            # 百度网页返回会有html实体，需要替换掉
            return re.sub('<.*?>', '', result).replace('&nbsp;', ' ').replace('&amp;', '&')
        else:
            # 新版页面2024后，实际翻译结果在 window.g_result 里，可以继续抓
            m2 = re.search(r'"dst":"([^"]+)"', html)
            if m2:
                return m2.group(1).replace('\\n', '\n').replace('&nbsp;', ' ').replace('&amp;', '&')
            return "未获取到百度翻译网页结果"
    except Exception as e:
        return f"【百度网页翻译失败】{e}"

class NightDict(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('离线英译中词典（支持Google/百度网页翻译）')
        self.resize(540, 300)
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
            return

        self.output.setText("未找到本地词条，正在使用Google翻译...\n")
        QApplication.processEvents()
        # Step 2: Google翻译
        try:
            translation = self.translator.translate(text, src='en', dest='zh-cn').text
            self.output.append(f"【Google翻译】\n{translation}")
        except Exception as e:
            self.output.append(f"【Google翻译失败】\n{e}")
            self.output.append("正在尝试百度网页翻译...\n")
            QApplication.processEvents()
            # Step 3: 百度网页翻译兜底
            baidu_result = baidu_web_translate(text)
            self.output.append(f"【百度网页翻译】\n{baidu_result}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = NightDict()
    win.show()
    sys.exit(app.exec_())
