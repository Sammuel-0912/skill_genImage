# -*- coding: utf-8 -*-
"""FAL Studio — 主視窗。"""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame,
                               QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QToolButton,
                               QVBoxLayout, QWidget, QFileDialog)

if __package__ in (None, ""):                     # 允許直接 python app/main.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app import config, falclient, theme, widgets
else:
    from . import config, falclient, theme, widgets

from app.widgets import (DropZone, FlowLayout, ParamPill, PrefsDialog,
                         PreviewDialog, Spinner, WorkCard, shadow)


class MainWindow(QWidget):
    PANEL_W = 392

    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.setObjectName("Root")
        self.resize(1320, 880)
        self.setMinimumSize(940, 640)

        self.settings = QSettings("falstudio", "FalStudio")
        self.models = config.load_models()
        self.pricing = config.load_pricing()
        self.out_dir = Path(self.settings.value("out_dir", str(config.OUT_DIR)))
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.mode = "image"
        self.model = None
        self.values = {}
        self.pills = []
        self._threads = []
        self._jobs = 0

        self._build()
        self._apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply_theme())

        self._on_mode_changed("image")
        self._load_existing()

    # ================================================================ 介面

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)
        root.addWidget(self._build_panel())
        root.addWidget(self._build_wall(), 1)

    # ---------------------------------------------------------- 左：操作面板

    def _build_panel(self):
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(self.PANEL_W)
        shadow(panel, blur=30, dy=6)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # 標題列
        head = QHBoxLayout()
        title = QLabel(config.APP_NAME)
        title.setObjectName("Title")
        self.gear = QToolButton()
        self.gear.setObjectName("Pill")
        self.gear.setText("偏好設定")
        self.gear.setCursor(Qt.PointingHandCursor)
        self.gear.clicked.connect(self._open_prefs)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.gear)
        lay.addLayout(head)

        # 分頁：圖片 / 影片
        bar = QFrame()
        bar.setObjectName("SegmentBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(3, 3, 3, 3)
        bl.setSpacing(3)
        self.seg = QButtonGroup(self)
        for key, text in (("image", "圖片"), ("video", "影片")):
            b = QPushButton(text)
            b.setObjectName("SegmentBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("mode", key)
            bl.addWidget(b, 1)
            self.seg.addButton(b)
            if key == "image":
                b.setChecked(True)
        self.seg.buttonClicked.connect(
            lambda b: self._on_mode_changed(b.property("mode")))
        lay.addWidget(bar)

        # 模型
        lay.addWidget(self._label("模型"))
        self.model_box = QComboBox()
        self.model_box.setCursor(Qt.PointingHandCursor)
        self.model_box.currentIndexChanged.connect(self._on_model_changed)
        lay.addWidget(self.model_box)

        # 參考圖
        self.ref_label = self._label("參考圖")
        lay.addWidget(self.ref_label)
        self.drop = DropZone(config.REF_DIR)
        self.drop.changed.connect(self._refresh_cost)
        lay.addWidget(self.drop)

        # 提示詞
        lay.addWidget(self._label("提示詞"))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("描述你想生成的內容…（Ctrl+Enter 送出）")
        self.prompt.setMinimumHeight(150)
        lay.addWidget(self.prompt, 1)

        # 參數藥丸
        self.pill_box = QWidget()
        self.pill_lay = FlowLayout(self.pill_box, margin=0, spacing=7)
        lay.addWidget(self.pill_box)

        # 生成列
        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.go = QPushButton("生成")
        self.go.setObjectName("Primary")
        self.go.setCursor(Qt.PointingHandCursor)
        self.go.clicked.connect(self._generate)
        self.go_spin = Spinner(16, 2)
        self.go_spin.hide()
        self.cost = QLabel("—")
        self.cost.setObjectName("Cost")
        bottom.addWidget(self.go)
        bottom.addWidget(self.go_spin)
        bottom.addStretch(1)
        bottom.addWidget(self.cost)
        lay.addLayout(bottom)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        return panel

    def _label(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("Muted")
        return lbl

    # ---------------------------------------------------------- 右：作品牆

    def _build_wall(self):
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        head = QHBoxLayout()
        t = QLabel("作品牆")
        t.setObjectName("Title")
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("Muted")
        folder = QToolButton()
        folder.setObjectName("Pill")
        folder.setText("開啟資料夾")
        folder.setCursor(Qt.PointingHandCursor)
        folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.out_dir))))
        head.addWidget(t)
        head.addWidget(self.count_lbl)
        head.addStretch(1)
        head.addWidget(folder)
        lay.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        self.wall = FlowLayout(inner, margin=2, spacing=14)
        self.scroll.setWidget(inner)
        lay.addWidget(self.scroll, 1)

        self.empty = QLabel("還沒有作品。在左邊輸入提示詞，按下「生成」。")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty)
        return wrap

    # ================================================================ 主題

    def _apply_theme(self):
        app = QApplication.instance()
        p = theme.palette(app)
        self.palette_colors = p
        app.setStyleSheet(theme.stylesheet(p))
        self.go_spin.color = QColor(p["muted"])
        for w in self.findChildren(Spinner):
            w.color = QColor(p["muted"])
        for w in self.findChildren(QFrame):
            eff = w.graphicsEffect()
            if eff is not None:
                eff.setColor(p["shadow"])

    # ================================================================ 邏輯

    def _on_mode_changed(self, mode):
        self.mode = mode
        self.model_box.blockSignals(True)
        self.model_box.clear()
        for m in self.models.get(mode, []):
            self.model_box.addItem(f"{m.label}" + (f"  ·  {m.vendor}" if m.vendor else ""))
        self.model_box.blockSignals(False)
        if self.models.get(mode):
            self.model_box.setCurrentIndex(0)
            self._on_model_changed(0)
        else:
            self.model = None
            self.status.setText("models.json 裡沒有這個模式的模型。")

    def _on_model_changed(self, index):
        pool = self.models.get(self.mode, [])
        if not (0 <= index < len(pool)):
            return
        self.model = pool[index]
        self.values = self.model.defaults()
        self.drop.set_max(self.model.ref_max)
        self.ref_label.setText(
            "參考圖" if self.model.ref_multi else "起始畫格（單張）")
        self._rebuild_pills()
        self._refresh_cost()

    def _rebuild_pills(self):
        while self.pill_lay.count():
            item = self.pill_lay.takeAt(0)
            if item and item.widget():
                w = item.widget()
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.pills = []
        if not self.model:
            return
        for spec in self.model.params:
            pill = ParamPill(spec, self.values.get(spec["key"], spec.get("default")))
            pill.changed.connect(self._on_param_changed)
            self.pill_lay.addWidget(pill)
            self.pills.append(pill)
        self.pill_box.updateGeometry()

    def _on_param_changed(self, key, value):
        self.values[key] = value
        self._refresh_cost()

    def _refresh_cost(self):
        if not self.model:
            self.cost.setText("—")
            return
        amount, ok = config.estimate_cost(self.model, self.values, self.pricing)
        self.cost.setText(config.format_cost(amount) if ok else "—")
        self.cost.setToolTip(
            "依 pricing.json 的估算值，不是實際帳單。" if ok else "pricing.json 裡沒有這個模型的價目。")

    # ---------------------------------------------------------- 生成

    def _generate(self):
        if not self.model:
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            self.prompt.setFocus()
            self.status.setText("請先輸入提示詞。")
            return

        key = config.read_key()
        if not key:
            QMessageBox.information(
                self, "尚未設定金鑰",
                "請先到「偏好設定」貼上你的 FAL 金鑰。")
            self._open_prefs()
            return

        refs = list(self.drop.paths)
        card = WorkCard(placeholder=True, label=f"{self.model.label} 生成中…")
        card.setToolTip(prompt)
        self._insert_card(card, 0)

        worker = falclient.GenerateWorker(
            self.model, self.values, prompt, refs, key, self.out_dir)
        worker.status.connect(lambda s, c=card: self._on_progress(c, s))
        worker.done.connect(lambda paths, meta, c=card: self._on_done(c, paths, meta))
        worker.failed.connect(lambda msg, c=card: self._on_failed(c, msg))
        thread = falclient.start_worker(worker)
        self._threads.append((thread, worker))
        thread.finished.connect(lambda t=thread: self._reap(t))

        self._jobs += 1
        self._set_busy(True)

    def _reap(self, thread):
        self._threads = [(t, w) for (t, w) in self._threads if t is not thread]

    def _set_busy(self, busy):
        running = self._jobs > 0
        self.go.setEnabled(not running)
        self.go.setText("生成中…" if running else "生成")
        if running:
            self.go_spin.start()
        else:
            self.go_spin.stop()
            self.status.setText("")

    def _on_progress(self, card, text):
        card.set_caption(text)
        self.status.setText(text)

    def _on_done(self, card, paths, meta):
        self._jobs = max(0, self._jobs - 1)
        self._set_busy(False)
        if not paths:
            card.deleteLater()
            return
        card.promote(paths[0], meta)
        self._wire_card(card)
        for extra in paths[1:]:
            c = WorkCard(extra, meta)
            self._wire_card(c)
            self._insert_card(c, 0)
        self._refresh_count()

    def _on_failed(self, card, message):
        self._jobs = max(0, self._jobs - 1)
        self._set_busy(False)
        card.fail(message)
        self.status.setText(message)
        QMessageBox.warning(self, "生成失敗", message)

    # ---------------------------------------------------------- 作品牆操作

    def _insert_card(self, card, index=0):
        self.wall.insertWidgetAt(index, card)
        card.show()
        self.empty.hide()
        self._refresh_count()

    def _wire_card(self, card):
        card.open_requested.connect(self._open_card)
        card.delete_requested.connect(self._delete_card)
        card.download_requested.connect(self._download_card)

    def _open_card(self, card):
        meta = card.meta or falclient.read_meta(card.path)
        dlg = PreviewDialog(card.path, meta, self)
        dlg.exec()

    def _delete_card(self, card):
        ans = QMessageBox.question(
            self, "刪除作品",
            f"要刪除 {card.path.name} 嗎？檔案會從資料夾移除。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        try:
            card.path.unlink()
        except OSError as e:
            QMessageBox.warning(self, "刪不掉", str(e))
            return
        falclient.delete_meta(card.path)
        for i in range(self.wall.count()):
            item = self.wall.itemAt(i)
            if item and item.widget() is card:
                self.wall.takeAt(i)
                break
        card.setParent(None)
        card.deleteLater()
        self._refresh_count()

    def _download_card(self, card):
        target, _ = QFileDialog.getSaveFileName(
            self, "另存作品", str(Path.home() / "Downloads" / card.path.name))
        if not target:
            return
        try:
            Path(target).write_bytes(card.path.read_bytes())
            self.status.setText(f"已另存到 {target}")
        except OSError as e:
            QMessageBox.warning(self, "存檔失敗", str(e))

    def _refresh_count(self):
        n = sum(1 for i in range(self.wall.count())
                if self.wall.itemAt(i) and not self.wall.itemAt(i).widget().placeholder)
        self.count_lbl.setText(f"{n} 件" if n else "")
        self.empty.setVisible(self.wall.count() == 0)

    def _load_existing(self):
        exts = widgets.IMAGE_EXT | widgets.VIDEO_EXT
        files = [p for p in self.out_dir.iterdir()
                 if p.is_file() and p.suffix.lower() in exts]
        files.sort(key=lambda p: p.stat().st_mtime)      # 舊 → 新
        for p in files:                                  # 逐一插到最前，最後最新在前
            card = WorkCard(p, falclient.read_meta(p))
            self._wire_card(card)
            self._insert_card(card, 0)
        self._refresh_count()

    # ---------------------------------------------------------- 偏好設定

    def _open_prefs(self):
        dlg = PrefsDialog(config.read_key(), self.out_dir, self)
        if dlg.exec() != PrefsDialog.Accepted:
            return
        key, out = dlg.values()
        try:
            config.write_key(key)
        except OSError as e:
            QMessageBox.warning(self, "無法寫入 .env", str(e))
        if out and Path(out) != self.out_dir:
            self.out_dir = Path(out)
            self.out_dir.mkdir(parents=True, exist_ok=True)
            self.settings.setValue("out_dir", str(self.out_dir))
            self._reload_wall()
        self.status.setText("設定已儲存。")
        QTimer.singleShot(2500, lambda: self.status.setText(""))

    def _reload_wall(self):
        while self.wall.count():
            item = self.wall.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        self._load_existing()

    # ---------------------------------------------------------- 快捷鍵

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ControlModifier:
            self._generate()
            return
        super().keyPressEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
