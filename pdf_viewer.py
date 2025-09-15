import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QLineEdit, QComboBox, QScrollArea, QLabel,
    QStatusBar, QSplitter, QListWidget, QListWidgetItem,
    QMessageBox, QFileDialog, QInputDialog
)
from PyQt6.QtGui import QAction, QPixmap, QIcon
from PyQt6.QtCore import Qt, QTimer
import fitz  # PyMuPDF

class PDFLabel(QLabel):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.viewer.prev_page()
        elif delta < 0:
            self.viewer.next_page()
        event.accept()


class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_pdf = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_factor = 1.0
        self.doc = None
        self.data_folder = "app_data"
        self.last_session_file = os.path.join(self.data_folder, "last_session.json")
        self.bookmarks_file = os.path.join(self.data_folder, "bookmarks.json")

        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)

        self.bookmarks = self.load_bookmarks()

        self.init_ui()
        self.apply_windows11_style()
        self.load_last_session()

    def init_ui(self):
        self.setWindowTitle("PDF Reader")
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(self.sidebar)

        sidebar_layout.addWidget(QLabel("Bookmarks"))
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.itemClicked.connect(self.bookmark_clicked)
        sidebar_layout.addWidget(self.bookmarks_list)

        self.splitter.addWidget(self.sidebar)

        self.main_area = QWidget()
        main_layout_main = QVBoxLayout(self.main_area)

        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setMovable(False)

        self.menu_action = QAction("☰", self)
        self.menu_action.triggered.connect(self.toggle_sidebar)
        self.toolbar.addAction(self.menu_action)

        self.open_action = QAction("Open", self)
        self.open_action.triggered.connect(self.open_pdf)
        self.toolbar.addAction(self.open_action)

        self.add_bookmark_action = QAction("Bookmark", self)
        self.add_bookmark_action.triggered.connect(self.add_bookmark)
        self.toolbar.addAction(self.add_bookmark_action)

        self.prev_action = QAction("◀", self)
        self.prev_action.triggered.connect(self.prev_page)
        self.toolbar.addAction(self.prev_action)

        self.page_input = QLineEdit("1 / 1")
        self.page_input.setFixedWidth(80)
        self.page_input.returnPressed.connect(self.go_to_page)
        self.toolbar.addWidget(self.page_input)

        self.next_action = QAction("▶", self)
        self.next_action.triggered.connect(self.next_page)
        self.toolbar.addAction(self.next_action)

        self.zoom_out_action = QAction("-", self)
        self.zoom_out_action.triggered.connect(self.zoom_out)
        self.toolbar.addAction(self.zoom_out_action)

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "Fit Width", "Fit Page"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self.zoom_changed)
        self.toolbar.addWidget(self.zoom_combo)

        self.zoom_in_action = QAction("+", self)
        self.zoom_in_action.triggered.connect(self.zoom_in)
        self.toolbar.addAction(self.zoom_in_action)

        self.search_action = QAction("🔍", self)
        self.search_action.triggered.connect(self.show_search)
        self.toolbar.addAction(self.search_action)

        self.scroll_area = QScrollArea()
        self.pdf_label = PDFLabel(self)
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.pdf_label)
        self.scroll_area.setWidgetResizable(True)
        main_layout_main.addWidget(self.scroll_area)

        self.splitter.addWidget(self.main_area)
        self.splitter.setSizes([200, 1000])

        self.status_bar = self.statusBar()
        self.page_label = QLabel("Page 1 of 1")
        self.status_bar.addWidget(self.page_label)
        self.zoom_label = QLabel("Zoom: 100%")
        self.status_bar.addPermanentWidget(self.zoom_label)

        self.search_widget = QLineEdit()
        self.search_widget.setPlaceholderText("Search...")
        self.search_widget.returnPressed.connect(self.search_pdf)
        self.search_widget.hide()
        main_layout_main.addWidget(self.search_widget)

        self.toast_label = QLabel("")
        self.toast_label.setStyleSheet("background-color: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 5px;")
        self.toast_label.hide()
        main_layout_main.addWidget(self.toast_label)

    def apply_windows11_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f3f3f3; border-radius: 8px; }
            QToolBar { background-color: #ffffff; border-bottom: 1px solid #e1e1e1; padding: 5px; }
            QPushButton, QComboBox, QLineEdit { border: 1px solid #cccccc; border-radius: 4px; padding: 5px; background-color: #ffffff; }
            QPushButton:hover { background-color: #e6e6e6; }
            QListWidget { background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px; }
            QStatusBar { background-color: #ffffff; border-top: 1px solid #e1e1e1; }
        """)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, file_path, page_number=0):
        try:
            self.doc = fitz.open(file_path)
            self.total_pages = len(self.doc)
            self.current_pdf = file_path
            self.setWindowTitle(f"{os.path.basename(file_path)} - PDF Reader")
            self.current_page = page_number
            
            self.update_bookmarks()
            self.display_page()
            self.update_ui()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open PDF: {str(e)}")

    def display_page(self):
        if self.doc and 0 <= self.current_page < self.total_pages:
            page = self.doc[self.current_page]
            zoom_text = self.zoom_combo.currentText()
            if zoom_text == "Fit Width":
                zoom = self.scroll_area.width() / page.rect.width
            elif zoom_text == "Fit Page":
                zoom = min(self.scroll_area.width() / page.rect.width, self.scroll_area.height() / page.rect.height)
            else:
                zoom = float(zoom_text.strip('%')) / 100.0

            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)
            img = QPixmap()
            img.loadFromData(pix.tobytes("png"))
            self.pdf_label.setPixmap(img)
            self.save_last_session()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()
            self.update_ui()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_page()
            self.update_ui()

    def go_to_page(self):
        try:
            page_num = int(self.page_input.text().split('/')[0].strip()) - 1
            if 0 <= page_num < self.total_pages:
                self.current_page = page_num
                self.display_page()
                self.update_ui()
        except ValueError:
            pass

    def zoom_in(self):
        current_zoom = self.zoom_combo.currentText()
        if "%" in current_zoom:
            zoom_value = min(int(current_zoom.strip('%')) + 25, 200)
            self.zoom_combo.setCurrentText(f"{zoom_value}%")
            self.display_page()

    def zoom_out(self):
        current_zoom = self.zoom_combo.currentText()
        if "%" in current_zoom:
            zoom_value = max(int(current_zoom.strip('%')) - 25, 50)
            self.zoom_combo.setCurrentText(f"{zoom_value}%")
            self.display_page()

    def zoom_changed(self):
        self.display_page()
        self.update_zoom_label()

    def update_ui(self):
        self.page_input.setText(f"{self.current_page + 1} / {self.total_pages}")
        self.page_label.setText(f"Page {self.current_page + 1} of {self.total_pages}")
        self.prev_action.setEnabled(self.current_page > 0)
        self.next_action.setEnabled(self.current_page < self.total_pages - 1)

    def update_zoom_label(self):
        self.zoom_label.setText(f"Zoom: {self.zoom_combo.currentText()}")

    def show_search(self):
        self.search_widget.setVisible(not self.search_widget.isVisible())
        if self.search_widget.isVisible():
            self.search_widget.setFocus()

    def search_pdf(self):
        query = self.search_widget.text()
        if self.doc and query:
            for page_num in range(self.total_pages):
                page = self.doc[page_num]
                if query.lower() in page.get_text().lower():
                    self.current_page = page_num
                    self.display_page()
                    self.update_ui()
                    self.show_toast(f"Found on page {page_num + 1}")
                    return
            self.show_toast("Text not found")

    def show_toast(self, message):
        self.toast_label.setText(message)
        self.toast_label.show()
        QTimer.singleShot(3000, self.toast_label.hide)

    def save_last_session(self):
        if self.current_pdf:
            session_data = {
                "last_opened_pdf": self.current_pdf,
                "last_opened_page": self.current_page
            }
            with open(self.last_session_file, "w") as f:
                json.dump(session_data, f)

    def load_last_session(self):
        try:
            with open(self.last_session_file, "r") as f:
                session_data = json.load(f)
                pdf_path = session_data.get("last_opened_pdf")
                page = session_data.get("last_opened_page", 0)
                if pdf_path and os.path.exists(pdf_path):
                    self.load_pdf(pdf_path, page)
                    self.show_toast(f"Resumed from last session: Page {page + 1}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def add_bookmark(self):
        if self.current_pdf:
            text, ok = QInputDialog.getText(self, 'Add Bookmark', 'Enter bookmark name:')
            if ok and text:
                if self.current_pdf not in self.bookmarks:
                    self.bookmarks[self.current_pdf] = []
                self.bookmarks[self.current_pdf].append({"page": self.current_page, "name": text})
                self.save_bookmarks()
                self.update_bookmarks()

    def save_bookmarks(self):
        with open(self.bookmarks_file, "w") as f:
            json.dump(self.bookmarks, f)

    def load_bookmarks(self):
        try:
            with open(self.bookmarks_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def update_bookmarks(self):
        self.bookmarks_list.clear()
        if self.current_pdf in self.bookmarks:
            for bookmark in self.bookmarks[self.current_pdf]:
                item = QListWidgetItem(f"{bookmark['name']} (Page {bookmark['page'] + 1})")
                item.setData(Qt.ItemDataRole.UserRole, bookmark['page'])
                self.bookmarks_list.addItem(item)

    def bookmark_clicked(self, item):
        page_num = item.data(Qt.ItemDataRole.UserRole)
        self.current_page = page_num
        self.display_page()
        self.update_ui()

    def closeEvent(self, event):
        self.save_last_session()
        event.accept()
