import sys
import fitz
import json
import os
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QInputDialog, QToolBar, QComboBox, QLabel, QGraphicsLineItem, QGraphicsPixmapItem, QMessageBox
from PyQt6.QtGui import QAction, QPixmap, QColor, QPen, QResizeEvent
from PyQt6.QtCore import Qt
from logical_document import LogicalDocument

class PDFView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.parent_viewer = parent
        self.selection_rect = None
        self.selected_annot_rect = None
        self.selected_annot_page = None
        self.annot_highlight = None

        # Alignment guides
        guide_pen = QPen(QColor("green"), 1, Qt.PenStyle.SolidLine)
        self.guide_top = QGraphicsLineItem()
        self.guide_bottom = QGraphicsLineItem()
        self.guide_left = QGraphicsLineItem()
        self.guide_right = QGraphicsLineItem()
        self.guides = [self.guide_top, self.guide_bottom, self.guide_left, self.guide_right]
        for guide in self.guides:
            guide.setPen(guide_pen)
            guide.setZValue(100)
            guide.hide()
            self.scene().addItem(guide)

    def update_and_show_guides(self, rect_on_scene, page_y_start):
        offset = 2
        bottom_offset = 4 # Increased offset for the bottom guide
        scene_rect = self.scene().sceneRect()
        self.guide_top.setLine(scene_rect.left(), rect_on_scene.y0 + page_y_start + offset, scene_rect.right(), rect_on_scene.y0 + page_y_start + offset)
        self.guide_bottom.setLine(scene_rect.left(), rect_on_scene.y1 + page_y_start - bottom_offset, scene_rect.right(), rect_on_scene.y1 + page_y_start - bottom_offset)
        self.guide_left.setLine(rect_on_scene.x0 + offset, scene_rect.top(), rect_on_scene.x0 + offset, scene_rect.bottom())
        self.guide_right.setLine(rect_on_scene.x1 - offset, scene_rect.top(), rect_on_scene.x1 - offset, scene_rect.bottom())
        for guide in self.guides:
            guide.show()

    def hide_guides(self):
        for guide in self.guides:
            guide.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            zoom = self.parent_viewer.zoom_factor

            if self.parent_viewer.doc:
                # Check for annotation selection first
                page, page_y_start = self.parent_viewer.get_page_at(scene_pos.y())
                if page:
                    page_x = scene_pos.x() / zoom
                    page_y = (scene_pos.y() - page_y_start) / zoom
                    page_point = fitz.Point(page_x, page_y)

                    for annot in page.annots():
                        if page_point in annot.rect:
                            self.selected_annot_rect = annot.rect
                            self.selected_annot_page = page.number
                            if self.annot_highlight:
                                self.scene().removeItem(self.annot_highlight)
                            
                            rect_on_scene = annot.rect * zoom
                            self.annot_highlight = QGraphicsRectItem(rect_on_scene.x0, rect_on_scene.y0 + page_y_start, rect_on_scene.width, rect_on_scene.height)
                            self.annot_highlight.setPen(QPen(QColor("red")))
                            self.scene().addItem(self.annot_highlight)
                            
                            self.update_and_show_guides(rect_on_scene, page_y_start)
                            return

                # If no annotation was selected, clear selection and proceed
                if self.selected_annot_rect:
                    self.selected_annot_rect = None
                    self.selected_annot_page = None
                    self.scene().removeItem(self.annot_highlight)
                    self.annot_highlight = None
                    self.hide_guides()

                # Word selection logic
                page_num = -1
                page_y_start_word = 0
                for i in range(len(self.parent_viewer.doc)):
                    page_height = self.parent_viewer.doc[i].rect.height * zoom
                    if page_y_start_word <= scene_pos.y() < page_y_start_word + page_height:
                        page_num = i
                        break
                    page_y_start_word += page_height + 10

                if page_num == -1:
                    return

                page = self.parent_viewer.doc.load_page(page_num)
                page_pos_y = (scene_pos.y() - page_y_start_word) / zoom
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
                        word_bbox = fitz.Rect(clicked_word[:4])
                        font_name, font_size = self.parent_viewer.get_font_for_word(page, word_bbox)
                        
                        word_info = {
                            "bbox": clicked_word[:4],
                            "text": clicked_word[4],
                            "font": font_name,
                            "size": font_size
                        }
                        self.parent_viewer.edit_text_on_page(page_num, word_info, new_text)

                    if self.selection_rect:
                        self.scene().removeItem(self.selection_rect)

                    x0, y0, x1, y1, _, _, _, _ = clicked_word

                    rect = QGraphicsRectItem(x0 * zoom, y0 * zoom + page_y_start_word, (x1 - x0) * zoom, (y1 - y0) * zoom)
                    rect.setPen(QPen(QColor("yellow")))
                    rect.setBrush(QColor(255, 255, 0, 100))
                    self.selection_rect = self.scene().addRect(rect.rect(), rect.pen(), rect.brush())
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.selected_annot_rect:
            page = self.parent_viewer.doc.load_page(self.selected_annot_page)
            found_annot = None
            for annot in page.annots():
                if abs(annot.rect.x0 - self.selected_annot_rect.x0) < 0.1 and \
                   abs(annot.rect.y0 - self.selected_annot_rect.y0) < 0.1:
                    found_annot = annot
                    break
            
            if found_annot:
                move_dist = 1
                rect = found_annot.rect

                if event.key() == Qt.Key.Key_Up:
                    rect.y0 -= move_dist
                    rect.y1 -= move_dist
                elif event.key() == Qt.Key.Key_Down:
                    rect.y0 += move_dist
                    rect.y1 += move_dist
                elif event.key() == Qt.Key.Key_Left:
                    rect.x0 -= move_dist
                    rect.x1 -= move_dist
                elif event.key() == Qt.Key.Key_Right:
                    rect.x0 += move_dist
                    rect.x1 += move_dist
                elif event.key() == Qt.Key.Key_Delete:
                    page.delete_annot(found_annot)
                    self.selected_annot_rect = None
                    self.selected_annot_page = None
                    if self.annot_highlight:
                        self.scene().removeItem(self.annot_highlight)
                        self.annot_highlight = None
                    self.hide_guides()
                    self.parent_viewer.refresh_view()
                    return

                if event.key() in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right]:
                    found_annot.set_rect(rect)
                    found_annot.update()
                    self.selected_annot_rect = rect
                    
                    self.parent_viewer.refresh_view()

                    page, page_y_start = self.parent_viewer.get_page_at_num(self.selected_annot_page)
                    if page:
                        zoom = self.parent_viewer.zoom_factor
                        rect_on_scene = self.selected_annot_rect * zoom
                        
                        self.annot_highlight = QGraphicsRectItem(rect_on_scene.x0, rect_on_scene.y0 + page_y_start, rect_on_scene.width, rect_on_scene.height)
                        self.annot_highlight.setPen(QPen(QColor("red")))
                        self.scene().addItem(self.annot_highlight)

                        self.update_and_show_guides(rect_on_scene, page_y_start)

        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            scene_pos = self.mapToScene(event.pos())
            zoom = self.parent_viewer.zoom_factor

            if self.parent_viewer.doc:
                page, page_y_start = self.parent_viewer.get_page_at(scene_pos.y())
                if page:
                    page_x = scene_pos.x() / zoom
                    page_y = (scene_pos.y() - page_y_start) / zoom
                    page_point = fitz.Point(page_x, page_y)

                    for annot in page.annots():
                        if page_point in annot.rect:
                            if annot.type[0] == 2: # FreeText
                                current_text = annot.info["content"]
                                new_text, ok = QInputDialog.getText(self, "Edit Annotation", "Enter new text:", text=current_text)
                                if ok and new_text:
                                    annot.set_info(content=new_text)
                                    annot.update()
                                    self.parent_viewer.refresh_view()
                                return

        super().mouseReleaseEvent(event)

