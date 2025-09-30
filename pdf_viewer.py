from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QScrollArea, QToolBar, QFileDialog,
    QTextEdit, QDockWidget, QMessageBox, QWidget, QHBoxLayout, QSpinBox, QPushButton, QLineEdit
)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QAction, QPainter, QColor
from PyQt6.QtCore import Qt, QEvent
import fitz  # PyMuPDF
import os
from collections import Counter

class PDFViewer(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF Редактор")
        self.pdf_path = None
        self.doc = None
        self.current_page = 0
        self.selected_word_rect = None
        self.original_pixmap = None
        self.selected_word = None
        self.debug_mode = False

        # central image view
        self.image_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMouseTracking(True)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.image_label)
        self.setCentralWidget(self.scroll)



        # toolbar
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        open_act = QAction("Відкрити", self)
        open_act.triggered.connect(self.open_file)
        toolbar.addAction(open_act)

        save_act = QAction("Зберегти", self)
        save_act.triggered.connect(self.save_document)
        toolbar.addAction(save_act)

        toolbar.addSeparator()

        prev_act = QAction("←", self)
        prev_act.triggered.connect(self.prev_page)
        toolbar.addAction(prev_act)

        next_act = QAction("→", self)
        next_act.triggered.connect(self.next_page)
        toolbar.addAction(next_act)

        self.page_spinner = QSpinBox()
        self.page_spinner.setMinimum(1)
        self.page_spinner.valueChanged.connect(self.goto_page)
        toolbar.addWidget(self.page_spinner)

        debug_act = QAction("Режим налагодження", self)
        debug_act.setCheckable(True)
        debug_act.toggled.connect(self.toggle_debug_mode)
        toolbar.addAction(debug_act)



    def toggle_debug_mode(self, checked):
        self.debug_mode = checked
        self.show_page()



    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Відкрити PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        try:
            self.doc = fitz.open(path)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося відкрити PDF:\n{e}")
            return
        self.pdf_path = path
        self.current_page = 0
        self.page_spinner.setMaximum(max(1, len(self.doc)))
        self.page_spinner.setValue(1)
        self.show_page()

    def show_page(self):
        if not self.doc:
            self.image_label.setText("Відкрийте PDF файл...")
            return
        page = self.doc[self.current_page]
        # render with scale for better quality
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        mode = QImage.Format.Format_RGB888
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, mode).copy()
        self.original_pixmap = QPixmap.fromImage(qimg)

        if self.debug_mode:
            pixmap = self.original_pixmap.copy()
            painter = QPainter(pixmap)
            words = page.get_text("words")
            for word in words:
                x0, y0, x1, y1, _ = word[:5]
                rect = fitz.Rect(x0, y0, x1, y1)
                rect.transform(mat)
                painter.setPen(QColor(255, 0, 0, 150))  # red, semi-transparent
                painter.drawRect(int(rect.x0), int(rect.y0), int(rect.width), int(rect.height))
            painter.end()
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setPixmap(self.original_pixmap)



    def prev_page(self):
        if not self.doc:
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.page_spinner.setValue(self.current_page + 1)
            self.show_page()

    def next_page(self):
        if not self.doc:
            return
        if self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.page_spinner.setValue(self.current_page + 1)
            self.show_page()

    def goto_page(self, value):
        if not self.doc:
            return
        idx = max(0, min(len(self.doc) -1, value - 1))
        self.current_page = idx
        self.show_page()



    def _get_most_common_font_properties(self, page):
        fonts = []
        sizes = []
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        fonts.append(span.get("font"))
                        sizes.append(span.get("size"))

        if not fonts:
            return "helv", 11

        font_counter = Counter(fonts)
        size_counter = Counter(sizes)

        most_common_font = font_counter.most_common(1)[0][0]
        most_common_size = size_counter.most_common(1)[0][0]

        return most_common_font, most_common_size



    def save_document(self):
        if not self.doc:
            return
        if not self.pdf_path:
            path, _ = QFileDialog.getSaveFileName(self, "Зберегти PDF як", "", "PDF Files (*.pdf)")
            if not path:
                return
            self.pdf_path = path
        try:
            # overwrite original file
            # use save to ensure all changes are written
            tmp_path = self.pdf_path + ".tmp"
            self.doc.save(tmp_path)
            # replace file atomically
            os.replace(tmp_path, self.pdf_path)
            QMessageBox.information(self, "Збережено", f"Файл збережено: {self.pdf_path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти PDF:\n{e}")

