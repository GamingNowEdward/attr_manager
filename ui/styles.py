"""Maya Channel Box-inspired widget styling."""

from __future__ import annotations


STYLESHEET = """
QMainWindow, QWidget {
    background-color: #464646;
    color: #d6d6d6;
}

QMainWindow::separator { background: #252525; width: 1px; height: 1px; }
QLabel { color: #d6d6d6; background: transparent; }

QWidget#attributeToolbar {
    background-color: #505050;
    border-bottom: 1px solid #292929;
}
QWidget#attributeToolbar QLabel { color: #c9c9c9; }

QPushButton {
    background-color: #5a5a5a;
    color: #dedede;
    border: 1px solid #303030;
    border-radius: 0;
    padding: 2px 7px;
    min-height: 17px;
}
QPushButton:hover { background-color: #666666; border-color: #777777; }
QPushButton:pressed { background-color: #363636; border-color: #202020; }
QPushButton:checked { background-color: #6a6a6a; border-color: #a0a0a0; color: #ffffff; }
QPushButton#delBtn {
    background: transparent;
    border: none;
    color: #aaaaaa;
    font-size: 15px;
    padding: 0;
    min-height: 0;
}
QPushButton#delBtn:hover { color: #eeeeee; background: #555555; }

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #363636;
    border: 1px solid #252525;
    border-radius: 0;
    color: #e1e1e1;
    selection-background-color: #5285a6;
    selection-color: #ffffff;
    min-height: 17px;
    padding: 1px 4px;
}
QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover { border-color: #7b7b7b; }
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border-color: #8a8a8a; }
QDoubleSpinBox::up-button, QSpinBox::up-button {
    width: 0; height: 0;
}
QDoubleSpinBox::down-button, QSpinBox::down-button {
    width: 0; height: 0;
}

QSlider::groove:horizontal {
    background: #2e2e2e; height: 5px; border: 1px solid #222222; border-radius: 0;
}
QSlider::sub-page:horizontal { background: #707070; }
QSlider::handle:horizontal {
    background: #c2c2c2; width: 8px; margin: -4px 0; border: 1px solid #202020; border-radius: 0;
}
QSlider::handle:horizontal:hover { background: #dedede; border-color: #f0f0f0; }

QCheckBox { spacing: 4px; color: #d6d6d6; }
QCheckBox::indicator { width: 12px; height: 12px; }
QCheckBox::indicator:unchecked { border: 1px solid #222222; background-color: #353535; border-radius: 0; }
QCheckBox::indicator:checked { border: 1px solid #242424; background-color: #bdbdbd; border-radius: 0; }

QRadioButton { spacing: 4px; color: #d6d6d6; }
QRadioButton::indicator { width: 11px; height: 11px; }
QRadioButton::indicator:unchecked { border: 1px solid #222222; background-color: #353535; border-radius: 6px; }
QRadioButton::indicator:checked { border: 1px solid #222222; background-color: #bdbdbd; border-radius: 6px; }

QComboBox::drop-down { border: none; width: 16px; background: #4d4d4d; }
QComboBox::down-arrow { image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-top: 4px solid #d0d0d0; }
QComboBox QAbstractItemView, QListWidget {
    background-color: #383838; color: #dedede; border: 1px solid #202020;
    selection-background-color: #5285a6; selection-color: #ffffff;
}
QListWidget::item { padding: 3px 6px; }

QScrollArea { background: #414141; border: none; }
QScrollArea > QWidget > QWidget { background: #414141; }
QScrollBar:vertical { background: #393939; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #666666; min-height: 24px; border: 1px solid #2c2c2c; }
QScrollBar::handle:vertical:hover { background: #777777; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #393939; }
QScrollBar:horizontal { height: 0; }

QFrame[frameShape="4"] { color: #292929; }
QLabel#dragHandle { color: #adadad; background: transparent; }
QLabel#dragHandle:hover { color: #eeeeee; background: #585858; }
QLabel#groupArrow { background: transparent; }
QLabel#groupArrow:hover { background: #585858; }
QLabel#nameLabel { min-width: 96px; max-width: 145px; color: #d6d6d6; }
QLabel#groupTitle { color: #eeeeee; font-weight: bold; }
QWidget#groupHeader { background-color: #595959; border: 1px solid #2b2b2b; }
QWidget#attributeRow { background-color: #484848; border-bottom: 1px solid #3b3b3b; }
QWidget#attributeRow:hover { background-color: #505050; }
QLabel#dropPlaceholder {
    color: #808080;
    font-style: italic;
    border: 1px dashed #5a5a5a;
    padding: 4px;
    min-height: 18px;
}
QMenu { background-color: #4a4a4a; color: #dedede; border: 1px solid #242424; }
QMenu::item { padding: 4px 22px 4px 16px; }
QMenu::item:selected { background-color: #686868; color: #ffffff; }
QDialog { background-color: #464646; }
QDialog#sliderRangeDialog { background-color: #464646; }
QLabel#dialogSectionHeader {
    background-color: #5b5b5b;
    border: 1px solid #333333;
    color: #e2e2e2;
    font-weight: bold;
    padding: 3px 7px;
}
QWidget#rangeContent { background-color: #484848; border: 1px solid #343434; }
QWidget#dialogButtonBar { background-color: #414141; border-top: 1px solid #303030; }
QWidget#dialogButtonBar QPushButton { min-height: 21px; }
"""
