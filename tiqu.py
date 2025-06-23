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
    QHBoxLayout, QLineEdit, QDialog, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from wordcloud import WordCloud
import matplotlib
matplotlib.rcParams['axes.unicode_minus'] = False
import matplotlib.pyplot as plt
from googletrans import Translator

# ========== 资源初始化 ==========
nltk.download('words')
nltk.download('stopwords')
nlp = spacy.load("en_core_web_sm")
english_vocab = set(w.lower() for w in nltk_words.words())
stop_words = set(stopwords.words('english'))

translator = Translator()

# ========== 熟词库加载 ==========
def load_known_words(path):
    known_words = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().split()[0].lower()
            if word:
                known_words.add(word)
    return known_words

KNOWN_WORDS = load_known_words("46merged.txt")

def google_translate(word):
    try:
        result = translator.translate(word, src='en', dest='zh-cn')
        return result.text
    except Exception as e:
        return "【翻译失败】"

# ========== 后台提取线程 ==========
class ExtractWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(Counter, str)  # Counter结果 + PDF路径

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
    progress = pyqtSignal(int)   # 当前进度百分比
    finished = pyqtSignal(list)  # 最终结果（lines）

    def __init__(self, word_freq_list, known_words):
        super().__init__()
        self.word_freq_list = word_freq_list
        self.known_words = known_words

    def run(self):
        trans_cache = {}
        lines = []
        total = len(self.word_freq_list)
        for i, (word, freq) in enumerate(self.word_freq_list):
            if word in self.known_words:
                line = f"{word:<20} {freq:<6} [熟词]"
            else:
                if word in trans_cache:
                    translation = trans_cache[word]
                else:
                    translation = google_translate(word)
                    trans_cache[word] = translation
                    time.sleep(0.25)
                line = f"{word:<20} {freq:<6} {translation}"
            lines.append(line)
            percent = int((i + 1) / total * 100)
            self.progress.emit(percent)
        self.finished.emit(lines)

