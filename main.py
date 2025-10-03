import sys
from PyQt6.QtWidgets import QApplication
from pdf_viewer import PDFViewer

def main():
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
