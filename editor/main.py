import sys
from PySide6.QtWidgets import QApplication
from main_window import CrossStitchWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Устанавливаем стиль (можно Fusion или Windows)
    app.setStyle("Fusion")
    
    # Тёмная палитра (как у тебя было)
    app.setPalette(app.style().standardPalette())
    
    window = CrossStitchWindow()
    window.show()
    sys.exit(app.exec())