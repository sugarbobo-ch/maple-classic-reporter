from PySide6.QtWidgets import QComboBox


class WheelSafeComboBox(QComboBox):
    """Do not change a selection when the pointer merely passes over it."""

    def wheelEvent(self, event):
        # Keep keyboard and intentional combo-box interaction available, while
        # allowing a wheel over an unfocused combo box to scroll its parent.
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()
