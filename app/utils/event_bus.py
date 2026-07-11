from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    donnees_mises_a_jour = Signal()


event_bus = EventBus()