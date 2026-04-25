import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


APP_TITLE = "MP3 批量轉換工具"
APP_DIR_NAME = "MP3BatchConverter"
APP_VERSION = "1.0.1"
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a"}
SAMPLE_RATES = ["22050", "32000", "44100", "48000"]
BIT_RATES = ["32k", "64k", "96k", "128k", "160k", "192k", "256k", "320k"]
DEFAULT_CONFIG = {
    "source_dir": "",
    "destination_dir": "",
    "sample_rate": "44100",
    "bit_rate": "128k",
}
FFMPEG_INSTALL_HELP = (
    "找不到 ffmpeg。\n\n"
    "macOS（Homebrew）:\n"
    "  brew install ffmpeg\n\n"
    "Windows（winget）:\n"
    "  winget install Gyan.FFmpeg\n\n"
    "Ubuntu / Debian:\n"
    "  sudo apt update && sudo apt install ffmpeg\n\n"
    "安裝完成後，請重新開啟本程式。"
)
COMMON_FFMPEG_PATHS = [
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/opt/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
]


def get_storage_paths() -> Tuple[Path, Path]:
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
        log_dir = Path.home() / "Library" / "Logs" / APP_DIR_NAME
    else:
        base_dir = Path(__file__).resolve().parent
        log_dir = base_dir / "logs"

    base_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "config.json", log_dir


CONFIG_FILE, LOG_DIR = get_storage_paths()


def load_config() -> dict:
    legacy_config = Path(__file__).with_name("config.json")
    if not CONFIG_FILE.exists() and legacy_config.exists() and legacy_config != CONFIG_FILE:
        try:
            shutil.copy2(legacy_config, CONFIG_FILE)
        except OSError:
            pass

    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

    config = DEFAULT_CONFIG.copy()
    for key, value in DEFAULT_CONFIG.items():
        config[key] = data.get(key, value)

    if config["sample_rate"] not in SAMPLE_RATES:
        config["sample_rate"] = DEFAULT_CONFIG["sample_rate"]
    if config["bit_rate"] not in BIT_RATES:
        config["bit_rate"] = DEFAULT_CONFIG["bit_rate"]
    return config


def save_config(config: dict) -> None:
    with CONFIG_FILE.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)


def find_ffmpeg() -> Optional[str]:
    configured_path = os.environ.get("FFMPEG_PATH", "").strip()
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    discovered = shutil.which("ffmpeg")
    if discovered:
        return discovered

    for candidate_text in COMMON_FFMPEG_PATHS:
        candidate = Path(candidate_text)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    return None


def resolve_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


