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
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from googletrans import Translator
import urllib.parse

# ========== 资源初始化 ==========
nltk.download('words')
nltk.download('stopwords')
nlp = spacy.load("en_core_web_sm")
english_vocab = set(w.lower() for w in nltk_words.words())
stop_words = set(stopwords.words('english'))
translator = Translator()

# ========== 词典与熟词库加载 ==========
DICT_FILE = "dict.txt"
SYS_KNOWN_WORDS_FILE = "46merged.txt"
USER_KNOWN_WORDS_FILE = "shuci02.txt"  # 新增：用户成长熟词库

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
    """加载一类熟词文件到集合"""
    known_words = set()
    if not os.path.exists(path):
        return known_words
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            word = line.strip().split()[0].lower()
            if word:
                known_words.add(word)
    return known_words

def save_user_known_words(new_lines):
    """追加新熟词到用户熟词文件"""
    with open(USER_KNOWN_WORDS_FILE, "a", encoding="utf-8") as f:
        for line in new_lines:
            f.write(line + "\n")

def reload_user_known_words():
    """重新读取用户成长熟词文件"""
    return load_known_words(USER_KNOWN_WORDS_FILE)

DICT = load_dict(DICT_FILE)
SYS_KNOWN_WORDS = load_known_words(SYS_KNOWN_WORDS_FILE)
USER_KNOWN_WORDS = load_known_words(USER_KNOWN_WORDS_FILE)

def google_translate(word):
    try:
        result = translator.translate(word, src='en', dest='zh-cn')
        return result.text
    except Exception as e:
        return "【翻译失败】"

# ========== PDF单词提取线程 ==========
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

