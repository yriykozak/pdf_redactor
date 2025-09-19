import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImageReader
from pdf_viewer import PDFViewer

if __name__ == "__main__":
    QImageReader.setAllocationLimit(1024)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for better customization
    viewer = PDFViewer()
    viewer.showMaximized()
    sys.exit(app.exec())
















    