import json
import copy
import sys
from collections import defaultdict

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QColorDialog, QPushButton, QLabel, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QApplication, QInputDialog,
    QListWidgetItem
)
from PySide6.QtWidgets import QMenu
# from PySide6.QtCore import Qt, Signal, QUndoStack, QUndoCommand
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack, QUndoCommand
from PySide6.QtGui import QAction, QKeySequence, QColor
from canvas_widget import CrossStitchCanvas


# ============================================
# КОМАНДЫ ДЛЯ UNDO/REDO
# ============================================

class ChangeCellColorCommand(QUndoCommand):
    """Команда изменения цвета ячейки"""
    def __init__(self, canvas, row, col, old_color, new_color, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.row = row
        self.col = col
        self.old_color = old_color
        self.new_color = new_color
        self.setText(f"Изменить цвет ячейки [{row}, {col}]")
    
    def undo(self):
        self.canvas.set_cell_color(self.row, self.col, self.old_color, update_data=True)
    
    def redo(self):
        self.canvas.set_cell_color(self.row, self.col, self.new_color, update_data=True)


class FloodFillCommand(QUndoCommand):
    """Команда заливки"""
    def __init__(self, canvas, rgb_matrix, symbol_matrix, palette, 
                 old_state, new_state, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.old_rgb = copy.deepcopy(old_state['rgb_matrix'])
        self.new_rgb = copy.deepcopy(new_state['rgb_matrix'])
        self.old_symbol = copy.deepcopy(old_state['symbol_matrix'])
        self.new_symbol = copy.deepcopy(new_state['symbol_matrix'])
        self.old_palette = copy.deepcopy(old_state['palette'])
        self.new_palette = copy.deepcopy(new_state['palette'])
        self.setText("Заливка")
    
    def undo(self):
        self.restore_state(self.old_rgb, self.old_symbol, self.old_palette)
    
    def redo(self):
        self.restore_state(self.new_rgb, self.new_symbol, self.new_palette)
    
    def restore_state(self, rgb, symbol, palette):
        self.canvas.rgb_matrix = copy.deepcopy(rgb)
        self.canvas.symbol_matrix = copy.deepcopy(symbol)
        self.canvas.palette = copy.deepcopy(palette)
        self.canvas.load_scheme(self.canvas.rgb_matrix, self.canvas.symbol_matrix)
        if hasattr(self.canvas.parent(), 'update_palette_display'):
            self.canvas.parent().update_palette_display()


class ChangeSymbolCommand(QUndoCommand):
    """Команда изменения символа ячейки"""
    def __init__(self, canvas, row, col, old_symbol, new_symbol, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.row = row
        self.col = col
        self.old_symbol = old_symbol
        self.new_symbol = new_symbol
        self.setText(f"Изменить символ [{row}, {col}] на '{new_symbol}'")
    
    def undo(self):
        self.canvas.set_cell_symbol(self.row, self.col, self.old_symbol, update_data=True)
    
    def redo(self):
        self.canvas.set_cell_symbol(self.row, self.col, self.new_symbol, update_data=True)


class ReplaceColorCommand(QUndoCommand):
    """Команда замены цвета во всей схеме"""
    def __init__(self, canvas, symbol, old_color, new_color, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.symbol = symbol
        self.old_color = old_color
        self.new_color = new_color
        self.setText(f"Заменить цвет '{symbol}'")
    
    def undo(self):
        self.apply_color(self.old_color)
    
    def redo(self):
        self.apply_color(self.new_color)
    
    def apply_color(self, color):
        for i in range(self.canvas.rows):
            for j in range(self.canvas.cols):
                if self.canvas.symbol_matrix[i][j] == self.symbol:
                    self.canvas.set_cell_color(i, j, color, update_data=False)
        self.canvas.palette[self.symbol] = color
        self.canvas.load_scheme(self.canvas.rgb_matrix, self.canvas.symbol_matrix)
        if hasattr(self.canvas.parent(), 'update_palette_display'):
            self.canvas.parent().update_palette_display()


# ============================================
# ГЛАВНОЕ ОКНО
# ============================================

class CrossStitchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CrossStitch Pro - Редактор схем вышивки")
        self.setGeometry(100, 100, 1400, 900)
        
        # Данные
        self.rgb_matrix = []
        self.symbol_matrix = []
        self.palette = {}
        self.rows = 0
        self.cols = 0
        self.current_color = (255, 0, 0)  # красный
        self.current_symbol = "A"
        self.current_tool = "brush"  # brush, eyedropper, eraser, fill, text, hand
        
        # История
        self.undo_stack = QUndoStack(self)
        
        # Подсветка
        self.highlighted_cells = set()
        
        # === ЦЕНТРАЛЬНЫЙ ХОЛСТ ===
        self.canvas = CrossStitchCanvas(self)
        self.setCentralWidget(self.canvas)
        
        # === ЛЕВАЯ ПАНЕЛЬ (ИНСТРУМЕНТЫ) ===
        self.create_toolbar_dock()
        
        # === ПРАВАЯ ПАНЕЛЬ (ПАЛИТРА) ===
        self.create_palette_dock()
        
        # === ПРАВАЯ ПАНЕЛЬ (ИСТОРИЯ) ===
        self.create_history_dock()
        
        # === НИЖНЯЯ ПАНЕЛЬ (БЫСТРЫЕ ЦВЕТА И СИМВОЛЫ) ===
        self.create_bottom_bar()
        
        # === ВЕРХНЕЕ МЕНЮ ===
        self.create_menu()
        
        # === СТАТУС БАР ===
        self.statusBar().showMessage("Готов")
        
        # === ПОДКЛЮЧАЕМ СИГНАЛЫ ХОЛСТА ===
        self.canvas.cell_clicked.connect(self.on_cell_clicked)
        
        # === ПРИМЕНЯЕМ СТИЛЬ ===
        self.apply_styles()
    
    def apply_styles(self):
        """Применяем тёмную тему"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QDockWidget::title {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 5px;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #0078d4;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
    
    def create_toolbar_dock(self):
        """Левая панель с инструментами"""
        dock = QDockWidget("Инструменты", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Кнопки инструментов
        self.tool_buttons = {}
        tools = [
            ("🖐️ Рука", "hand", "H"),
            ("🖌️ Кисть", "brush", "B"),
            ("💧 Пипетка", "eyedropper", "I"),
            ("🧽 Ластик", "eraser", "E"),
            ("🪣 Заливка", "fill", "F"),
            ("🔤 Текст", "text", "T"),
        ]
        
        for text, tool, shortcut in tools:
            btn = QPushButton(f"{text} ({shortcut})")
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda checked, t=tool: self.set_tool(t))
            layout.addWidget(btn)
            self.tool_buttons[tool] = btn
        
        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #3d3d3d;")
        layout.addWidget(line)
        
        # Текущий цвет
        self.color_label = QLabel("Текущий цвет:")
        layout.addWidget(self.color_label)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(50, 50)
        self.color_preview.setStyleSheet(f"background-color: rgb(255, 0, 0); border-radius: 4px;")
        layout.addWidget(self.color_preview)
        
        choose_color_btn = QPushButton("Выбрать цвет")
        choose_color_btn.clicked.connect(self.choose_color)
        layout.addWidget(choose_color_btn)
        
        # Текущий символ
        layout.addWidget(QLabel("Текущий символ:"))
        self.symbol_entry = QPushButton("A")
        self.symbol_entry.setFixedSize(50, 50)
        self.symbol_entry.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.symbol_entry.clicked.connect(self.edit_current_symbol)
        layout.addWidget(self.symbol_entry)
        
        layout.addStretch()
        dock.setWidget(widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
    
    def create_palette_dock(self):
        """Правая панель с палитрой цветов"""
        dock = QDockWidget("Палитра", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Кнопка "Снять подсветку"
        clear_highlight_btn = QPushButton("✖ Снять подсветку")
        clear_highlight_btn.clicked.connect(self.clear_highlight)
        layout.addWidget(clear_highlight_btn)
        
        # Список палитры
        self.palette_list = QListWidget()
        self.palette_list.itemClicked.connect(self.on_palette_click)
        layout.addWidget(self.palette_list)

            # Контекстное меню для палитры
        self.palette_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.palette_list.customContextMenuRequested.connect(self.show_palette_context_menu)
        
        dock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def show_palette_context_menu(self, position):
        """Контекстное меню для палитры"""
        item = self.palette_list.itemAt(position)
        if not item:
            return
        
        symbol = item.data(Qt.UserRole)
        if not symbol:
            text = item.text()
            if text:
                symbol = text.split()[0].replace("🔒", "").replace("🔓", "").strip()
        
        if not symbol or symbol not in self.palette:
            return
        
        menu = QMenu(self)
        
        replace_color_action = menu.addAction("🎨 Заменить цвет")
        replace_symbol_action = menu.addAction("🔤 Заменить символ")
        replace_both_action = menu.addAction("🔄 Заменить цвет и символ")
        menu.addSeparator()
        select_action = menu.addAction("✅ Выбрать цвет для кисти")
        
        action = menu.exec(self.palette_list.mapToGlobal(position))
        
        if action == replace_color_action:
            self.replace_all_cells_by_symbol(symbol, new_symbol=symbol)
        elif action == replace_symbol_action:
            self.replace_all_cells_by_symbol(symbol, new_color=self.palette[symbol])
        elif action == replace_both_action:
            self.replace_all_cells_by_symbol(symbol)
        elif action == select_action:
            self.current_color = self.palette[symbol]
            self.update_color_preview()
            self.set_tool("brush")
            self.highlight_cells_by_symbol(symbol)
    
    def create_history_dock(self):
        """Правая панель с историей (красивые плашки)"""
        dock = QDockWidget("История", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        dock.setMinimumWidth(280)
        
        # Контейнер для списка истории
        history_container = QWidget()
        history_layout = QVBoxLayout(history_container)
        history_layout.setContentsMargins(5, 5, 5, 5)
        history_layout.setSpacing(5)
        
        # Скролл-область для истории
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2d2d2d;
            }
        """)
        
        # Виджет для списка действий
        self.history_widget = QWidget()
        self.history_layout_inner = QVBoxLayout(self.history_widget)
        self.history_layout_inner.setContentsMargins(5, 5, 5, 5)
        self.history_layout_inner.setSpacing(5)
        self.history_layout_inner.addStretch()
        
        scroll_area.setWidget(self.history_widget)
        history_layout.addWidget(scroll_area)
        
        # Кнопка очистки истории
        clear_btn = QPushButton("🗑️ Очистить историю")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        clear_btn.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_btn)
        
        dock.setWidget(history_container)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        
        # Обновляем список истории при изменении
        self.undo_stack.indexChanged.connect(self.update_history_display)
    
    def create_bottom_bar(self):
        """Нижняя панель с быстрыми цветами и символами"""
        bottom_widget = QWidget()
        bottom_widget.setFixedHeight(70)
        layout = QHBoxLayout(bottom_widget)
        
        # Быстрые цвета
        quick_colors = [
            ("#FF0000", "Красный"), ("#00FF00", "Зеленый"), ("#0000FF", "Синий"),
            ("#FFFF00", "Желтый"), ("#FF00FF", "Пурпурный"), ("#00FFFF", "Голубой"),
            ("#FFA500", "Оранжевый"), ("#800080", "Фиолетовый"), ("#FFFFFF", "Белый"),
            ("#000000", "Черный")
        ]
        
        layout.addWidget(QLabel("Быстрые цвета:"))
        for hex_color, name in quick_colors:
            btn = QPushButton()
            btn.setFixedSize(30, 30)
            btn.setStyleSheet(f"background-color: {hex_color}; border-radius: 4px;")
            btn.clicked.connect(lambda checked, c=hex_color: self.set_color_from_hex(c))
            layout.addWidget(btn)
        
        layout.addSpacing(30)
        
        # Быстрые символы
        layout.addWidget(QLabel("Символы:"))
        quick_symbols = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        for sym in quick_symbols[:20]:  # первые 20 для экономии места
            btn = QPushButton(sym)
            btn.setFixedSize(35, 35)
            btn.setStyleSheet("font-size: 14px; font-weight: bold;")
            btn.clicked.connect(lambda checked, s=sym: self.set_current_symbol(s))
            layout.addWidget(btn)
        
        layout.addStretch()
        self.statusBar().addPermanentWidget(bottom_widget)
    
    def create_menu(self):
        """Верхнее меню"""
        menubar = self.menuBar()
        
        # Файл
        file_menu = menubar.addMenu("Файл")
        file_menu.addAction("Открыть JSON", self.load_json).setShortcut("Ctrl+O")
        file_menu.addAction("Сохранить JSON", self.save_json).setShortcut("Ctrl+S")
        file_menu.addSeparator()
        file_menu.addAction("Выход", self.close).setShortcut("Ctrl+Q")
        
        # Правка
        edit_menu = menubar.addMenu("Правка")
        edit_menu.addAction("Отменить", self.undo).setShortcut("Ctrl+Z")
        edit_menu.addAction("Повторить", self.redo).setShortcut("Ctrl+Y")
        
        # Вид
        view_menu = menubar.addMenu("Вид")
        view_menu.addAction("Увеличить", self.zoom_in).setShortcut("Ctrl++")
        view_menu.addAction("Уменьшить", self.zoom_out).setShortcut("Ctrl+-")
        view_menu.addAction("Сбросить масштаб", self.zoom_reset).setShortcut("Ctrl+0")
        
        # Схема
        scheme_menu = menubar.addMenu("Схема")
        scheme_menu.addAction("Статистика", self.show_stats)
    
    # ============================================
    # ИНСТРУМЕНТЫ И ДЕЙСТВИЯ
    # ============================================
    
    def set_tool(self, tool):
        self.current_tool = tool
        for t, btn in self.tool_buttons.items():
            btn.setStyleSheet("")
        if tool in self.tool_buttons:
            self.tool_buttons[tool].setStyleSheet("background-color: #0078d4;")
        self.update_cursor()
        self.statusBar().showMessage(f"Инструмент: {tool}")
    
    def set_current_symbol(self, symbol):
        self.current_symbol = symbol
        self.symbol_entry.setText(symbol)
    
    def edit_current_symbol(self):
        """Редактирование текущего символа"""
        dialog = QColorDialog(self)
        symbol, ok = QInputDialog.getText(self, "Символ", "Введи символ:", text=self.current_symbol)
        if ok and symbol:
            self.set_current_symbol(symbol)
    
    def set_color_from_hex(self, hex_color):
        hex_color = hex_color.lstrip('#')
        self.current_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        self.update_color_preview()
    
    def choose_color(self):
        color = QColorDialog.getColor(QColor(*self.current_color), self, "Выбери цвет")
        if color.isValid():
            self.current_color = (color.red(), color.green(), color.blue())
            self.update_color_preview()
    
    def update_color_preview(self):
        hex_color = f'rgb({self.current_color[0]}, {self.current_color[1]}, {self.current_color[2]})'
        self.color_preview.setStyleSheet(f"background-color: {hex_color}; border-radius: 4px;")

    def sort_colors_by_hue(self, colors_with_counts):
        """
        Сортирует цвета по оттенку (hue) для красивого отображения в палитре
        
        colors_with_counts: список кортежей (color, count)
        возвращает: отсортированный список
        """
        import math
        
        def rgb_to_hue(rgb):
            """Конвертирует RGB в оттенок (hue) от 0 до 360"""
            r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            
            if max_c == min_c:
                return 0
            
            if max_c == r:
                hue = 60 * ((g - b) / (max_c - min_c))
            elif max_c == g:
                hue = 60 * (2 + (b - r) / (max_c - min_c))
            else:
                hue = 60 * (4 + (r - g) / (max_c - min_c))
            
            if hue < 0:
                hue += 360
            
            return hue
        
        # Добавляем оттенок к каждому цвету
        colors_with_hue = []
        for color, count in colors_with_counts:
            hue = rgb_to_hue(color)
            # Также считаем яркость для вторичной сортировки
            brightness = (color[0] + color[1] + color[2]) / 3
            colors_with_hue.append((color, count, hue, brightness))
        
        # Сортируем сначала по оттенку, потом по яркости
        colors_with_hue.sort(key=lambda x: (x[2], x[3]))
        
        return [(c[0], c[1]) for c in colors_with_hue]
    
    def update_palette_display(self):
        """Обновление палитры — цвета отсортированы по оттенку"""
        self.palette_list.clear()
        
        if not self.palette:
            empty_label = QLabel("Нет палитры\nЗагрузите JSON схему")
            empty_label.setStyleSheet("color: #888888; padding: 20px;")
            empty_label.setAlignment(Qt.AlignCenter)
            
            item = QListWidgetItem(self.palette_list)
            item.setSizeHint(empty_label.sizeHint())
            self.palette_list.setItemWidget(item, empty_label)
            return
        
        # Считаем количество крестиков для каждого цвета из rgb_matrix
        color_counts = {}
        for i in range(self.rows):
            for j in range(self.cols):
                color = tuple(self.rgb_matrix[i][j])
                color_counts[color] = color_counts.get(color, 0) + 1
        
        # Собираем список цветов для сортировки
        colors_to_sort = []
        for key, color in self.palette.items():
            count = color_counts.get(color, 0)
            colors_to_sort.append((color, count))
        
        # Сортируем по оттенку (красиво!)
        sorted_colors = self.sort_colors_by_hue(colors_to_sort)
        
        total_cells = self.rows * self.cols
        colors_used = len(color_counts)
        
        # Добавляем заголовок с общей информацией
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_label = QLabel(f"📊 Всего цветов: {colors_used}  |  Ячеек: {total_cells}")
        header_label.setStyleSheet("color: #888888; font-size: 10px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        header_item = QListWidgetItem(self.palette_list)
        header_item.setSizeHint(header_widget.sizeHint())
        self.palette_list.setItemWidget(header_item, header_widget)
        
        # Отображаем каждый цвет (уже отсортированный)
        for color, count in sorted_colors:
            hex_color = f'#{color[0]:02x}{color[1]:02x}{color[2]:02x}'
            
            # Находим ключ (символ или временное имя)
            key = None
            for k, v in self.palette.items():
                if v == color:
                    key = k
                    break
            
            # Создаём виджет для цвета
            item_widget = QWidget()
            layout = QHBoxLayout(item_widget)
            layout.setContentsMargins(5, 2, 5, 2)
            
            # Цветной прямоугольник
            color_box = QLabel()
            color_box.setFixedSize(30, 30)
            color_box.setStyleSheet(f"background-color: {hex_color}; border-radius: 4px; border: 1px solid #555;")
            layout.addWidget(color_box)
            
            # Название и количество
            if key and key.startswith("color_"):
                label_text = f"Цвет {key.split('_')[1]}  x{count}"
            elif key:
                label_text = f"{key}  x{count}"
            else:
                label_text = f"{hex_color.upper()}  x{count}"
            
            label = QLabel(label_text)
            label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
            layout.addWidget(label)
            
            layout.addStretch()
            
            # Кнопка "Заменить цвет"
            replace_btn = QPushButton("🎨")
            replace_btn.setFixedSize(30, 30)
            replace_btn.setStyleSheet("background-color: #3d3d3d; border-radius: 4px;")
            replace_btn.clicked.connect(lambda checked, c=color: self.replace_color_in_scheme(c))
            layout.addWidget(replace_btn)
            
            # Кнопка "Выбрать"
            select_btn = QPushButton("✓")
            select_btn.setFixedSize(30, 30)
            select_btn.setStyleSheet("background-color: #3d3d3d; border-radius: 4px;")
            select_btn.clicked.connect(lambda checked, c=color: self.select_color_from_palette(c))
            layout.addWidget(select_btn)
            
            item = QListWidgetItem(self.palette_list)
            item.setSizeHint(item_widget.sizeHint())
            self.palette_list.setItemWidget(item, item_widget)
            item.setData(Qt.UserRole, color)
            
    def select_color_from_palette(self, color):
        """Выбрать цвет из палитры для кисти и подсветить ячейки"""
        self.current_color = color
        self.update_color_preview()
        self.set_tool("brush")
        self.canvas.highlight_cells_by_color(color)  # ← подсветка ячеек
        self.statusBar().showMessage(f"Выбран цвет RGB{color} — подсвечено {self.canvas.highlighted_cells} ячеек")

    def replace_color_in_scheme(self, old_color):
        """Заменить один цвет на другой во всей схеме"""
        new_color = QColorDialog.getColor(QColor(*old_color), self, "Выбери новый цвет")
        if new_color.isValid():
            new_rgb = (new_color.red(), new_color.green(), new_color.blue())
            
            # Сохраняем состояние для Undo
            old_state = {
                'rgb_matrix': copy.deepcopy(self.rgb_matrix),
                'symbol_matrix': copy.deepcopy(self.symbol_matrix),
                'palette': copy.deepcopy(self.palette)
            }
            
            # Заменяем цвет
            for i in range(self.rows):
                for j in range(self.cols):
                    if tuple(self.rgb_matrix[i][j]) == old_color:
                        self.canvas.set_cell_color(i, j, new_rgb, update_data=True)
            
            # Обновляем палитру, если этот цвет был связан с символом
            for symbol, color in list(self.palette.items()):
                if color == old_color:
                    self.palette[symbol] = new_rgb
            
            self.canvas.load_scheme(self.rgb_matrix, self.symbol_matrix)
            self.update_palette_display()
            
            # Сохраняем в историю
            new_state = {
                'rgb_matrix': copy.deepcopy(self.rgb_matrix),
                'symbol_matrix': copy.deepcopy(self.symbol_matrix),
                'palette': copy.deepcopy(self.palette)
            }
            cmd = FloodFillCommand(self.canvas, self.rgb_matrix, self.symbol_matrix, 
                                self.palette, old_state, new_state)
            self.undo_stack.push(cmd)
            
            self.statusBar().showMessage(f"Цвет заменён")

    # def update_history_display(self):
    #     """Обновление списка истории"""
    #     self.history_list.clear()
    #     for i in range(self.undo_stack.count()):
    #         cmd = self.undo_stack.command(i)
    #         self.history_list.addItem(f"{i+1}. {cmd.text()}")
    #     if self.undo_stack.index() >= 0:
    #         self.history_list.setCurrentRow(self.undo_stack.index())

    def update_history_display(self):
        """Обновление списка истории (красивые плашки)"""
        # Очищаем, но оставляем stretch
        for i in reversed(range(self.history_layout_inner.count() - 1)):
            widget = self.history_layout_inner.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Добавляем каждое действие как плашку
        for i in range(self.undo_stack.count()):
            cmd = self.undo_stack.command(i)
            cmd_text = cmd.text()
            
            # Создаём плашку
            item_widget = QWidget()
            item_widget.setStyleSheet("""
                QWidget {
                    background-color: #3d3d3d;
                    border-radius: 6px;
                    margin: 2px;
                }
                QWidget:hover {
                    background-color: #4d4d4d;
                }
            """)
            
            layout = QHBoxLayout(item_widget)
            layout.setContentsMargins(10, 8, 10, 8)
            
            # Иконка действия (по тексту)
            icon = "🎨"
            if "кисть" in cmd_text.lower() or "brush" in cmd_text.lower():
                icon = "🖌️"
            elif "ластик" in cmd_text.lower() or "eraser" in cmd_text.lower():
                icon = "🧽"
            elif "заливк" in cmd_text.lower() or "fill" in cmd_text.lower():
                icon = "🪣"
            elif "символ" in cmd_text.lower() or "symbol" in cmd_text.lower():
                icon = "🔤"
            elif "замен" in cmd_text.lower() or "replace" in cmd_text.lower():
                icon = "🔄"
            elif "загрузк" in cmd_text.lower():
                icon = "📂"
            
            # Номер действия и текст
            number_label = QLabel(f"{i+1}.")
            number_label.setStyleSheet("color: #888888; font-size: 11px;")
            number_label.setFixedWidth(25)
            
            text_label = QLabel(f"{icon} {cmd_text}")
            text_label.setStyleSheet("color: #e0e0e0; font-size: 11px;")
            
            layout.addWidget(number_label)
            layout.addWidget(text_label)
            layout.addStretch()
            
            # Индикатор текущего состояния
            if i == self.undo_stack.index():
                indicator = QLabel("●")
                indicator.setStyleSheet("color: #0078d4; font-size: 12px;")
                layout.addWidget(indicator)
            
            # Добавляем в контейнер
            self.history_layout_inner.insertWidget(self.history_layout_inner.count() - 1, item_widget)
            
            # Сохраняем индекс для клика
            item_widget.mousePressEvent = lambda e, idx=i: self.jump_to_history(idx)
            
            # Подсветка текущего действия
            if i == self.undo_stack.index():
                item_widget.setStyleSheet("""
                    QWidget {
                        background-color: #0078d4;
                        border-radius: 6px;
                        margin: 2px;
                    }
                """)
                text_label.setStyleSheet("color: white; font-size: 11px;")
                number_label.setStyleSheet("color: #cce5ff; font-size: 11px;")
    

    def jump_to_history(self, idx):
        """Переход к определённому действию в истории"""
        if 0 <= idx < self.undo_stack.count():
            while self.undo_stack.index() > idx:
                self.undo_stack.undo()
            while self.undo_stack.index() < idx:
                self.undo_stack.redo()

    def clear_history(self):
        """Очистить историю действий"""
        self.undo_stack.clear()
        self.update_history_display()
        self.statusBar().showMessage("История очищена")

    def on_history_click(self, item):
        """Переход к действию в истории"""
        idx = self.history_list.currentRow()
        if idx >= 0:
            while self.undo_stack.index() > idx:
                self.undo_stack.undo()
            while self.undo_stack.index() < idx:
                self.undo_stack.redo()
    
    def on_palette_click(self, item):
        """Клик по палитре - выбор цвета для кисти"""
        color = item.data(Qt.UserRole)
        if color:
            self.current_color = color
            self.update_color_preview()
            self.set_tool("brush")
            self.statusBar().showMessage(f"Выбран цвет RGB{color}")
            self.select_color_from_palette(color)
    
    def replace_all_cells_by_symbol(self, symbol, new_symbol=None, new_color=None):
        """
        Замена символа и/или цвета для всех ячеек с указанным символом
        """
        if symbol not in self.palette:
            return
        
        old_color = self.palette[symbol]
        
        # Если новый цвет не указан, спрашиваем
        if new_color is None:
            color = QColorDialog.getColor(QColor(*old_color), self, f"Выбери новый цвет для символа '{symbol}'")
            if color.isValid():
                new_color = (color.red(), color.green(), color.blue())
            else:
                return
        
        # Если новый символ не указан, спрашиваем
        if new_symbol is None:
            new_symbol, ok = QInputDialog.getText(self, "Новый символ", 
                                                f"Введи новый символ для '{symbol}':",
                                                text=symbol)
            if not ok or not new_symbol:
                new_symbol = symbol
        
        # Сохраняем состояние для Undo
        old_state = {
            'rgb_matrix': copy.deepcopy(self.rgb_matrix),
            'symbol_matrix': copy.deepcopy(self.symbol_matrix),
            'palette': copy.deepcopy(self.palette)
        }
        
        # Заменяем все ячейки
        for i in range(self.rows):
            for j in range(self.cols):
                if self.symbol_matrix[i][j] == symbol:
                    if new_color:
                        self.canvas.set_cell_color(i, j, new_color, update_data=True)
                    if new_symbol and new_symbol != symbol:
                        self.canvas.set_cell_symbol(i, j, new_symbol, update_data=True)
        
        # Обновляем палитру
        if new_color:
            self.palette[new_symbol if new_symbol != symbol else symbol] = new_color
        if new_symbol and new_symbol != symbol:
            # Удаляем старый символ из палитры, если он больше не используется
            still_used = False
            for i in range(self.rows):
                for j in range(self.cols):
                    if self.symbol_matrix[i][j] == symbol:
                        still_used = True
                        break
            if not still_used and symbol in self.palette:
                del self.palette[symbol]
        
        # Обновляем отображение
        self.canvas.load_scheme(self.rgb_matrix, self.symbol_matrix)
        self.update_palette_display()
        
        # Сохраняем в историю
        new_state = {
            'rgb_matrix': copy.deepcopy(self.rgb_matrix),
            'symbol_matrix': copy.deepcopy(self.symbol_matrix),
            'palette': copy.deepcopy(self.palette)
        }
        cmd = FloodFillCommand(self.canvas, self.rgb_matrix, self.symbol_matrix, 
                            self.palette, old_state, new_state)
        self.undo_stack.push(cmd)
        
        self.statusBar().showMessage(f"Заменены все ячейки с '{symbol}' на '{new_symbol}'")
    
    def highlight_cells_by_symbol(self, symbol):
        """Подсветка ячеек с указанным символом"""
        self.canvas.highlight_cells_by_symbol(symbol)
    
    def clear_highlight(self):
        """Снять подсветку"""
        self.canvas.clear_highlight()
        self.statusBar().showMessage("Подсветка снята")
    
    def on_cell_clicked(self, row, col):
        """Обработка клика по ячейке"""
        if self.current_tool == "brush":
            old_color = self.canvas.get_cell_color(row, col)
            if old_color != self.current_color:
                cmd = ChangeCellColorCommand(self.canvas, row, col, old_color, self.current_color)
                self.undo_stack.push(cmd)
        
        elif self.current_tool == "eraser":
            old_color = self.canvas.get_cell_color(row, col)
            white = (255, 255, 255)
            if old_color != white:
                cmd = ChangeCellColorCommand(self.canvas, row, col, old_color, white)
                self.undo_stack.push(cmd)
        
        elif self.current_tool == "eyedropper":
            color = self.canvas.get_cell_color(row, col)
            self.current_color = color
            self.update_color_preview()
            self.set_tool("brush")
            self.statusBar().showMessage(f"Взят цвет RGB{color}")
        
        elif self.current_tool == "fill":
            target_color = self.canvas.get_cell_color(row, col)
            if target_color != self.current_color:
                # Сохраняем состояние до заливки
                old_state = {
                    'rgb_matrix': copy.deepcopy(self.rgb_matrix),
                    'symbol_matrix': copy.deepcopy(self.symbol_matrix),
                    'palette': copy.deepcopy(self.palette)
                }
                self.flood_fill(row, col, target_color, self.current_color)
                new_state = {
                    'rgb_matrix': copy.deepcopy(self.rgb_matrix),
                    'symbol_matrix': copy.deepcopy(self.symbol_matrix),
                    'palette': copy.deepcopy(self.palette)
                }
                cmd = FloodFillCommand(self.canvas, self.rgb_matrix, self.symbol_matrix, 
                                       self.palette, old_state, new_state)
                self.undo_stack.push(cmd)
        
        elif self.current_tool == "text":
            self.edit_cell_symbol(row, col)
    
    def flood_fill(self, row, col, target_color, new_color, visited=None):
        """Рекурсивная заливка"""
        if visited is None:
            visited = set()
        if (row, col) in visited:
            return
        if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
            return
        visited.add((row, col))
        if self.rgb_matrix[row][col] == target_color:
            self.canvas.set_cell_color(row, col, new_color, update_data=True)
            self.flood_fill(row+1, col, target_color, new_color, visited)
            self.flood_fill(row-1, col, target_color, new_color, visited)
            self.flood_fill(row, col+1, target_color, new_color, visited)
            self.flood_fill(row, col-1, target_color, new_color, visited)
    
    def edit_cell_symbol(self, row, col):
        """Редактирование символа в ячейке"""
        from PySide6.QtWidgets import QInputDialog
        
        old_symbol = self.symbol_matrix[row][col] if self.symbol_matrix else " "
        symbol, ok = QInputDialog.getText(self, "Символ ячейки", 
                                          f"Введи символ для ячейки [{row}, {col}]:",
                                          text=old_symbol)
        if ok and symbol and symbol != old_symbol:
            cmd = ChangeSymbolCommand(self.canvas, row, col, old_symbol, symbol)
            self.undo_stack.push(cmd)
    
    def replace_palette_color(self, symbol):
        """Замена цвета для символа во всей схеме"""
        old_color = self.palette.get(symbol)
        if not old_color:
            return
        new_color = QColorDialog.getColor(QColor(*old_color), self, f"Новый цвет для '{symbol}'")
        if new_color.isValid():
            new_rgb = (new_color.red(), new_color.green(), new_color.blue())
            cmd = ReplaceColorCommand(self.canvas, symbol, old_color, new_rgb)
            self.undo_stack.push(cmd)

    def update_cursor(self):
        """Обновляет курсор в зависимости от выбранного инструмента"""
        cursors = {
            "hand": Qt.OpenHandCursor,
            "brush": Qt.CrossCursor,
            "eyedropper": Qt.IBeamCursor,
            "eraser": Qt.BlankCursor,  # ластик обычно квадратный
            "fill": Qt.PointingHandCursor,
            "text": Qt.IBeamCursor,
        }
        cursor = cursors.get(self.current_tool, Qt.ArrowCursor)
        self.canvas.setCursor(cursor)
    
    # ============================================
    # ЗАГРУЗКА / СОХРАНЕНИЕ
    # ============================================
    
    def load_json(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Открыть JSON", "", "JSON (*.json)")
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.rgb_matrix = data['rgb_matrix']
            self.rows = len(self.rgb_matrix)
            self.cols = len(self.rgb_matrix[0]) if self.rows > 0 else 0
            self.symbol_matrix = data.get('symbol_matrix', 
                [[" " for _ in range(self.cols)] for _ in range(self.rows)])
            
            # Восстанавливаем палитру из symbol_matrix (если есть символы)
            self.palette = {}
            for i in range(self.rows):
                for j in range(self.cols):
                    sym = self.symbol_matrix[i][j]
                    if sym and sym != " ":
                        self.palette[sym] = tuple(self.rgb_matrix[i][j])
            
            # ЕСЛИ ПАЛИТРА ВСЁ ЕЩЁ ПУСТАЯ — СОЗДАЁМ ИЗ ЦВЕТОВ (БЕЗ СИМВОЛОВ)
            if not self.palette and self.rows > 0:
                print("DEBUG: Создаём палитру из уникальных цветов (без символов)")
                # Просто собираем уникальные цвета
                unique_colors = set()
                for i in range(self.rows):
                    for j in range(self.cols):
                        unique_colors.add(tuple(self.rgb_matrix[i][j]))
                
                # Для каждого цвета создаём временный ключ (временный символ)
                # Но не записываем его в symbol_matrix!
                temp_symbol = 1
                for color in unique_colors:
                    # Используем временный символ для отображения в палитре
                    self.palette[f"color_{temp_symbol}"] = color
                    temp_symbol += 1
            
            # Загружаем на холст
            self.canvas.rgb_matrix = self.rgb_matrix
            self.canvas.symbol_matrix = self.symbol_matrix
            self.canvas.palette = self.palette
            self.canvas.rows = self.rows
            self.canvas.cols = self.cols
            self.canvas.load_scheme(self.rgb_matrix, self.symbol_matrix)
            
            self.update_palette_display()
            self.undo_stack.clear()
            
            self.statusBar().showMessage(f"Загружена схема {self.rows}x{self.cols}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл:\n{str(e)}")
    
    def save_json(self):
        if self.rows == 0:
            QMessageBox.warning(self, "Предупреждение", "Нет данных для сохранения")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить JSON", "", "JSON (*.json)")
        if not filepath:
            return
        
        data = {
            "rows": self.rows,
            "cols": self.cols,
            "rgb_matrix": self.rgb_matrix,
            "symbol_matrix": self.symbol_matrix,
            "palette": {k: list(v) for k, v in self.palette.items()}
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        self.statusBar().showMessage(f"Сохранено: {filepath}")
    
    def export_png(self):
        if self.rows == 0:
            return
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Экспорт PNG", "", "PNG (*.png)")
        if filepath:
            self.canvas.export_png(filepath)
            self.statusBar().showMessage(f"Экспортировано: {filepath}")
    
    def show_stats(self):
        stats = f"""
📊 СТАТИСТИКА СХЕМЫ

Размер: {self.rows} x {self.cols}
Всего ячеек: {self.rows * self.cols}
Уникальных цветов: {len(self.palette)}
Уникальных символов: {len([s for s in self.palette.keys() if s and s != " "])}
        """
        QMessageBox.information(self, "Статистика", stats)
    
    def zoom_in(self):
        self.canvas.zoom_in()
    
    def zoom_out(self):
        self.canvas.zoom_out()
    
    def zoom_reset(self):
        self.canvas.zoom_reset()
    
    def undo(self):
        self.undo_stack.undo()
    
    def redo(self):
        self.undo_stack.redo()


# ============================================
# ЗАПУСК
# ============================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CrossStitchWindow()
    window.show()
    sys.exit(app.exec())