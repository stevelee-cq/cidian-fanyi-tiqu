import sys, os, time
import pdfplumber
import spacy
import nltk
from collections import Counter
from nltk.corpus import words as nltk_words
from nltk.corpus import stopwords
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout,
    QWidget, QFileDialog, QTextEdit, QMessageBox, QProgressBar,
    QHBoxLayout, QLineEdit, QDialog, QTabWidget, QListWidget,
    QListWidgetItem
)
from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from googletrans import Translator
import urllib.parse

# ========== 环境和资源初始化 ==========
nltk.download('words')
nltk.download('stopwords')
nlp = spacy.load("en_core_web_sm")
english_vocab = set(w.lower() for w in nltk_words.words())
stop_words = set(stopwords.words('english'))
translator = Translator()

# ========== 词典与熟词库加载 ==========
def load_dict(file):
    d_en2zh = {}
    with open(file, encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue
            parts = line.split('\t', 1)
            if len(parts) != 2: continue
            en, zh = parts
            en, zh = en.strip(), zh.strip()
            if en and zh:
                d_en2zh[en.lower()] = zh
    return d_en2zh

def load_known_words(path):
    known_words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().split()[0].lower()
            if word:
                known_words.add(word)
    return known_words

DICT = load_dict("dict.txt")
KNOWN_WORDS = load_known_words("46merged.txt")

def google_translate(word):
    try:
        result = translator.translate(word, src='en', dest='zh-cn')
        return result.text
    except Exception as e:
        return "【翻译失败】"

# ========== PDF单词提取后台线程 ==========
class ExtractWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(Counter, str)

    def __init__(self, pdf_path, start_page, end_page):
        super().__init__()
        self.pdf_path = pdf_path
        self.start_page = start_page
        self.end_page = end_page

    def run(self):
        try:
            word_counter = Counter()
            with pdfplumber.open(self.pdf_path) as pdf:
                pages = pdf.pages[self.start_page - 1 : self.end_page]
                for i, page in enumerate(pages):
                    text = page.extract_text()
                    if text:
                        doc = nlp(text)
                        for token in doc:
                            if token.is_alpha and token.is_ascii and len(token) > 1:
                                lemma = token.lemma_.lower()
                                if lemma in english_vocab and lemma not in stop_words:
                                    word_counter[lemma] += 1
                    self.progress.emit(int((i + 1) / len(pages) * 100))
            self.result.emit(word_counter, self.pdf_path)
        except Exception as e:
            self.result.emit(Counter({"❌ 提取失败": 1}), self.pdf_path)

# ========== 生词翻译线程 ==========
class TranslateWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(self, unknown_word_list):
        super().__init__()
        self.unknown_word_list = unknown_word_list

    def run(self):
        lines = []
        total = len(self.unknown_word_list)
        for i, (word, freq) in enumerate(self.unknown_word_list):
            # 优先查词典
            trans = DICT.get(word, "")
            if not trans:
                trans = google_translate(word)
            lines.append((word, freq, trans))
            percent = int((i + 1) / total * 100)
            self.progress.emit(percent)
        self.finished.emit(lines)

# ========== 生词选择保存对话框 ==========
class SaveUnknownWordsDialog(QDialog):
    def __init__(self, unknown_word_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择要保存的生词")
        self.setMinimumWidth(600)
        self.selected_items = []

        vbox = QVBoxLayout(self)
        label = QLabel("请勾选要保存的生词（含翻译）：")
        vbox.addWidget(label)

        self.list_widget = QListWidget(self)
        for word, freq, trans in unknown_word_list:
            item = QListWidgetItem(f"{word:<16} 频率:{freq:<4} 翻译:{trans}")
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)
        vbox.addWidget(self.list_widget)

        hbox = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_none = QPushButton("全不选")
        btn_save = QPushButton("保存")
        btn_cancel = QPushButton("取消")
        hbox.addWidget(btn_all)
        hbox.addWidget(btn_none)
        hbox.addStretch(1)
        hbox.addWidget(btn_save)
        hbox.addWidget(btn_cancel)
        vbox.addLayout(hbox)

        btn_all.clicked.connect(self.check_all)
        btn_none.clicked.connect(self.uncheck_all)
        btn_save.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def check_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Checked)
    def uncheck_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Unchecked)
    def get_selected_words(self):
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