# ========== 生词保存对话框：支持保存txt、同步加入熟词库 ==========
class SaveUnknownWordsDialog(QDialog):
    def __init__(self, unknown_word_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择要保存的生词/同步加入新熟词库")
        self.setMinimumWidth(650)
        vbox = QVBoxLayout(self)
        label = QLabel("请勾选要保存的生词（勾选=加入熟词库shuci02.txt，下次自动识别为熟词）：")
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
        btn_save = QPushButton("保存勾选生词到txt/同步入熟词库")
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

    def get_selected_word_pairs(self):
        """返回勾选的单词及其翻译，用于加入熟词库"""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                content = item.text()
                word = content.split()[0]
                # 解析翻译部分
                try:
                    trans = content.split("翻译:")[1].strip()
                except Exception:
                    trans = ""
                selected.append((word, trans))
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

        # ------ 左右分栏（加标题和计数） ------
        self.left_label = QLabel()
        self.left_label.setStyleSheet("color:#81c784;font-size:14px;font-weight:bold;padding:2px;")
        self.known_edit = QTextEdit()
        self.known_edit.setReadOnly(True)
        self.known_edit.setPlaceholderText("熟词（含翻译）")
        left_vbox = QVBoxLayout()
        left_vbox.addWidget(self.left_label)
        left_vbox.addWidget(self.known_edit)

        self.right_label = QLabel()
        self.right_label.setStyleSheet("color:#64b5f6;font-size:14px;font-weight:bold;padding:2px;")
        self.unknown_edit = QTextEdit()
        self.unknown_edit.setReadOnly(True)
        self.unknown_edit.setPlaceholderText("生词（含翻译）")
        right_vbox = QVBoxLayout()
        right_vbox.addWidget(self.right_label)
        right_vbox.addWidget(self.unknown_edit)

        text_layout = QHBoxLayout()
        text_layout.addLayout(left_vbox, 1)
        text_layout.addLayout(right_vbox, 1)

        # 页码输入区
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
        layout.addLayout(text_layout)
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
                self.left_label.setText("【熟词（含翻译，数量：0）】")
                self.right_label.setText("【生词（含翻译，数量：0）】")
                self.known_edit.setText(f"✅ 已加载文件（共 {self.total_pages} 页）：{self.pdf_path}\n")
                self.unknown_edit.clear()
            except Exception as e:
                self.known_edit.setText(f"❌ 无法读取PDF页数：{e}")
                self.unknown_edit.clear()

    def extract_words(self):
        global USER_KNOWN_WORDS
        USER_KNOWN_WORDS = load_known_words(USER_KNOWN_WORDS_FILE)  # 动态刷新
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

        self.left_label.setText("【熟词（含翻译，数量：0）】")
        self.right_label.setText("【生词（含翻译，数量：0）】")
        self.known_edit.setText(f"⏳ 正在分析第 {start_page} 页至第 {end_page} 页内容...\n")
        self.unknown_edit.clear()
        self.progress_bar.setValue(0)
        self.save_button.setEnabled(False)
        self.worker = ExtractWorker(self.pdf_path, start_page, end_page)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.result.connect(self.display_result)
        self.worker.start()

    def display_result(self, word_counter: Counter, pdf_path: str):
        global USER_KNOWN_WORDS
        USER_KNOWN_WORDS = load_known_words(USER_KNOWN_WORDS_FILE)  # 动态刷新
        if "❌ 提取失败" in word_counter:
            self.left_label.setText("【熟词（含翻译，数量：0）】")
            self.right_label.setText("【生词（含翻译，数量：0）】")
            self.known_edit.setText("❌ 提取失败，请检查PDF是否包含可识别文本内容。")
            self.unknown_edit.clear()
            self.save_button.setEnabled(False)
            return
        self.word_counter = word_counter
        self.save_button.setEnabled(True)
        known, unknown = [], []
        for word in sorted(word_counter.keys()):  # 字典序
            freq = word_counter[word]
            if (word in SYS_KNOWN_WORDS) or (word in USER_KNOWN_WORDS):
                trans = DICT.get(word, "[本地词典无翻译]")
                known.append(f"{word:<18} {freq:<4} {trans}")
            else:
                trans = DICT.get(word, "")
                if not trans:
                    trans = google_translate(word)
                unknown.append((word, freq, trans))

        self.left_label.setText(f"【熟词（含翻译，数量：{len(known)}）】")
        self.right_label.setText(f"【生词（含翻译，数量：{len(unknown)}）】")

        self.unknown_word_list = unknown
        self.known_edit.setText("\n".join(known) if known else "无熟词")
        self.unknown_edit.setText("\n".join([f"{w:<18} {f:<4} {t}" for w, f, t in unknown] if unknown else ["无生词"]))

    def show_and_save_unknown_words(self):
        if not self.unknown_word_list:
            QMessageBox.information(self, "无生词", "未检测到生词，无需保存。")
            return
        dlg = SaveUnknownWordsDialog(self.unknown_word_list, parent=self)
        if dlg.exec_():
            selected = dlg.get_selected_words()
            selected_pairs = dlg.get_selected_word_pairs()
            if selected:
                # 保存到txt
                base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
                out_path, _ = QFileDialog.getSaveFileName(self, "保存为...", base_name + "_生词翻译.txt", "Text Files (*.txt)")
                if out_path:
                    with open(out_path, "w", encoding="utf-8") as f:
                        for line in selected:
                            f.write(line.strip() + "\n")
                    QMessageBox.information(self, "保存成功", f"翻译结果已保存至：\n{out_path}")
            if selected_pairs:
                # 追加到shuci02.txt，去重
                existing = load_known_words(USER_KNOWN_WORDS_FILE)
                new_lines = []
                for word, trans in selected_pairs:
                    if word not in existing:
                        new_lines.append(f"{word} {trans}")
                if new_lines:
                    save_user_known_words(new_lines)
                    QMessageBox.information(self, "同步成功", f"已将勾选生词加入新熟词库 shuci02.txt（下次统计会自动识别为熟词）")
                else:
                    QMessageBox.information(self, "未新增熟词", "勾选生词均已存在于熟词库，无需重复添加。")
            else:
                QMessageBox.information(self, "未保存", "未选择任何生词，未保存文件/未同步熟词库。")

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
        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        layout.addWidget(self.output)
        layout.setSpacing(12)
        self.setLayout(layout)
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
            QApplication.processEvents()
            try:
                translation = self.translator.translate(text, src='en', dest='zh-cn').text
                self.output.append(f"【Google翻译】\n{translation}")
            except Exception as e:
                self.output.append(f"【Google翻译失败】\n{e}")

# ========== 主程序 ==========
from PyQt5.QtWidgets import QTabWidget

class MainTabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("学术英语助手 | 词典 + PDF单词统计（夜间美观版）")
        self.resize(1300, 820)
        self.tabs = QTabWidget()
        self.tabs.addTab(NightDict(), "英汉词典查询")
        self.tabs.addTab(PDFWordExtractor(), "PDF词频/生词翻译")
        self.setCentralWidget(self.tabs)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainTabWindow()
    window.show()
    sys.exit(app.exec_())
