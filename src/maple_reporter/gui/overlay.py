from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QPixmap
from PySide6.QtWidgets import QWidget
from PIL import Image

class ScreenSnipperOverlay(QWidget):
    """
    Semi-transparent full-screen overlay allowing user to select a rectangular area.
    Emits snippet_captured(PIL.Image, (x, y, w, h)) when user releases mouse.
    """
    snippet_captured = Signal(object, tuple)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.origin_point = None
        self.current_point = None
        self.full_screen_pixmap: QPixmap = None
        self.scale_factor = 1.0

    def start_snipping(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            self.full_screen_pixmap = screen.grabWindow(0)
            self.setGeometry(screen.geometry())
            self.scale_factor = screen.devicePixelRatio()

        self.origin_point = None
        self.current_point = None
        self.showFullScreen()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.full_screen_pixmap:
            painter.drawPixmap(0, 0, self.full_screen_pixmap)

        # Dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # Selection rectangle
        if self.origin_point and self.current_point:
            rect = QRect(self.origin_point, self.current_point).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)

            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 120, 215), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin_point = event.pos()
            self.current_point = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin_point:
            self.current_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.origin_point and self.current_point:
            rect = QRect(self.origin_point, self.current_point).normalized()
            self.hide()

            if rect.width() > 10 and rect.height() > 10 and self.full_screen_pixmap:
                # Crop selected area
                scaled_rect = QRect(
                    int(rect.x() * self.scale_factor),
                    int(rect.y() * self.scale_factor),
                    int(rect.width() * self.scale_factor),
                    int(rect.height() * self.scale_factor)
                )
                cropped_pixmap = self.full_screen_pixmap.copy(scaled_rect)
                qimage = cropped_pixmap.toImage()

                # Convert QImage to PIL Image
                qimage = qimage.convertToFormat(qimage.Format.Format_RGBA8888)
                width, height = qimage.width(), qimage.height()
                ptr = qimage.bits()
                # Use bytes(...) to handle memoryview
                pil_img = Image.frombytes("RGBA", (width, height), bytes(ptr), "raw", "RGBA")

                bounds = (rect.x(), rect.y(), rect.width(), rect.height())
                self.snippet_captured.emit(pil_img, bounds)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