# ========== 主窗口类 ==========
class PDFWordExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("英文PDF单词词频提取器（熟词过滤+生词谷歌翻译 | 可视化 | 夜间风格）")
        self.setGeometry(100, 100, 900, 860)
        self.set_dark_theme_style()

        self.label = QLabel("📄 请选择PDF文献：")
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.start_page_input = QLineEdit()
        self.start_page_input.setPlaceholderText("起始页（从1开始）")
        self.end_page_input = QLineEdit()
        self.end_page_input.setPlaceholderText("结束页")

        self.select_button = QPushButton("选择PDF")
        self.extract_button = QPushButton("提取并统计词频")
        self.wordcloud_button = QPushButton("生成词云图")
        self.wordcloud_button.setEnabled(False)
        self.bar_button = QPushButton("高频词条形图")
        self.bar_button.setEnabled(False)
        self.save_button = QPushButton("保存为 txt")
        self.save_button.setEnabled(False)
        self.trans_button = QPushButton("显示/保存生词翻译")
        self.trans_button.setEnabled(False)
        self.show_words_button = QPushButton("显示熟词/生词")
        self.show_words_button.setEnabled(False)
        self.trans_progress = QProgressBar()
        self.trans_progress.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        # 页码输入区域
        page_layout = QHBoxLayout()
        page_layout.addWidget(self.start_page_input)
        page_layout.addWidget(self.end_page_input)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.select_button)
        layout.addLayout(page_layout)
        layout.addWidget(self.extract_button)
        layout.addWidget(self.wordcloud_button)
        layout.addWidget(self.bar_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.trans_button)
        layout.addWidget(self.show_words_button)
        layout.addWidget(self.trans_progress)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.text_edit)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.select_button.clicked.connect(self.select_pdf)
        self.extract_button.clicked.connect(self.extract_words)
        self.wordcloud_button.clicked.connect(self.show_wordcloud)
        self.bar_button.clicked.connect(self.show_bar_chart)
        self.save_button.clicked.connect(self.save_txt)
        self.trans_button.clicked.connect(self.show_and_save_translation)
        self.show_words_button.clicked.connect(self.show_known_unknown_words)

        self.pdf_path = ""
        self.worker = None
        self.total_pages = 0
        self.word_counter = None
        self.trans_worker = None

    def set_dark_theme_style(self):
        self.setStyleSheet("""
            QWidget { background-color: #1e1e1e; color: #ffffff; font-family: 'Segoe UI'; font-size: 10.5pt; }
            QPushButton { background-color: #3A99D8; color: white; border-radius: 5px; padding: 6px; }
            QPushButton:hover { background-color: #5FB3E7; }
            QTextEdit { background-color: #282c34; border: 1px solid #444; color: #f8f8f2; font-family: Consolas; font-size: 10pt; }
            QLineEdit { background-color: #2e2e2e; border: 1px solid #555; border-radius: 4px; padding: 4px; color: white; }
            QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; background-color: #2e2e2e; color: white; }
            QProgressBar::chunk { background-color: #5CB85C; border-radius: 5px; }
        """)

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
        self.wordcloud_button.setEnabled(False)
        self.bar_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.trans_button.setEnabled(False)
        self.show_words_button.setEnabled(False)
        self.text_edit.append(f"⏳ 正在分析第 {start_page} 页至第 {end_page} 页内容...\n")

        self.worker = ExtractWorker(self.pdf_path, start_page, end_page)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.result.connect(self.display_result)
        self.worker.start()

    def display_result(self, word_counter: Counter, pdf_path: str):
        if "❌ 提取失败" in word_counter:
            self.text_edit.append("❌ 提取失败，请检查PDF是否包含可识别文本内容。")
            self.wordcloud_button.setEnabled(False)
            self.bar_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.trans_button.setEnabled(False)
            self.show_words_button.setEnabled(False)
            return

        self.word_counter = word_counter
        self.wordcloud_button.setEnabled(True)
        self.bar_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.trans_button.setEnabled(True)
        self.show_words_button.setEnabled(True)

        total_unique = len(word_counter)
        total_count = sum(word_counter.values())

        self.text_edit.append(f"✅ 有效英文总词数：{total_count}，唯一词汇：{total_unique} 个\n")
        sorted_items = word_counter.most_common()

        for word, freq in sorted_items:
            self.text_edit.append(f"{word:<20} {freq}")

        self.progress_bar.setValue(100)

    def save_txt(self):
        if not self.word_counter or sum(self.word_counter.values()) == 0:
            QMessageBox.information(self, "提示", "无有效词频数据，请先提取词频。")
            return

        base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        out_path, _ = QFileDialog.getSaveFileName(self, "保存为...", base_name + "_词频统计.txt", "Text Files (*.txt)")
        if not out_path:
            return

        total_unique = len(self.word_counter)
        total_count = sum(self.word_counter.values())
        sorted_items = self.word_counter.most_common()
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"总词数：{total_count}，唯一词汇：{total_unique} 个\n\n")
                for word, freq in sorted_items:
                    f.write(f"{word:<20} {freq}\n")
            QMessageBox.information(self, "保存成功", f"词频统计结果已保存至：\n{out_path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存文件失败：{e}")

    def get_font_path(self):
        import matplotlib.font_manager as fm
        for font in ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']:
            for f in fm.fontManager.ttflist:
                if font in f.name:
                    return f.fname
        return None

    def get_zh_font(self):
        import matplotlib.font_manager as fm
        for font in ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']:
            if any(font in f.name for f in fm.fontManager.ttflist):
                return fm.FontProperties(fname=fm.findfont(font))
        return None

    def show_wordcloud(self):
        if not self.word_counter or sum(self.word_counter.values()) == 0:
            QMessageBox.information(self, "提示", "无有效词频数据，请先提取词频。")
            return

        wc = WordCloud(
            width=1000,
            height=400,
            background_color='white',
            max_words=200,
            colormap='viridis',
            prefer_horizontal=1.0,
            font_path=self.get_font_path()
        )
        wc.generate_from_frequencies(self.word_counter)

        plt.figure(figsize=(14, 6))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title("词频词云", fontsize=18, fontproperties=self.get_zh_font())
        plt.tight_layout()
        plt.show()

    def show_bar_chart(self):
        if not self.word_counter or sum(self.word_counter.values()) == 0:
            QMessageBox.information(self, "提示", "无有效词频数据，请先提取词频。")
            return

        top_items = self.word_counter.most_common(20)
        words, freqs = zip(*top_items)
        plt.figure(figsize=(12, 7))
        bars = plt.barh(words, freqs, color='#3A99D8')
        plt.xlabel("频数", fontsize=14)
        plt.title("Top 20 高频词横向条形统计", fontsize=16, fontproperties=self.get_zh_font())
        plt.gca().invert_yaxis()
        for bar in bars:
            plt.text(bar.get_width()+0.2, bar.get_y()+bar.get_height()/2, int(bar.get_width()), va='center', fontsize=12)
        plt.tight_layout()
        plt.show()

    def show_and_save_translation(self):
        if not self.word_counter or sum(self.word_counter.values()) == 0:
            QMessageBox.information(self, "提示", "请先完成词频统计！")
            return
        sorted_items = self.word_counter.most_common()
        self.trans_progress.setValue(0)
        self.trans_progress.setVisible(True)
        self.trans_button.setEnabled(False)
        self.trans_worker = TranslateWorker(sorted_items, KNOWN_WORDS)
        self.trans_worker.progress.connect(self.trans_progress.setValue)
        self.trans_worker.finished.connect(self.finish_translation)
        self.trans_worker.start()

    def finish_translation(self, lines):
        self.trans_progress.setValue(100)
        self.text_edit.clear()
        self.text_edit.append("【生词自动翻译结果】\n")
        for line in lines:
            self.text_edit.append(line)
        # 保存文件
        base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        out_path, _ = QFileDialog.getSaveFileName(self, "保存为...", base_name + "_生词翻译.txt", "Text Files (*.txt)")
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
            QMessageBox.information(self, "保存成功", f"翻译结果已保存至：\n{out_path}")
        self.trans_button.setEnabled(True)
        self.trans_progress.setVisible(False)

    def show_known_unknown_words(self):
        if not self.word_counter or sum(self.word_counter.values()) == 0:
            QMessageBox.information(self, "提示", "请先完成词频统计！")
            return

        # 拆分熟词和生词
        known_lines = []
        unknown_lines = []
        for word, freq in self.word_counter.most_common():
            line = f"{word:<20} {freq}"
            if word in KNOWN_WORDS:
                known_lines.append(line)
            else:
                unknown_lines.append(line)

        dlg = QDialog(self)
        dlg.setWindowTitle("熟词/生词 统计")
        dlg.setMinimumWidth(500)
        tabs = QTabWidget(dlg)

        known_edit = QTextEdit()
        known_edit.setReadOnly(True)
        known_edit.setPlainText("\n".join(known_lines) if known_lines else "无熟词")
        tabs.addTab(known_edit, f"熟词 ({len(known_lines)})")

        unknown_edit = QTextEdit()
        unknown_edit.setReadOnly(True)
        unknown_edit.setPlainText("\n".join(unknown_lines) if unknown_lines else "无生词")
        tabs.addTab(unknown_edit, f"生词 ({len(unknown_lines)})")

        vbox = QVBoxLayout()
        vbox.addWidget(tabs)
        dlg.setLayout(vbox)
        dlg.exec_()

# ========== 启动程序 ==========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFWordExtractor()
    window.show()
    sys.exit(app.exec_())