STYLESHEET = """
QMainWindow, QWidget { background-color: #232323; }
QLabel { color: #DCDCDC; font-family: 'Segoe UI'; font-size: 11px; }

QPushButton {
    background-color: #2E3D4D; color: #8DBAE8; border-radius: 4px;
    padding: 3px 8px; min-height: 16px; font-weight: bold; font-family: 'Segoe UI';
}
QPushButton:hover { background-color: #3E4D5D; color: white; border: 1px solid #00AFFF; }
QPushButton:pressed { background-color: #1E2D3D; }
QPushButton:checked { background-color: #2E3D4D; border: 1px solid #00AFFF; color: white; }
QPushButton:checked:hover { background-color: #3E4D5D; }
QPushButton#delBtn { padding: 0; font-size: 13px; min-height: 0; }

QDoubleSpinBox, QSpinBox {
    background-color: #151515; border: 1px solid #333; border-radius: 4px;
    padding: 3px 6px; min-height: 16px; color: #00FFAD; font-family: 'Consolas'; font-size: 11px;
}
QDoubleSpinBox:hover, QSpinBox:hover { border: 1px solid #00AFFF; }
QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    background-color: #2a2a2a; border-left: 1px solid #333; border-bottom: 1px solid #333;
}
QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    background-color: #2a2a2a; border-left: 1px solid #333;
}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
    image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-bottom: 4px solid #8DBAE8;
}
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
    image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-top: 4px solid #8DBAE8;
}

QSlider::groove:horizontal { background: #151515; height: 8px; border-radius: 4px; border: 1px solid #333; }
QSlider::handle:horizontal { background: #00AFFF; width: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover { background: #33CCFF; }
QSlider::sub-page:horizontal { background: #2E3D4D; border-radius: 4px; }

QFrame[frameShape="4"] { color: #333; }

QScrollArea { background-color: transparent; border: none; }
QScrollBar:vertical { background-color: #1a1a1a; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background-color: #444; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background-color: #555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { height: 0px; }

QCheckBox { color: #DCDCDC; }
QCheckBox::indicator { width: 14px; height: 14px; }
QCheckBox::indicator:unchecked { border: 1px solid #555; background-color: #151515; border-radius: 2px; }
QCheckBox::indicator:checked { border: 1px solid #00AFFF; background-color: #00AFFF; border-radius: 2px; }

QComboBox {
    background-color: #151515; border: 1px solid #333; border-radius: 4px;
    padding: 4px 8px; color: #00FFAD; font-family: 'Consolas'; font-size: 11px;
}
QComboBox:hover { border: 1px solid #00AFFF; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #8DBAE8; margin-right: 5px; }
QComboBox QAbstractItemView {
    background-color: #1a1a1a; color: #DCDCDC; border: 1px solid #333;
    selection-background-color: #2E3D4D; selection-color: white;
}

QLineEdit {
    background-color: #151515; border: 1px solid #333; border-radius: 4px;
    padding: 3px 6px; min-height: 16px; color: #00FFAD; font-family: 'Consolas'; font-size: 11px;
}
QLineEdit:hover { border: 1px solid #00AFFF; }

QLabel#dragHandle, QLabel#groupArrow {
    color: #555; font-size: 13px; background: transparent;
}
QLabel#dragHandle:hover, QLabel#groupArrow:hover { color: #00AFFF; }

QLabel#nameLabel {
    min-width: 82px; max-width: 130px; line-height: 20px;
}
QLabel#groupTitle { color: #8DBAE8; font-weight: bold; font-size: 12px; }

QRadioButton { color: #DCDCDC; }
QRadioButton::indicator:unchecked { border: 1px solid #555; background-color: #151515; border-radius: 7px; }
QRadioButton::indicator:checked { border: 1px solid #00AFFF; background-color: #00AFFF; border-radius: 7px; }

QListWidget {
    background-color: #151515; border: 1px solid #333; border-radius: 4px;
    color: #DCDCDC; font-family: 'Segoe UI'; font-size: 11px;
}
QListWidget::item { padding: 4px 8px; }
QListWidget::item:selected { background-color: #2E3D4D; color: white; }

QDialog { background-color: #232323; }
"""
