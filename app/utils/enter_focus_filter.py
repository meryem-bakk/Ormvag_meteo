from PySide6.QtCore import QObject, Qt, QEvent
from PySide6.QtWidgets import QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QApplication


class FiltreEntreeChampSuivant(QObject):
    """
    Filtre d'événements global : la touche Entrée déplace le focus
    vers le champ suivant au lieu de son comportement par défaut,
    pour tous les champs de saisie de l'application.
    """

    CHAMPS_CONCERNES = (QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if isinstance(obj, self.CHAMPS_CONCERNES):
                widget_focus = QApplication.focusWidget()
                if widget_focus:
                    widget_focus.focusNextChild()
                return True  # bloque le comportement par défaut (ex: soumission accidentelle)
        return super().eventFilter(obj, event)