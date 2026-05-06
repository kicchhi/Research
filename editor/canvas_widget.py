from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QBrush, QPen, QColor, QFont

class CellItem(QGraphicsRectItem):
    """Одна ячейка схемы"""
    def __init__(self, row, col, size, color, symbol=""):
        super().__init__(0, 0, size, size)
        self.row = row
        self.col = col
        self.size = size
        self.setBrush(QBrush(QColor(*color)))
        self.setPen(QPen(Qt.gray, 0.5))
        
        self.text_item = QGraphicsTextItem(symbol, self)
        self.update_text_style(color)
        self.center_text()
    
    def update_text_style(self, color):
        brightness = color[0] + color[1] + color[2]
        self.text_item.setDefaultTextColor(Qt.black if brightness > 382 else Qt.white)
        font = QFont("Courier", self.size // 2, QFont.Bold)
        self.text_item.setFont(font)
    
    def center_text(self):
        rect = self.text_item.boundingRect()
        self.text_item.setPos(self.size//2 - rect.width()//2, self.size//2 - rect.height()//2)
    
    def set_cell_color(self, color):
        self.setBrush(QBrush(QColor(*color)))
        self.update_text_style(color)
    
    def set_symbol(self, symbol):
        self.text_item.setPlainText(symbol)
        self.center_text()


class CrossStitchCanvas(QGraphicsView):
    """Холст для отображения схемы вышивки"""
    
    cell_clicked = Signal(int, int)  # row, col
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.cell_items = []
        self.rows = 0
        self.cols = 0
        self.cell_size = 35
        
        # Данные (для undo/redo)
        self.rgb_matrix = []
        self.symbol_matrix = []
        self.palette = {}
        
        self.zoom_factor = 1.1
        self.min_zoom = 0.2
        self.max_zoom = 5.0
        
        self.highlighted_cells = set()

        self.is_drawing = False
    
    def load_scheme(self, rgb_matrix, symbol_matrix):
        """Загружает схему из матриц"""
        self.scene.clear()
        self.cell_items = []
        self.rows = len(rgb_matrix)
        self.cols = len(rgb_matrix[0]) if self.rows > 0 else 0
        self.rgb_matrix = rgb_matrix
        self.symbol_matrix = symbol_matrix
        
        for i in range(self.rows):
            row_items = []
            for j in range(self.cols):
                color = rgb_matrix[i][j]
                symbol = symbol_matrix[i][j] if symbol_matrix and i < len(symbol_matrix) else ""
                item = CellItem(i, j, self.cell_size, color, str(symbol))
                item.setPos(j * self.cell_size, i * self.cell_size)
                self.scene.addItem(item)
                row_items.append(item)
            self.cell_items.append(row_items)
        
        self.scene.setSceneRect(0, 0, self.cols * self.cell_size, self.rows * self.cell_size)
        self.apply_highlight()
    
    def apply_highlight(self):
        """Применяет подсветку ячеек"""
        for i in range(self.rows):
            for j in range(self.cols):
                item = self.cell_items[i][j]
                if (i, j) in self.highlighted_cells:
                    item.setPen(QPen(QColor("#FFD700"), 3))
                else:
                    item.setPen(QPen(Qt.gray, 0.5))
    
    def highlight_cells_by_symbol(self, symbol):
        """Подсветить все ячейки с указанным символом"""
        self.highlighted_cells.clear()
        for i in range(self.rows):
            for j in range(self.cols):
                if self.symbol_matrix[i][j] == symbol:
                    self.highlighted_cells.add((i, j))
        self.apply_highlight()
    
    def clear_highlight(self):
        """Снять подсветку"""
        self.highlighted_cells.clear()
        self.apply_highlight()
    
    def set_cell_color(self, row, col, color, update_data=True):
        """Меняет цвет ячейки"""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.cell_items[row][col].set_cell_color(color)
            if update_data:
                self.rgb_matrix[row][col] = list(color)
    
    def get_cell_color(self, row, col):
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return tuple(self.rgb_matrix[row][col])
        return (0, 0, 0)
    
    def set_cell_symbol(self, row, col, symbol, update_data=True):
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.cell_items[row][col].set_symbol(symbol)
            if update_data:
                self.symbol_matrix[row][col] = symbol
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            scene_pos = self.mapToScene(pos)
            col = int(scene_pos.x() // self.cell_size)
            row = int(scene_pos.y() // self.cell_size)
            if 0 <= row < self.rows and 0 <= col < self.cols:
                self.is_drawing = True  # флаг для рисования
                self.last_row = row
                self.last_col = col
                self.cell_clicked.emit(row, col)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_drawing and (event.buttons() & Qt.LeftButton):
            pos = event.pos()
            scene_pos = self.mapToScene(pos)
            col = int(scene_pos.x() // self.cell_size)
            row = int(scene_pos.y() // self.cell_size)
            if 0 <= row < self.rows and 0 <= col < self.cols:
                # Проверяем, не та же ли ячейка
                if row != self.last_row or col != self.last_col:
                    self.last_row = row
                    self.last_col = col
                    self.cell_clicked.emit(row, col)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_drawing = False
        super().mouseReleaseEvent(event)

    
    def wheelEvent(self, event):
        zoom = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
        new_zoom = self.transform().m11() * zoom
        if self.min_zoom <= new_zoom <= self.max_zoom:
            self.scale(zoom, zoom)
    
    def zoom_in(self):
        new_zoom = self.transform().m11() * self.zoom_factor
        if new_zoom <= self.max_zoom:
            self.scale(self.zoom_factor, self.zoom_factor)
    
    def zoom_out(self):
        new_zoom = self.transform().m11() / self.zoom_factor
        if new_zoom >= self.min_zoom:
            self.scale(1 / self.zoom_factor, 1 / self.zoom_factor)
    
    def zoom_reset(self):
        self.resetTransform()
    
    def export_png(self, filepath):
        """Экспорт в PNG"""
        from PySide6.QtGui import QImage, QPainter
        
        size = self.cell_size
        image = QImage(self.cols * size, self.rows * size, QImage.Format_RGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        
        for i in range(self.rows):
            for j in range(self.cols):
                x = j * size
                y = i * size
                color = self.rgb_matrix[i][j]
                painter.fillRect(x, y, size, size, QColor(*color))
                
                symbol = self.symbol_matrix[i][j] if self.symbol_matrix else ""
                if symbol and symbol != " ":
                    painter.setPen(Qt.black if (color[0]+color[1]+color[2]) > 382 else Qt.white)
                    font = painter.font()
                    font.setPointSize(size // 2)
                    painter.setFont(font)
                    painter.drawText(x + size//3, y + size//1.5, symbol)
        
        painter.end()
        image.save(filepath)

    def highlight_cells_by_color(self, color):
        """Подсветить все ячейки с указанным цветом"""
        self.highlighted_cells.clear()
        for i in range(self.rows):
            for j in range(self.cols):
                if tuple(self.rgb_matrix[i][j]) == color:
                    self.highlighted_cells.add((i, j))
        self.apply_highlight()

    def clear_highlight(self):
        """Снять подсветку"""
        self.highlighted_cells.clear()
        self.apply_highlight()