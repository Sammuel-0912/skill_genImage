# -*- coding: utf-8 -*-
"""可重複使用的介面元件。"""

from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                            QSize, Qt, QTimer, Signal)
from PySide6.QtGui import (QColor, QDesktopServices, QGuiApplication, QIcon,
                           QPainter, QPen, QPixmap)
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QMenu, QPlainTextEdit,
                               QPushButton, QScrollArea, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".m4v"}


def shadow(widget, blur=24, dy=4, color=None):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(color or QColor(0, 0, 0, 30))
    widget.setGraphicsEffect(eff)
    return eff


def rounded(pix: QPixmap, radius: int = 10) -> QPixmap:
    """把 pixmap 裁成圓角。"""
    if pix.isNull():
        return pix
    out = QPixmap(pix.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(Qt.NoBrush)
    path_rect = QRect(0, 0, pix.width(), pix.height())
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    path.addRoundedRect(path_rect, radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pix)
    p.end()
    return out


# ---------------------------------------------------------------- 流式版面

class FlowLayout(QLayout):
    """作品牆用的自動換行版面。"""

    def __init__(self, parent=None, margin=0, spacing=14):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def insertWidgetAt(self, index, widget):
        self.addWidget(widget)
        item = self._items.pop()
        self._items.insert(index, item)
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, test=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect, test):
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = eff.x(), eff.y(), 0
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            if x + w > eff.right() + 1 and line_h > 0:
                x = eff.x()
                y += line_h + self._spacing
                line_h = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x += w + self._spacing
            line_h = max(line_h, h)
        return y + line_h - rect.y() + m.bottom()


# ---------------------------------------------------------------- 轉圈圈

class Spinner(QWidget):
    def __init__(self, size=18, width=2, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._w = width
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.color = QColor("#888888")

    def start(self):
        if not self._timer.isActive():
            self._timer.start(28)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.color, self._w)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        r = self.rect().adjusted(self._w, self._w, -self._w, -self._w)
        p.drawArc(r, -self._angle * 16, 100 * 16)


# ---------------------------------------------------------------- 參數藥丸

class ParamPill(QToolButton):
    """一顆參數按鈕，點了跳出選項選單。"""

    changed = Signal(str, object)

    def __init__(self, spec: dict, value, parent=None):
        super().__init__(parent)
        self.setObjectName("Pill")
        self.spec = spec
        self.key = spec["key"]
        self.setPopupMode(QToolButton.InstantPopup)
        self.setCursor(Qt.PointingHandCursor)
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self.set_value(value)
        self._build_menu()

    # 值 → 顯示文字
    def _label_for(self, value) -> str:
        if self.spec.get("type") == "bool":
            return "開" if value else "關"
        for v in self.spec.get("values", []):
            if isinstance(v, dict) and v.get("value") == value:
                return str(v.get("label", value))
        return "預設" if value in ("", None) else str(value)

    def _options(self):
        if self.spec.get("type") == "bool":
            return [("開", True), ("關", False)]
        out = []
        for v in self.spec.get("values", []):
            if isinstance(v, dict):
                out.append((str(v.get("label", v.get("value"))), v.get("value")))
            else:
                out.append((str(v), v))
        return out

    def _build_menu(self):
        self._menu.clear()
        for label, value in self._options():
            act = self._menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(value == self.value)
            act.triggered.connect(lambda _=False, v=value: self._pick(v))

    def _pick(self, value):
        self.set_value(value)
        self._build_menu()
        self.changed.emit(self.key, value)

    def set_value(self, value):
        self.value = value
        self.setText(f"{self.spec.get('label', self.key)}  {self._label_for(value)}")


# ---------------------------------------------------------------- 參考圖區