# ========== PDF 单词提取/生词翻译界面 ==========
class PDFWordExtractor(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #ffffff; font-family: 'Segoe UI'; font-size: 10.5pt; }
            QPushButton { background-color: #3A99D8; color: white; border-radius: 5px; padding: 6px; }
            QPushButton:hover { background-color: #5FB3E7; }
            QTextEdit { background-color: #282c34; border: 1px solid #444; color: #f8f8f2; font-family: Consolas; font-size: 10pt; }
            QLineEdit { background-color: #2e2e2e; border: 1px solid #555; border-radius: 4px; padding: 4px; color: white; }
            QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; background-color: #2e2e2e; color: white; }
            QProgressBar::chunk { background-color: #5CB85C; border-radius: 5px; }
        """)
        self.label = QLabel("📄 请选择PDF文献：")
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.start_page_input = QLineEdit()
        self.start_page_input.setPlaceholderText("起始页（从1开始）")
        self.end_page_input = QLineEdit()
        self.end_page_input.setPlaceholderText("结束页")

        self.select_button = QPushButton("选择PDF")
        self.extract_button = QPushButton("提取并统计词频")
        self.save_button = QPushButton("保存生词（可选）")
        self.save_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.trans_progress = QProgressBar()
        self.trans_progress.setVisible(False)

        page_layout = QHBoxLayout()
        page_layout.addWidget(self.start_page_input)
        page_layout.addWidget(self.end_page_input)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.select_button)
        layout.addLayout(page_layout)
        layout.addWidget(self.extract_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.trans_progress)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        self.select_button.clicked.connect(self.select_pdf)
        self.extract_button.clicked.connect(self.extract_words)
        self.save_button.clicked.connect(self.show_and_save_unknown_words)

        self.pdf_path = ""
        self.worker = None
        self.total_pages = 0
        self.word_counter = None
        self.unknown_word_list = []

    def select_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择PDF文件", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.label.setText(f"📄 当前文件：{os.path.basename(file_path)}")
            try:
                with pdfplumber.open(self.pdf_path) as pdf:
                    self.total_pages = len(pdf.pages)
                self.text_edit.append(f"✅ 已加载文件（共 {self.total_pages} 页）：{self.pdf_path}\n")
            except Exception as e:
                self.text_edit.append(f"❌ 无法读取PDF页数：{e}")

    def extract_words(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "⚠️ 未选择文件", "请先选择一个PDF文件")
            return
        try:
            start_page = int(self.start_page_input.text().strip())
            end_page = int(self.end_page_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "❌ 页码格式错误", "请输入有效的起始页和结束页（正整数）")
            return
        if start_page < 1 or end_page < start_page or end_page > self.total_pages:
            QMessageBox.warning(self, "❌ 页码范围错误", f"页码范围应在 1 ~ {self.total_pages} 之间，且起始页不大于结束页")
            return
        self.text_edit.clear()
        self.progress_bar.setValue(0)
        self.save_button.setEnabled(False)
        self.text_edit.append(f"⏳ 正在分析第 {start_page} 页至第 {end_page} 页内容...\n")
        self.worker = ExtractWorker(self.pdf_path, start_page, end_page)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.result.connect(self.display_result)
        self.worker.start()

    def display_result(self, word_counter: Counter, pdf_path: str):
        if "❌ 提取失败" in word_counter:
            self.text_edit.append("❌ 提取失败，请检查PDF是否包含可识别文本内容。")
            self.save_button.setEnabled(False)
            return
        self.word_counter = word_counter
        self.save_button.setEnabled(True)
        total_unique = len(word_counter)
        total_count = sum(word_counter.values())
        self.text_edit.append(f"✅ 有效英文总词数：{total_count}，唯一词汇：{total_unique} 个\n")
        known_count = 0
        unknown_count = 0
        for word, freq in word_counter.most_common():
            if word in KNOWN_WORDS:
                known_count += 1
                trans = DICT.get(word, "[本地词典无翻译]")
                self.text_edit.append(f"{word:<18} {freq:<4} [熟词] {trans}")
            else:
                unknown_count += 1
                self.text_edit.append(f"{word:<18} {freq:<4} [生词]")
        self.text_edit.append(f"\n熟词 {known_count} 个，生词 {unknown_count} 个。")

    def show_and_save_unknown_words(self):
        # 找出生词，先查本地词典，无则后续调用API翻译
        unknown_words = [(word, freq) for word, freq in self.word_counter.most_common() if word not in KNOWN_WORDS]
        if not unknown_words:
            QMessageBox.information(self, "无生词", "未检出生词，无需保存。")
            return
        self.trans_progress.setValue(0)
        self.trans_progress.setVisible(True)
        self.save_button.setEnabled(False)
        # 多线程翻译生词（先查dict.txt再查API）
        self.trans_worker = TranslateWorker(unknown_words)
        self.trans_worker.progress.connect(self.trans_progress.setValue)
        self.trans_worker.finished.connect(self.finish_translation)
        self.trans_worker.start()

    def finish_translation(self, lines):
        self.trans_progress.setValue(100)
        self.trans_progress.setVisible(False)
        self.save_button.setEnabled(True)
        # 弹窗让用户勾选
        dlg = SaveUnknownWordsDialog(lines, parent=self)
        if dlg.exec_():
            selected = dlg.get_selected_words()
            if selected:
                base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
                out_path, _ = QFileDialog.getSaveFileName(self, "保存为...", base_name + "_生词翻译.txt", "Text Files (*.txt)")
                if out_path:
                    with open(out_path, "w", encoding="utf-8") as f:
                        for line in selected:
                            f.write(line.strip() + "\n")
                    QMessageBox.information(self, "保存成功", f"翻译结果已保存至：\n{out_path}")
            else:
                QMessageBox.information(self, "未保存", "未选择任何生词，未保存文件。")

# ========== 词典查词/网页翻译界面 ==========
class NightDict(QWidget):
    def __init__(self):
        super().__init__()
        self.dict_en2zh = DICT
        self.translator = Translator()
        font = QFont('微软雅黑', 12)
        self.setFont(font)
        self.setStyleSheet("""
            QWidget { background-color: #23272e; color: #e6e6e6; }
            QLineEdit { background: #262b33; color: #fff; border: 1px solid #353b43; padding: 6px 8px; border-radius: 6px; }
            QPushButton { background: #353b43; color: #90caf9; padding: 6px 16px; border-radius: 6px; }
            QTextBrowser { background: #262b33; color: #e6e6e6; border: 1px solid #353b43; border-radius: 6px; font-size: 15px; }
        """)
        title = QLabel("🌙 离线英译中词典（夜间模式）")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #90caf9; margin-bottom:8px;")

        self.input = QLineEdit(self)
        self.input.setPlaceholderText('请输入英文单词或短语...')

        self.btn = QPushButton('查询', self)
        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.webview = QWebEngineView(self)
        self.webview.setVisible(False)
        self.close_web_btn = QPushButton('关闭在线翻译网页', self)
        self.close_web_btn.setVisible(False)
        self.close_web_btn.setStyleSheet("""
            background: #c62828;
            color: #fff;
            padding: 6px 12px;
            border-radius: 6px;
        """)

        main_layout = QVBoxLayout()
        main_layout.addWidget(title)
        main_layout.addWidget(self.input)
        main_layout.addWidget(self.btn)
        main_layout.addWidget(self.output)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.close_web_btn)
        btn_row.addStretch(1)
        main_layout.addLayout(btn_row)
        main_layout.addWidget(self.webview)
        main_layout.setSpacing(12)
        self.setLayout(main_layout)

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

# ========== 集成主界面 ==========
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("学术英语助手 | 词典 + PDF单词统计（夜间美观版）")
        self.resize(950, 700)
        tabs = QTabWidget()
        tabs.addTab(NightDict(), "英汉词典查词")
        tabs.addTab(PDFWordExtractor(), "PDF词频/生词翻译")
        self.setCentralWidget(tabs)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
