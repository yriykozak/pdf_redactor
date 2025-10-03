import sys
import fitz
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QInputDialog, QToolBar, QComboBox, QLabel
from PyQt6.QtGui import QAction, QPixmap, QColor, QPen, QResizeEvent
from PyQt6.QtCore import Qt
from logical_document import LogicalDocument

class PDFView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.parent_viewer = parent
        self.selection_rect = None

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.pos())

        if self.parent_viewer.logical_doc:
            page_num = -1
            page_y_start = 0
            zoom = self.parent_viewer.zoom_factor

            for i in range(len(self.parent_viewer.doc)):
                page_height = self.parent_viewer.doc[i].rect.height * zoom
                if page_y_start <= scene_pos.y() < page_y_start + page_height:
                    page_num = i
                    break
                page_y_start += page_height + 10

            if page_num == -1:
                return

            page_pos_y = (scene_pos.y() - page_y_start) / zoom
            page_pos_x = scene_pos.x() / zoom

            page_words = self.parent_viewer.logical_doc.get_page_words(page_num)
            clicked_word = None
            for word in page_words:
                x0, y0, x1, y1, text, _, _, _ = word
                if x0 <= page_pos_x < x1 and y0 <= page_pos_y < y1:
                    clicked_word = word
                    break

            if clicked_word:
                new_text, ok = QInputDialog.getText(self, "Edit Word", "Enter new text:", text=clicked_word[4])

                if ok and new_text:
                    self.parent_viewer.edit_text_on_page(page_num, clicked_word, new_text)

                if self.selection_rect:
                    self.scene().removeItem(self.selection_rect)

                x0, y0, x1, y1, _, _, _, _ = clicked_word

                rect = QGraphicsRectItem(x0 * zoom, y0 * zoom + page_y_start, (x1 - x0) * zoom, (y1 - y0) * zoom)
                rect.setPen(QPen(QColor("yellow")))
                rect.setBrush(QColor(255, 255, 0, 100))
                self.selection_rect = self.scene().addRect(rect.rect(), rect.pen(), rect.brush())


class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Editor")
        self.setGeometry(100, 100, 1200, 800)
        self.doc = None
        self.logical_doc = None

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_pdf)
        file_menu.addAction(open_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self.save_pdf)
        file_menu.addAction(save_as_action)

        self.zoom_factor = 1.0
        self.fit_mode = None  # Can be 'width', 'page', or None

        toolbar = QToolBar("Zoom Toolbar")
        self.addToolBar(toolbar)

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.addItems([
            "25%", "50%", "75%", "100%", "125%", "150%", "200%", "400%"
        ])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.lineEdit().returnPressed.connect(self.handle_zoom_change)
        self.zoom_combo.activated.connect(self.handle_zoom_change)
        toolbar.addWidget(QLabel("Zoom:"))
        toolbar.addWidget(self.zoom_combo)

        fit_width_action = QAction("Fit Width", self)
        fit_width_action.triggered.connect(self.fit_width)
        toolbar.addAction(fit_width_action)

        fit_page_action = QAction("Fit Page", self)
        fit_page_action.triggered.connect(self.fit_page)
        toolbar.addAction(fit_page_action)

        self.scene = QGraphicsScene()
        self.view = PDFView(self.scene, self)
        self.setCentralWidget(self.view)

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.doc = fitz.open(file_path)
            self.logical_doc = LogicalDocument(self.doc)
            self.refresh_view()

    def save_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if file_path and self.doc:
            self.doc.save(file_path)

    def edit_text_on_page(self, page_num, word_info, new_text):
        page = self.doc.load_page(page_num)
        
        x0, y0, x1, y1, _, _, _, _ = word_info
        word_bbox = fitz.Rect(x0, y0, x1, y1)
        
        page.add_redact_annot(word_bbox)
        page.apply_redactions()
        
        page.insert_text((x0, y1), new_text, fontname="helv", fontsize=11)
        
        self.logical_doc.parse_document() # Re-parse to update the logical model
        self.refresh_view()

    def refresh_view(self):
        self.scene.clear()
        self.view.selection_rect = None
        if not self.doc:
            return

        y_position = 0
        for page_num in range(len(self.doc)):
            page = self.doc.load_page(page_num)
            mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
            pix = page.get_pixmap(matrix=mat)
            pixmap = QPixmap()
            pixmap.loadFromData(pix.tobytes("ppm"))

            item = self.scene.addPixmap(pixmap)
            item.setPos(0, y_position)
            y_position += pix.height + 10

    def handle_zoom_change(self):
        zoom_text = self.zoom_combo.currentText().replace("%", "").strip()
        try:
            zoom_value = float(zoom_text) / 100.0
            self.zoom_factor = zoom_value
            self.fit_mode = None
            self.refresh_view()
        except ValueError:
            # Handle invalid input if necessary
            pass

    def fit_width(self):
        if not self.doc:
            return
        page = self.doc.load_page(0)
        self.zoom_factor = self.view.viewport().width() / page.rect.width
        self.fit_mode = 'width'
        self.zoom_combo.setCurrentText(f"{self.zoom_factor * 100:.2f}%")
        self.refresh_view()

    def fit_page(self):
        if not self.doc:
            return
        page = self.doc.load_page(0)
        zoom_x = self.view.viewport().width() / page.rect.width
        zoom_y = self.view.viewport().height() / page.rect.height
        self.zoom_factor = min(zoom_x, zoom_y)
        self.fit_mode = 'page'
        self.zoom_combo.setCurrentText(f"{self.zoom_factor * 100:.2f}%")
        self.refresh_view()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self.fit_mode == 'width':
            self.fit_width()
        elif self.fit_mode == 'page':
            self.fit_page()