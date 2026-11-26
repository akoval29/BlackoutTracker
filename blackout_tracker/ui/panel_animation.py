"""Shared timing and clipped, leftward reveal for side panels."""
from PySide6.QtCore import QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainterPath, QRegion


def create_panel_animation(parent, update):
    animation = QVariantAnimation(parent)
    animation.setDuration(260)
    animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    animation.valueChanged.connect(update)
    return animation


def arrange_reveal(clip, content, edge, top, width, height, reveal):
    visible = min(width, max(0, round(reveal)))
    clip.setGeometry(edge - visible, top, visible, height)
    # Reveal the left edge first; the content never shrinks or reflows.
    content.setGeometry(0, 0, width, height)
    radius = min(14, visible, height)
    corner = QPainterPath()
    corner.moveTo(radius, 0)
    corner.lineTo(visible, 0)
    corner.lineTo(visible, height)
    corner.lineTo(0, height)
    corner.lineTo(0, radius)
    corner.quadTo(0, 0, radius, 0)
    corner.closeSubpath()
    clip.setMask(QRegion(corner.toFillPolygon().toPolygon()))
    clip.setVisible(visible > 0)
    return visible
