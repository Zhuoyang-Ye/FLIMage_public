"""
Cross-platform Desktop GUI for FLIMage (.flim) viewing and analysis.
Compatible with macOS (Apple Silicon M1-M4 & Intel) and Windows 10/11.

Features:
- Instant lazy loading of .flim files via FastFLIM.
- Multi-dimensional navigation: Time pages (T), Z-slices (Z), Channels (Ch).
- False-color FLIM overlay (Hue=Lifetime, Value=Intensity) & raw intensity viewing.
- Interactive rectangular / circular ROI selection.
- Real-time fluorescence decay curve plotting (linear and semi-log).
- Multi-exponential reconvolution curve fitting.
- Export to publication-ready TIFF, PNG, and CSV.
"""

import sys
import os
from typing import Optional
import numpy as np

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QPushButton, QLabel, QSlider, QSpinBox, QDoubleSpinBox,
        QComboBox, QFileDialog, QGroupBox, QSplitter, QMessageBox,
        QCheckBox, QTextEdit, QTabWidget, QRadioButton, QButtonGroup
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QIcon, QFont, QAction
except ImportError:
    try:
        from PySide6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QGridLayout, QPushButton, QLabel, QSlider, QSpinBox, QDoubleSpinBox,
            QComboBox, QFileDialog, QGroupBox, QSplitter, QMessageBox,
            QCheckBox, QTextEdit, QTabWidget, QRadioButton, QButtonGroup
        )
        from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal
        from PySide6.QtGui import QIcon, QFont, QAction
    except ImportError:
        raise ImportError(
            "PyQt6 or PySide6 is required. Install via: pip install PyQt6"
        )

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle

from fast_io import FastFLIM
from fitting import DecayFitter