class ConversionWorker(QObject):
    started = pyqtSignal(int)
    progress = pyqtSignal(int, int, str, int, int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, source_dir: str, destination_dir: str, sample_rate: str, bit_rate: str) -> None:
        super().__init__()
        self.source_dir = Path(source_dir)
        self.destination_dir = Path(destination_dir)
        self.sample_rate = sample_rate
        self.bit_rate = bit_rate
        self.ffmpeg_path = find_ffmpeg() or "ffmpeg"
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True

    def run(self) -> None:
        files = sorted(
            path for path in self.source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        total = len(files)
        success_count = 0
        fail_count = 0
        skip_count = 0

        self.started.emit(total)

        if total == 0:
            self.finished.emit({
                "success": 0,
                "fail": 0,
                "skip": 0,
                "cancelled": False,
                "message": "來源資料夾中找不到可轉換的音訊檔。",
            })
            return

        for index, source_file in enumerate(files, start=1):
            if self.cancel_requested:
                self.finished.emit({
                    "success": success_count,
                    "fail": fail_count,
                    "skip": skip_count,
                    "cancelled": True,
                    "message": "轉換已取消。",
                })
                return

            relative_parent = source_file.relative_to(self.source_dir).parent
            target_dir = self.destination_dir / relative_parent
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                fail_count += 1
                self.log.emit(f"建立資料夾失敗：{target_dir}，原因：{exc}")
                self.progress.emit(index, total, str(source_file), success_count, fail_count, skip_count)
                continue

            target_name = f"CV_{source_file.stem}.mp3"
            target_path = resolve_unique_path(target_dir / target_name)
            command = [
                self.ffmpeg_path,
                "-y",
                "-i",
                str(source_file),
                "-ar",
                self.sample_rate,
                "-b:a",
                self.bit_rate,
                str(target_path),
            ]

            self.log.emit(f"開始轉換：{source_file} -> {target_path}")
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if completed.returncode == 0:
                success_count += 1
                self.log.emit(f"轉換成功：{target_path}")
            else:
                fail_count += 1
                error_message = completed.stderr.strip() or completed.stdout.strip() or "未知錯誤"
                self.log.emit(f"轉換失敗：{source_file}\n{error_message}")
                if target_path.exists():
                    try:
                        target_path.unlink()
                    except OSError:
                        pass

            self.progress.emit(index, total, str(source_file), success_count, fail_count, skip_count)

        self.finished.emit({
            "success": success_count,
            "fail": fail_count,
            "skip": skip_count,
            "cancelled": False,
            "message": "批量轉換完成。",
        })


class ConverterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.resize(900, 680)

        self.config = load_config()
        self.thread: Optional[QThread] = None
        self.worker: Optional[ConversionWorker] = None
        self.log_file_path: Optional[Path] = None

        self.source_edit = QLineEdit(self.config["source_dir"])
        self.destination_edit = QLineEdit(self.config["destination_dir"])
        self.sample_rate_combo = QComboBox()
        self.bit_rate_combo = QComboBox()
        self.status_label = QLabel("請先選擇來源與目的資料夾。")
        self.current_file_label = QLabel("目前檔案：")
        self.progress_label = QLabel("0 / 0")
        self.summary_label = QLabel("成功：0　失敗：0　略過：0")
        self.progress_bar = QProgressBar()
        self.log_output = QPlainTextEdit()
        self.start_button = QPushButton("開始轉換")
        self.cancel_button = QPushButton("取消轉換")
        self.source_button = QPushButton("選擇來源")
        self.destination_button = QPushButton("選擇目的地")

        self.build_ui()
        self.bind_events()
        self.apply_idle_state()

    def build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        form_group = QGroupBox("轉換設定")
        form_layout = QGridLayout(form_group)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(12)

        self.source_edit.setPlaceholderText("請選擇來源資料夾")
        self.destination_edit.setPlaceholderText("請選擇目的資料夾")

        self.sample_rate_combo.addItems(SAMPLE_RATES)
        self.sample_rate_combo.setCurrentText(self.config["sample_rate"])
        self.bit_rate_combo.addItems(BIT_RATES)
        self.bit_rate_combo.setCurrentText(self.config["bit_rate"])

        form_layout.addWidget(QLabel("來源資料夾"), 0, 0)
        form_layout.addWidget(self.source_edit, 0, 1)
        form_layout.addWidget(self.source_button, 0, 2)
        form_layout.addWidget(QLabel("目的資料夾"), 1, 0)
        form_layout.addWidget(self.destination_edit, 1, 1)
        form_layout.addWidget(self.destination_button, 1, 2)
        form_layout.addWidget(QLabel("取樣率"), 2, 0)
        form_layout.addWidget(self.sample_rate_combo, 2, 1, 1, 2)
        form_layout.addWidget(QLabel("位元率"), 3, 0)
        form_layout.addWidget(self.bit_rate_combo, 3, 1, 1, 2)
        form_layout.setColumnStretch(1, 1)

        progress_group = QGroupBox("轉換進度")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.current_file_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.summary_label)

        log_group = QGroupBox("訊息與錯誤")
        log_layout = QVBoxLayout(log_group)
        self.log_output.setReadOnly(True)
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout.addWidget(self.log_output)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)

        root_layout.addWidget(form_group)
        root_layout.addWidget(progress_group)
        root_layout.addWidget(log_group, 1)
        root_layout.addLayout(button_layout)

    def bind_events(self) -> None:
        self.source_button.clicked.connect(self.select_source_dir)
        self.destination_button.clicked.connect(self.select_destination_dir)
        self.start_button.clicked.connect(self.start_conversion)
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.sample_rate_combo.currentTextChanged.connect(self.persist_settings)
        self.bit_rate_combo.currentTextChanged.connect(self.persist_settings)
        self.source_edit.editingFinished.connect(self.persist_settings)
        self.destination_edit.editingFinished.connect(self.persist_settings)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_output.appendPlainText(line)

        if self.log_file_path:
            try:
                with self.log_file_path.open("a", encoding="utf-8") as file:
                    file.write(line + "\n")
            except OSError:
                pass

    def persist_settings(self) -> None:
        try:
            save_config({
                "source_dir": self.source_edit.text().strip(),
                "destination_dir": self.destination_edit.text().strip(),
                "sample_rate": self.sample_rate_combo.currentText(),
                "bit_rate": self.bit_rate_combo.currentText(),
            })
        except OSError as exc:
            self.append_log(f"設定檔儲存失敗：{exc}")

    def select_source_dir(self) -> None:
        initial = self.source_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "選擇來源資料夾", initial)
        if selected:
            self.source_edit.setText(selected)
            self.persist_settings()

    def select_destination_dir(self) -> None:
        initial = self.destination_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "選擇目的資料夾", initial)
        if selected:
            self.destination_edit.setText(selected)
            self.persist_settings()

    def validate_inputs(self) -> Tuple[bool, str]:
        source_dir_text = self.source_edit.text().strip()
        destination_dir_text = self.destination_edit.text().strip()

        if not find_ffmpeg():
            return False, FFMPEG_INSTALL_HELP
        if not source_dir_text:
            return False, "請先選擇來源資料夾。"
        if not destination_dir_text:
            return False, "請先選擇目的資料夾。"

        source_dir = Path(source_dir_text)
        destination_dir = Path(destination_dir_text)

        if not source_dir.exists() or not source_dir.is_dir():
            return False, "來源資料夾不存在或不是有效資料夾。"

        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return False, f"無法建立目的資料夾：{exc}"

        return True, ""

    def set_controls_enabled(self, enabled: bool) -> None:
        self.source_edit.setEnabled(enabled)
        self.destination_edit.setEnabled(enabled)
        self.source_button.setEnabled(enabled)
        self.destination_button.setEnabled(enabled)
        self.sample_rate_combo.setEnabled(enabled)
        self.bit_rate_combo.setEnabled(enabled)
        self.start_button.setEnabled(enabled)
        self.cancel_button.setEnabled(not enabled)

    def apply_idle_state(self) -> None:
        self.set_controls_enabled(True)
        self.cancel_button.setEnabled(False)

    def start_conversion(self) -> None:
        valid, message = self.validate_inputs()
        if not valid:
            QMessageBox.critical(self, "無法開始轉換", message)
            self.append_log(message)
            return

        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "轉換中", "目前已有轉換工作正在執行。")
            return

        self.persist_settings()
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_file_path = LOG_DIR / f"convert_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.progress_bar.setValue(0)
        self.progress_label.setText("0 / 0")
        self.summary_label.setText("成功：0　失敗：0　略過：0")
        self.status_label.setText("準備開始轉換...")
        self.current_file_label.setText("目前檔案：")
        self.append_log("開始新一輪批量轉換。")
        self.set_controls_enabled(False)

        self.thread = QThread()
        self.worker = ConversionWorker(
            self.source_edit.text().strip(),
            self.destination_edit.text().strip(),
            self.sample_rate_combo.currentText(),
            self.bit_rate_combo.currentText(),
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.started.connect(self.on_worker_started)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.cleanup_thread)
        self.thread.start()

    def cancel_conversion(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("正在取消，請稍候...")
            self.append_log("已收到取消要求，將在目前檔案處理完成後停止。")

    def on_worker_started(self, total: int) -> None:
        self.progress_label.setText(f"0 / {total}")
        self.status_label.setText(f"共找到 {total} 個檔案，開始轉換中...")
        self.append_log(f"已掃描到 {total} 個可轉換檔案。")

    def on_worker_progress(
        self,
        index: int,
        total: int,
        current_file: str,
        success_count: int,
        fail_count: int,
        skip_count: int,
    ) -> None:
        percent = int((index / total) * 100) if total else 0
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{index} / {total}")
        self.current_file_label.setText(f"目前檔案：{current_file}")
        self.summary_label.setText(
            f"成功：{success_count}　失敗：{fail_count}　略過：{skip_count}"
        )
        self.status_label.setText("轉換進行中...")

    def on_worker_finished(self, result: dict) -> None:
        if not result["cancelled"] and (result["success"] + result["fail"] + result["skip"]):
            self.progress_bar.setValue(100)

        self.summary_label.setText(
            f"成功：{result['success']}　失敗：{result['fail']}　略過：{result['skip']}"
        )
        self.status_label.setText(result["message"])
        self.current_file_label.setText("目前檔案：")
        self.append_log(result["message"])
        self.set_controls_enabled(True)

        QMessageBox.information(
            self,
            "轉換結果",
            f"{result['message']}\n成功：{result['success']}\n失敗：{result['fail']}\n略過：{result['skip']}",
        )

    def cleanup_thread(self) -> None:
        self.thread = None
        self.worker = None


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)
    window = ConverterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