class DropZone(QFrame):
    """拖曳參考圖進來。"""

    changed = Signal()

    def __init__(self, ref_dir: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragging", "false")
        self.setMinimumHeight(92)
        self.ref_dir = Path(ref_dir)
        self.paths = []
        self.max_items = 10

        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(10, 10, 10, 10)
        self._lay.setSpacing(8)
        self._hint = QLabel("拖曳參考圖到這裡，或點擊選擇")
        self._hint.setObjectName("Muted")
        self._hint.setAlignment(Qt.AlignCenter)
        self._lay.addWidget(self._hint)
        self.setCursor(Qt.PointingHandCursor)

    # --- 拖放 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_dragging(True)

    def dragLeaveEvent(self, _):
        self._set_dragging(False)

    def dropEvent(self, e):
        self._set_dragging(False)
        files = []
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_file() and p.suffix.lower() in IMAGE_EXT:
                files.append(p)
        if files:
            self.add(files)
            e.acceptProposedAction()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            picked, _ = QFileDialog.getOpenFileNames(
                self, "選擇參考圖", str(self.ref_dir),
                "圖片 (*.png *.jpg *.jpeg *.webp *.bmp)")
            if picked:
                self.add([Path(p) for p in picked])

    def _set_dragging(self, on: bool):
        self.setProperty("dragging", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    # --- 資料 ---
    def set_max(self, n: int):
        self.max_items = max(1, int(n))
        if len(self.paths) > self.max_items:
            self.paths = self.paths[: self.max_items]
        self._rebuild()

    def add(self, files):
        for f in files:
            f = Path(f)
            # 不在參考圖資料夾裡的，複製一份進去
            try:
                if f.parent.resolve() != self.ref_dir.resolve():
                    target = self.ref_dir / f.name
                    i = 1
                    while target.exists() and target.stat().st_size != f.stat().st_size:
                        target = self.ref_dir / f"{f.stem}-{i}{f.suffix}"
                        i += 1
                    if not target.exists():
                        target.write_bytes(f.read_bytes())
                    f = target
            except OSError:
                pass
            if str(f) not in self.paths:
                self.paths.append(str(f))
        self.paths = self.paths[: self.max_items]
        self._rebuild()
        self.changed.emit()

    def remove(self, path: str):
        if path in self.paths:
            self.paths.remove(path)
            self._rebuild()
            self.changed.emit()

    def clear(self):
        self.paths.clear()
        self._rebuild()
        self.changed.emit()

    def _rebuild(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.paths:
            self._hint = QLabel("拖曳參考圖到這裡，或點擊選擇")
            self._hint.setObjectName("Muted")
            self._hint.setAlignment(Qt.AlignCenter)
            self._lay.addWidget(self._hint)
            return

        for path in self.paths:
            self._lay.addWidget(self._thumb(path))
        self._lay.addStretch(1)

    def _thumb(self, path: str) -> QWidget:
        holder = QWidget(self)
        holder.setFixedSize(72, 72)
        lbl = QLabel(holder)
        lbl.setGeometry(0, 0, 72, 72)
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(72, 72, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            lbl.setPixmap(rounded(pix.copy(0, 0, 72, 72), 9))
        lbl.setToolTip(Path(path).name)

        x = QToolButton(holder)
        x.setObjectName("CardBtn")
        x.setText("✕")
        x.setFixedSize(20, 20)
        x.move(50, 2)
        x.setCursor(Qt.PointingHandCursor)
        x.clicked.connect(lambda: self.remove(path))
        return holder


# ---------------------------------------------------------------- 作品卡片

class WorkCard(QFrame):
    """作品牆上的一張卡。placeholder=True 時是生成中的佔位卡。"""

    CARD_W = 248

    open_requested = Signal(object)
    delete_requested = Signal(object)
    download_requested = Signal(object)

    def __init__(self, path=None, meta=None, placeholder=False, label="", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.path = Path(path) if path else None
        self.meta = meta or {}
        self.placeholder = placeholder
        self.setFixedWidth(self.CARD_W)
        shadow(self, blur=20, dy=3)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setMinimumHeight(130)
        lay.addWidget(self.thumb)

        self.caption = QLabel(label or (self.path.name if self.path else ""))
        self.caption.setObjectName("Muted")
        self.caption.setWordWrap(False)
        self.caption.setTextFormat(Qt.PlainText)
        lay.addWidget(self.caption)

        # 浮動按鈕
        self.btn_download = QToolButton(self)
        self.btn_download.setObjectName("CardBtn")
        self.btn_download.setText("⤓")
        self.btn_download.setToolTip("下載")
        self.btn_delete = QToolButton(self)
        self.btn_delete.setObjectName("CardBtn")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setText("🗑")
        self.btn_delete.setToolTip("刪除")
        for b in (self.btn_download, self.btn_delete):
            b.setFixedSize(28, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.hide()
        self.btn_download.clicked.connect(lambda: self.download_requested.emit(self))
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self))

        self.spinner = Spinner(24, 2, self)

        if placeholder:
            self._render_placeholder(label)
        else:
            self.render_file()
        self.setCursor(Qt.PointingHandCursor if not placeholder else Qt.ArrowCursor)

    # --- 呈現 ---
    def _render_placeholder(self, label):
        self.thumb.setFixedHeight(150)
        self.thumb.setText("")
        self.caption.setText(label or "生成中…")
        self.spinner.start()
        self._place_spinner()

    def _place_spinner(self):
        self.spinner.move(self.CARD_W // 2 - 12, 10 + 150 // 2 - 12)
        self.spinner.raise_()

    def render_file(self):
        self.spinner.stop()
        if not self.path or not self.path.exists():
            self.thumb.setText("檔案不存在")
            return
        if self.path.suffix.lower() in VIDEO_EXT:
            self.thumb.setFixedHeight(150)
            self.thumb.setText("🎬")
            f = self.thumb.font()
            f.setPointSize(34)
            self.thumb.setFont(f)
        else:
            pix = QPixmap(str(self.path))
            if pix.isNull():
                self.thumb.setText("無法預覽")
                return
            w = self.CARD_W - 20
            h = max(90, min(300, int(pix.height() * w / max(1, pix.width()))))
            self.thumb.setFixedHeight(h)
            self.thumb.setPixmap(rounded(
                pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                   .copy(0, 0, w, h), 10))
        self.set_caption(self.path.name)
        self.caption.setToolTip(self.meta.get("prompt", "") or self.path.name)

    def set_caption(self, text: str):
        self._caption_text = text
        self._elide_caption()

    def _elide_caption(self):
        from PySide6.QtGui import QFontMetrics
        text = getattr(self, "_caption_text", "")
        if not text:
            return
        width = max(60, self.caption.width() or (self.CARD_W - 24))
        fm = QFontMetrics(self.caption.font())
        self.caption.setText(fm.elidedText(text, Qt.ElideMiddle, width))

    def promote(self, path: Path, meta: dict):
        """佔位卡變成真正的作品卡。"""
        self.placeholder = False
        self.path = Path(path)
        self.meta = meta or {}
        self.thumb.setFont(QWidget().font())
        self.render_file()
        self.setCursor(Qt.PointingHandCursor)

    def fail(self, message: str):
        self.spinner.stop()
        self.thumb.setText("⚠")
        f = self.thumb.font()
        f.setPointSize(26)
        self.thumb.setFont(f)
        self.caption.setText(message[:60])
        self.caption.setToolTip(message)

    # --- 互動 ---
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.btn_delete.move(self.width() - 36, 8)
        self.btn_download.move(self.width() - 70, 8)
        self._elide_caption()
        if self.placeholder:
            self._place_spinner()

    def enterEvent(self, e):
        if not self.placeholder and self.path:
            self.btn_delete.show()
            self.btn_download.show()
            self.btn_delete.raise_()
            self.btn_download.raise_()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.btn_delete.hide()
        self.btn_download.hide()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and not self.placeholder and self.path:
            self.open_requested.emit(self)
        super().mouseReleaseEvent(e)


# ---------------------------------------------------------------- 放大預覽

class PreviewDialog(QDialog):
    def __init__(self, path: Path, meta: dict, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.meta = meta or {}
        self.setWindowTitle(self.path.name)
        self.setMinimumSize(720, 520)
        self.resize(1080, 720)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # 左：畫面
        stage = QFrame()
        stage.setObjectName("Card")
        sl = QVBoxLayout(stage)
        sl.setContentsMargins(12, 12, 12, 12)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(420, 420)
        sl.addWidget(self.view, 1)
        root.addWidget(stage, 3)

        # 右：資訊
        side = QFrame()
        side.setObjectName("Panel")
        side.setFixedWidth(320)
        il = QVBoxLayout(side)
        il.setContentsMargins(18, 18, 18, 18)
        il.setSpacing(10)

        title = QLabel(self.meta.get("model", "") or self.path.stem)
        title.setObjectName("Title")
        il.addWidget(title)

        sub = QLabel(self.meta.get("created", ""))
        sub.setObjectName("Muted")
        il.addWidget(sub)

        il.addSpacing(6)
        il.addWidget(self._section("提示詞"))
        prompt = QPlainTextEdit(self.meta.get("prompt", "（沒有記錄）"))
        prompt.setReadOnly(True)
        prompt.setMinimumHeight(140)
        il.addWidget(prompt)

        il.addWidget(self._section("設定"))
        rows = [("接口", self.meta.get("endpoint", "—"))]
        for k, v in (self.meta.get("params") or {}).items():
            rows.append((k, v))
        if self.meta.get("references"):
            rows.append(("參考圖", "、".join(self.meta["references"])))
        info = QLabel("\n".join(f"{k}：{v}" for k, v in rows) or "—")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        il.addWidget(info)

        il.addStretch(1)

        btns = QHBoxLayout()
        copy_btn = QPushButton("複製提示詞")
        copy_btn.setObjectName("Ghost")
        copy_btn.clicked.connect(self._copy_prompt)
        open_btn = QPushButton("在檔案總管顯示")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(self._reveal)
        btns.addWidget(copy_btn)
        btns.addWidget(open_btn)
        il.addLayout(btns)

        root.addWidget(side)
        self._load()

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("Title")
        return lbl

    def _copy_prompt(self):
        QGuiApplication.clipboard().setText(self.meta.get("prompt", ""))

    def _reveal(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path.parent)))

    def _load(self):
        if self.path.suffix.lower() in VIDEO_EXT:
            self.view.setText("🎬\n\n影片檔請用系統播放器開啟")
            self.view.setCursor(Qt.PointingHandCursor)
            self.view.mouseReleaseEvent = lambda _e: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.path)))
            return
        self._pix = QPixmap(str(self.path))
        self._rescale()

    def _rescale(self):
        if getattr(self, "_pix", None) and not self._pix.isNull():
            self.view.setPixmap(self._pix.scaled(
                self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()


# ---------------------------------------------------------------- 偏好設定

class PrefsDialog(QDialog):
    def __init__(self, current_key: str, out_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好設定")
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 18)
        lay.setSpacing(12)

        t = QLabel("FAL 金鑰")
        t.setObjectName("Title")
        lay.addWidget(t)

        hint = QLabel("到 fal.ai 的 Dashboard → Keys 產生，貼在這裡。金鑰只會存在專案資料夾的 .env，不會外傳。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        row = QHBoxLayout()
        self.key_edit = QLineEdit(current_key)
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("貼上 FAL_KEY")
        eye = QToolButton()
        eye.setObjectName("Pill")
        eye.setText("顯示")
        eye.setCheckable(True)
        eye.setCursor(Qt.PointingHandCursor)
        eye.toggled.connect(lambda on: self.key_edit.setEchoMode(
            QLineEdit.Normal if on else QLineEdit.Password))
        row.addWidget(self.key_edit, 1)
        row.addWidget(eye)
        lay.addLayout(row)

        lay.addSpacing(6)
        t2 = QLabel("輸出資料夾")
        t2.setObjectName("Title")
        lay.addWidget(t2)

        row2 = QHBoxLayout()
        self.dir_edit = QLineEdit(str(out_dir))
        browse = QToolButton()
        browse.setObjectName("Pill")
        browse.setText("瀏覽…")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse)
        row2.addWidget(self.dir_edit, 1)
        row2.addWidget(browse)
        lay.addLayout(row2)

        lay.addStretch(1)
        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Save).setText("儲存")
        box.button(QDialogButtonBox.Save).setObjectName("Primary")
        box.button(QDialogButtonBox.Cancel).setText("取消")
        box.button(QDialogButtonBox.Cancel).setObjectName("Ghost")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def values(self):
        return self.key_edit.text().strip(), self.dir_edit.text().strip()