class FLIMViewerGUI(QMainWindow):
    def __init__(self, initial_file: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("FLIMage Viewer (Cross-Platform)")
        self.resize(1280, 850)

        self.flim: Optional[FastFLIM] = None
        self.current_page = 0
        self.current_z = 0
        self.current_channel = 0
        self.display_mode = "FLIM_RGB"  # "FLIM_RGB", "Lifetime", "Intensity"

        # ROI State [ymin, ymax, xmin, xmax]
        self.roi = None
        self.roi_patch = None
        self._dragging_roi = False
        self._roi_start = None

        self._init_menu()
        self._init_ui()

        if initial_file and os.path.exists(initial_file):
            self.load_file(initial_file)

    def _init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open .flim File...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file_dialog)
        file_menu.addAction(open_action)

        export_img_action = QAction("Export Displayed Image...", self)
        export_img_action.triggered.connect(self._on_export_image)
        file_menu.addAction(export_img_action)

        export_decay_action = QAction("Export Decay Curve (CSV)...", self)
        export_decay_action.triggered.connect(self._on_export_decay)
        file_menu.addAction(export_decay_action)

        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_splitter)

        # ----------------- Left Panel: Image Viewer & Navigation ----------------- #
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("Open .flim File")
        self.btn_open.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        self.btn_open.clicked.connect(self._on_open_file_dialog)
        top_bar.addWidget(self.btn_open)

        self.lbl_filename = QLabel("No file loaded")
        self.lbl_filename.setStyleSheet("color: #666; font-style: italic;")
        top_bar.addWidget(self.lbl_filename, stretch=1)
        left_layout.addLayout(top_bar)

        # Image Canvas
        self.img_fig = Figure(figsize=(6, 6), facecolor="#1e1e1e")
        self.img_canvas = FigureCanvas(self.img_fig)
        self.img_ax = self.img_fig.add_subplot(111)
        self.img_fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)
        self.img_ax.axis("off")
        self.img_toolbar = NavigationToolbar(self.img_canvas, self)

        self.img_canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.img_canvas.mpl_connect("motion_notify_event", self._on_canvas_drag)
        self.img_canvas.mpl_connect("button_release_event", self._on_canvas_release)

        left_layout.addWidget(self.img_toolbar)
        left_layout.addWidget(self.img_canvas, stretch=1)

        # Display Mode & Color Limits Box
        disp_group = QGroupBox("Display & Color Limits")
        disp_layout = QGridLayout(disp_group)

        # Mode Radio Buttons
        self.rb_rgb = QRadioButton("FLIM False Color")
        self.rb_rgb.setChecked(True)
        self.rb_rgb.toggled.connect(lambda: self._set_display_mode("FLIM_RGB"))
        self.rb_lt = QRadioButton("Lifetime Map")
        self.rb_lt.toggled.connect(lambda: self._set_display_mode("Lifetime"))
        self.rb_int = QRadioButton("Intensity")
        self.rb_int.toggled.connect(lambda: self._set_display_mode("Intensity"))

        mode_box = QHBoxLayout()
        mode_box.addWidget(self.rb_rgb)
        mode_box.addWidget(self.rb_lt)
        mode_box.addWidget(self.rb_int)
        disp_layout.addLayout(mode_box, 0, 0, 1, 4)

        # Lifetime limits
        disp_layout.addWidget(QLabel("Lifetime Min (ns):"), 1, 0)
        self.spin_lt_min = QDoubleSpinBox()
        self.spin_lt_min.setRange(0.0, 20.0)
        self.spin_lt_min.setSingleStep(0.1)
        self.spin_lt_min.setValue(1.6)
        self.spin_lt_min.valueChanged.connect(self.update_image_display)
        disp_layout.addWidget(self.spin_lt_min, 1, 1)

        disp_layout.addWidget(QLabel("Lifetime Max (ns):"), 1, 2)
        self.spin_lt_max = QDoubleSpinBox()
        self.spin_lt_max.setRange(0.0, 20.0)
        self.spin_lt_max.setSingleStep(0.1)
        self.spin_lt_max.setValue(2.2)
        self.spin_lt_max.valueChanged.connect(self.update_image_display)
        disp_layout.addWidget(self.spin_lt_max, 1, 3)

        # Intensity limits
        disp_layout.addWidget(QLabel("Intensity Min:"), 2, 0)
        self.spin_int_min = QDoubleSpinBox()
        self.spin_int_min.setRange(0, 65535)
        self.spin_int_min.setValue(3.0)
        self.spin_int_min.valueChanged.connect(self.update_image_display)
        disp_layout.addWidget(self.spin_int_min, 2, 1)

        disp_layout.addWidget(QLabel("Intensity Max:"), 2, 2)
        self.spin_int_max = QDoubleSpinBox()
        self.spin_int_max.setRange(1, 65535)
        self.spin_int_max.setValue(25.0)
        self.spin_int_max.valueChanged.connect(self.update_image_display)
        disp_layout.addWidget(self.spin_int_max, 2, 3)

        left_layout.addWidget(disp_group)

        # Multi-Dimensional Navigation (Time, Z, Ch)
        nav_group = QGroupBox("Navigation (Time, Z, Channel)")
        nav_layout = QGridLayout(nav_group)

        # Time slider
        nav_layout.addWidget(QLabel("Time Frame:"), 0, 0)
        self.slider_time = QSlider(Qt.Orientation.Horizontal)
        self.slider_time.setRange(0, 0)
        self.slider_time.valueChanged.connect(self._on_time_slider_changed)
        nav_layout.addWidget(self.slider_time, 0, 1)
        self.lbl_time_val = QLabel("1 / 1")
        nav_layout.addWidget(self.lbl_time_val, 0, 2)

        # Z slider
        nav_layout.addWidget(QLabel("Z-Slice:"), 1, 0)
        self.slider_z = QSlider(Qt.Orientation.Horizontal)
        self.slider_z.setRange(0, 0)
        self.slider_z.valueChanged.connect(self._on_z_slider_changed)
        nav_layout.addWidget(self.slider_z, 1, 1)
        self.lbl_z_val = QLabel("1 / 1")
        nav_layout.addWidget(self.lbl_z_val, 1, 2)

        # Channel dropdown
        nav_layout.addWidget(QLabel("Channel:"), 2, 0)
        self.combo_ch = QComboBox()
        self.combo_ch.currentIndexChanged.connect(self._on_channel_changed)
        nav_layout.addWidget(self.combo_ch, 2, 1, 1, 2)

        left_layout.addWidget(nav_group)
        main_splitter.addWidget(left_widget)

        # ----------------- Right Panel: Decay Curve & Fitting ----------------- #
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Decay Plot Canvas
        self.decay_fig = Figure(figsize=(5, 5))
        self.decay_canvas = FigureCanvas(self.decay_fig)
        self.decay_ax = self.decay_fig.add_subplot(211)
        self.res_ax = self.decay_fig.add_subplot(212, sharex=self.decay_ax)
        self.decay_fig.subplots_adjust(left=0.15, right=0.95, top=0.95, bottom=0.12, hspace=0.3)
        self.decay_toolbar = NavigationToolbar(self.decay_canvas, self)

        decay_header = QHBoxLayout()
        decay_header.addWidget(QLabel("<b>Fluorescence Decay Curve & ROI</b>"))
        self.chk_semilog = QCheckBox("Semi-log (Y)")
        self.chk_semilog.setChecked(True)
        self.chk_semilog.toggled.connect(self.update_decay_display)
        decay_header.addWidget(self.chk_semilog)

        self.btn_clear_roi = QPushButton("Clear ROI")
        self.btn_clear_roi.clicked.connect(self._clear_roi)
        decay_header.addWidget(self.btn_clear_roi)

        right_layout.addLayout(decay_header)
        right_layout.addWidget(self.decay_toolbar)
        right_layout.addWidget(self.decay_canvas, stretch=1)

        # Fitting Controls Box
        fit_group = QGroupBox("Decay Fitting (Gaussian Reconvolution)")
        fit_layout = QGridLayout(fit_group)

        fit_layout.addWidget(QLabel("Model:"), 0, 0)
        self.combo_model = QComboBox()
        self.combo_model.addItems(["1-Exponential", "2-Exponential"])
        self.combo_model.setCurrentIndex(1)
        fit_layout.addWidget(self.combo_model, 0, 1)

        self.btn_fit = QPushButton("Run Reconvolution Fit")
        self.btn_fit.setStyleSheet("font-weight: bold; background-color: #007acc; color: white;")
        self.btn_fit.clicked.connect(self._run_fit)
        fit_layout.addWidget(self.btn_fit, 0, 2)

        # Results summary box
        self.txt_fit_results = QTextEdit()
        self.txt_fit_results.setReadOnly(True)
        self.txt_fit_results.setMaximumHeight(140)
        self.txt_fit_results.setFont(QFont("Courier", 11))
        fit_layout.addWidget(self.txt_fit_results, 1, 0, 1, 3)

        right_layout.addWidget(fit_group)
        main_splitter.addWidget(right_widget)

        main_splitter.setSizes([700, 580])

    # ----------------- File Loading ----------------- #
    def _on_open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FLIM File",
            "",
            "FLIMage Files (*.flim *.tif *.tiff);;All Files (*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        try:
            self.flim = FastFLIM(file_path)
            self.lbl_filename.setText(f"{os.path.basename(file_path)} ({self.flim.width}x{self.flim.height})")

            # Update Navigation Sliders
            self.slider_time.blockSignals(True)
            self.slider_time.setRange(0, max(0, self.flim.n_pages - 1))
            self.slider_time.setValue(0)
            self.slider_time.blockSignals(False)
            self.lbl_time_val.setText(f"1 / {self.flim.n_pages}")

            self.slider_z.blockSignals(True)
            self.slider_z.setRange(0, max(0, self.flim.n_fast_z - 1))
            self.slider_z.setValue(0)
            self.slider_z.blockSignals(False)
            self.lbl_z_val.setText(f"1 / {self.flim.n_fast_z}")

            self.combo_ch.blockSignals(True)
            self.combo_ch.clear()
            for ch in range(self.flim.n_channels):
                nt = self.flim.n_time[ch] if ch < len(self.flim.n_time) else 0
                self.combo_ch.addItem(f"Channel {ch + 1} ({nt} bins)")
            self.combo_ch.setCurrentIndex(0)
            self.combo_ch.blockSignals(False)

            self.current_page = 0
            self.current_z = 0
            self.current_channel = 0
            self.roi = None

            # Auto-estimate intensity thresholds
            int_img = self.flim.get_intensity(0, 0, 0)
            nonzero = int_img[int_img > 0]
            if len(nonzero) > 0:
                p10, p99 = np.percentile(nonzero, 10), np.percentile(nonzero, 99)
                self.spin_int_min.setValue(max(1.0, float(p10)))
                self.spin_int_max.setValue(max(5.0, float(p99)))

            self.update_image_display()
            self.update_decay_display()
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"Failed to load file:\n{str(e)}")

    # ----------------- Sliders & Controls ----------------- #
    def _on_time_slider_changed(self, val: int):
        self.current_page = val
        time_str = self.flim.acq_times[val] if self.flim and val < len(self.flim.acq_times) else ""
        self.lbl_time_val.setText(f"{val + 1} / {self.flim.n_pages} ({time_str})")
        self.update_image_display()
        self.update_decay_display()

    def _on_z_slider_changed(self, val: int):
        self.current_z = val
        self.lbl_z_val.setText(f"{val + 1} / {self.flim.n_fast_z}")
        self.update_image_display()
        self.update_decay_display()

    def _on_channel_changed(self, idx: int):
        if idx >= 0:
            self.current_channel = idx
            self.update_image_display()
            self.update_decay_display()

    def _set_display_mode(self, mode: str):
        self.display_mode = mode
        self.update_image_display()

    # ----------------- Image Display ----------------- #
    def update_image_display(self):
        if self.flim is None:
            return

        self.img_ax.clear()
        self.img_ax.axis("off")

        lt_min = self.spin_lt_min.value()
        lt_max = self.spin_lt_max.value()
        int_min = self.spin_int_min.value()
        int_max = self.spin_int_max.value()

        if self.display_mode == "FLIM_RGB":
            rgb = self.flim.get_rgb_lifetime_map(
                self.current_page, self.current_z, self.current_channel,
                lt_limits=(lt_min, lt_max),
                int_limits=(int_min, int_max)
            )
            self.img_ax.imshow(rgb, interpolation="nearest")
        elif self.display_mode == "Lifetime":
            lt = self.flim.get_lifetime_map(
                self.current_page, self.current_z, self.current_channel
            )
            self.img_ax.imshow(lt, cmap="turbo", vmin=lt_min, vmax=lt_max, interpolation="nearest")
        else:
            intensity = self.flim.get_intensity(
                self.current_page, self.current_z, self.current_channel
            )
            self.img_ax.imshow(intensity, cmap="gray", vmin=int_min, vmax=int_max, interpolation="nearest")

        # Redraw ROI if present
        if self.roi is not None:
            ymin, ymax, xmin, xmax = self.roi
            rect = Rectangle(
                (xmin, ymin), xmax - xmin, ymax - ymin,
                linewidth=2, edgecolor="#00ffcc", facecolor="none", linestyle="--"
            )
            self.img_ax.add_patch(rect)

        self.img_canvas.draw_idle()

    # ----------------- Interactive ROI ----------------- #
    def _on_canvas_click(self, event):
        if event.inaxes != self.img_ax or event.button != 1:
            return
        self._dragging_roi = True
        self._roi_start = (int(event.ydata), int(event.xdata))

    def _on_canvas_drag(self, event):
        if not self._dragging_roi or event.inaxes != self.img_ax:
            return
        y0, x0 = self._roi_start
        y1, x1 = int(event.ydata), int(event.xdata)
        self.roi = (min(y0, y1), max(y0, y1), min(x0, x1), max(x0, x1))
        self.update_image_display()

    def _on_canvas_release(self, event):
        if not self._dragging_roi:
            return
        self._dragging_roi = False
        if self.roi is not None:
            ymin, ymax, xmin, xmax = self.roi
            if abs(ymax - ymin) < 2 or abs(xmax - xmin) < 2:
                # Single click: select 10x10 area around click
                h, w = self.flim.height, self.flim.width
                self.roi = (max(0, ymin - 5), min(h, ymin + 5), max(0, xmin - 5), min(w, xmin + 5))
                self.update_image_display()
        self.update_decay_display()

    def _clear_roi(self):
        self.roi = None
        self.update_image_display()
        self.update_decay_display()

    # ----------------- Decay Curve & Fitting ----------------- #
    def _get_current_mask(self) -> Optional[np.ndarray]:
        if self.flim is None or self.roi is None:
            return None
        ymin, ymax, xmin, xmax = self.roi
        mask = np.zeros((self.flim.height, self.flim.width), dtype=bool)
        mask[ymin:ymax, xmin:xmax] = True
        return mask

    def update_decay_display(self, fitted_res: Optional[dict] = None):
        if self.flim is None:
            return

        self.decay_ax.clear()
        self.res_ax.clear()

        mask = self._get_current_mask()
        time_ns, counts = self.flim.get_decay_curve(
            self.current_page, self.current_z, self.current_channel, mask=mask
        )

        label = "ROI Decay" if mask is not None else "Global Decay"
        self.decay_ax.plot(time_ns, counts, "o-", markersize=3, color="#1f77b4", label=label)

        if fitted_res is not None:
            fit_t = fitted_res["time_ns"]
            fit_y = fitted_res["fitted_curve"]
            self.decay_ax.plot(fit_t, fit_y, "r-", linewidth=2, label="Reconvolution Fit")

            # Residuals
            residuals = fitted_res["residuals"]
            self.res_ax.plot(fit_t, residuals, "k.-", markersize=3)
            self.res_ax.axhline(0, color="gray", linestyle="--", linewidth=1)
            self.res_ax.set_ylabel("Residuals")
            self.res_ax.set_xlabel("Time (ns)")
        else:
            self.res_ax.set_visible(False)

        if self.chk_semilog.isChecked():
            self.decay_ax.set_yscale("log")
            self.decay_ax.set_ylim(bottom=max(0.5, np.min(counts[counts > 0]) * 0.5) if np.any(counts > 0) else 1)

        self.decay_ax.set_ylabel("Photons")
        self.decay_ax.legend(loc="upper right", fontsize=9)
        self.decay_ax.grid(True, linestyle=":", alpha=0.6)
        self.res_ax.grid(True, linestyle=":", alpha=0.6)

        self.decay_canvas.draw_idle()

    def _run_fit(self):
        if self.flim is None:
            return

        mask = self._get_current_mask()
        time_ns, counts = self.flim.get_decay_curve(
            self.current_page, self.current_z, self.current_channel, mask=mask
        )

        n_exp = 1 if self.combo_model.currentIndex() == 0 else 2
        fitter = DecayFitter(n_exp=n_exp)

        try:
            res = fitter.fit(time_ns, counts)
            p = res["params"]

            summary = [f"=== {n_exp}-Exponential Reconvolution Fit ==="]
            summary.append(f"Reduced Chi^2: {res['red_chi2']:.3f} (Chi^2: {res['chi2']:.1f})")

            if n_exp == 1:
                summary.append(f"tau:   {p.get('tau1', 0.0):.3f} ns")
                summary.append(f"Amp:   {p.get('A1', 0.0):.1f}")
            else:
                summary.append(f"tau1:  {p.get('tau1', 0.0):.3f} ns | f1 (pop): {p.get('f1_pop', 0.0)*100:.1f}%")
                summary.append(f"tau2:  {p.get('tau2', 0.0):.3f} ns | f2 (pop): {p.get('f2_pop', 0.0)*100:.1f}%")
                summary.append(f"Mean tau (int): {p.get('tau_mean_int', 0.0):.3f} ns")
                summary.append(f"Mean tau (amp): {p.get('tau_mean_amp', 0.0):.3f} ns")

            summary.append(f"t0:    {p.get('t0', 0.0):.3f} ns | sigma: {p.get('sigma', 0.0):.3f} ns")
            summary.append(f"Bg:    {p.get('bg', 0.0):.2f}")

            self.txt_fit_results.setText("\n".join(summary))
            self.res_ax.set_visible(True)
            self.update_decay_display(fitted_res=res)
        except Exception as e:
            QMessageBox.warning(self, "Fitting Error", f"Curve fitting failed:\n{str(e)}")

    # ----------------- Exporting ----------------- #
    def _on_export_image(self):
        if self.flim is None:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Displayed Image", "flim_image.png", "PNG (*.png);;TIFF (*.tiff *.tif);;SVG (*.svg)"
        )
        if save_path:
            self.img_fig.savefig(save_path, dpi=300, bbox_inches="tight")
            QMessageBox.information(self, "Export Successful", f"Image exported to:\n{save_path}")

    def _on_export_decay(self):
        if self.flim is None:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Decay Curve", "decay_curve.csv", "CSV Files (*.csv)"
        )
        if save_path:
            mask = self._get_current_mask()
            time_ns, counts = self.flim.get_decay_curve(
                self.current_page, self.current_z, self.current_channel, mask=mask
            )
            data = np.column_stack([time_ns, counts])
            np.savetxt(save_path, data, delimiter=",", header="Time_ns,Photons", comments="")
            QMessageBox.information(self, "Export Successful", f"Decay curve exported to:\n{save_path}")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About FLIMage Viewer",
            "<h3>FLIMage Cross-Platform Viewer</h3>"
            "<p>High-performance viewer and analysis tool for FLIMage .flim files.</p>"
            "<p>Supports macOS (Apple Silicon & Intel) and Windows.</p>"
        )


def main():
    app = QApplication(sys.argv)
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    viewer = FLIMViewerGUI(initial_file)
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