class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Editor")
        self.setGeometry(100, 100, 1200, 800)
        self.doc = None
        self.logical_doc = None
        self.session_file = "session.json"

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

        self.load_last_session()

    def load_last_session(self):
        if os.path.exists(self.session_file):
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
                last_file = session_data.get("last_file")
                if last_file and os.path.exists(last_file):
                    self._open_pdf_from_path(last_file)

    def save_session(self):
        if self.doc:
            session_data = {"last_file": self.doc.name}
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f)

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self._open_pdf_from_path(file_path)

    def _open_pdf_from_path(self, file_path):
        self.doc = fitz.open(file_path)
        self.logical_doc = LogicalDocument(self.doc)
        self.refresh_view()
        self.save_session()

    def get_page_at(self, y_coord):
        y_position = 0
        zoom = self.zoom_factor
        for page_num in range(len(self.doc)):
            page = self.doc.load_page(page_num)
            page_height = page.rect.height * zoom
            if y_position <= y_coord < y_position + page_height:
                return page, y_position
            y_position += page_height + 10
        return None, -1

    def get_page_at_num(self, page_num):
        y_position = 0
        zoom = self.zoom_factor
        for i in range(page_num):
            page = self.doc.load_page(i)
            page_height = page.rect.height * zoom
            y_position += page_height + 10
        
        page = self.doc.load_page(page_num)
        return page, y_position

    def save_pdf(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if file_path and self.doc:
            self.doc.save(file_path)

    def get_font_for_word(self, page, word_bbox):
        text_instances = page.get_text("dict")
        for block in text_instances['blocks']:
            if block.get("type") == 0: # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        span_bbox = fitz.Rect(span["bbox"])
                        if span_bbox.intersects(word_bbox):
                            return span["font"], span["size"]
        return "helv", 11  # Default fallback

    def get_font_name(self, font_string):
        if '+' in font_string:
            return font_string.split('+')[1]
        return font_string

    def edit_text_on_page(self, page_num, word_info, new_text):
        page = self.doc.load_page(page_num)

        font_name = self.get_font_name(word_info["font"])
        font_size = word_info["size"]
        word_bbox = fitz.Rect(word_info["bbox"])

        try:
            # Check if font is installed
            from matplotlib.font_manager import findfont, FontProperties
            findfont(FontProperties(family=font_name), fallback_to_default=False)
        except (ValueError, RuntimeError):
            # Font not found, show a message to the user
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText(f"Font '{font_name}' is not installed on your system.")
            msg_box.setInformativeText("Please install the font to ensure the edited text looks correct.")
            msg_box.setWindowTitle("Font Not Found")
            msg_box.exec()
            # We still proceed to add the text with a default font

        # Redact the old word
        page.add_redact_annot(word_bbox, fill=(1, 1, 1))
        page.apply_redactions()

        # Add the new word as a FreeText annotation
        page.add_freetext_annot(word_bbox, new_text, fontname=font_name, fontsize=font_size, text_color=(0, 0, 0))

        self.logical_doc.parse_document()
        self.refresh_view()

    def refresh_view(self):
        # Clear only the PDF page images (QGraphicsPixmapItem)
        for item in self.scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                self.scene.removeItem(item)

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