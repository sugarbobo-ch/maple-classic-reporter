import os
import sys
import time
import threading
import cv2
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget, QCheckBox,
    QProgressDialog, QDialog, QDialogButtonBox, QInputDialog
)

from maple_reporter import __version__
from maple_reporter.utils.config import load_config, save_config, load_history, add_history_entry
from maple_reporter.ocr.win_ocr import recognize_text_from_image, recognize_candidates_from_image_list
from maple_reporter.recorder.window_recorder import (
    get_active_window_titles, capture_screenshot, record_short_video, focus_window
)
from maple_reporter.gdrive.drive_service import GoogleDriveManager
from maple_reporter.automation.form_filler import submit_gamania_report
from maple_reporter.automation.playwright_runtime import PlaywrightBrowserError
from maple_reporter.gui.overlay import ScreenSnipperOverlay
from maple_reporter.gui.preview_modal import ReportPreviewModal
from maple_reporter.gui.playwright_error_dialog import show_playwright_error_dialog

class SubmitThread(QThread):
    finished_signal = Signal(bool, str, object)

    def __init__(self, data: dict):
        super().__init__()
        self.data = data

    def run(self):
        try:
            success, msg = submit_gamania_report(
                suspect_id=self.data["suspect_id"],
                server_name=self.data["server_name"],
                map_name=self.data["map_name"],
                note=self.data["note"],
                evidence_url=self.data.get("evidence_url", ""),
                headless=False
            )
        except PlaywrightBrowserError as error:
            self.finished_signal.emit(False, error.details.summary, error)
            return
        self.finished_signal.emit(success, msg, None)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"新楓之谷：經典版《自動外掛檢舉工具》 v{__version__}")
        self.resize(900, 650)

        self.cfg = load_config()
        self.drive_mgr = GoogleDriveManager(self.cfg.get("gdrive_token_file"))
        self.snipper_overlay = ScreenSnipperOverlay()
        self.snipper_overlay.snippet_captured.connect(self.on_snippet_captured)

        self.setup_ui()
        self.load_settings_to_ui()
        self.refresh_history_table()
        if not self.cfg.get("onboarding_completed", False):
            self.show_onboarding()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Control & Settings
        tab_control = QWidget()
        control_layout = QVBoxLayout(tab_control)

        # Group 1: Evidence storage
        g1 = QGroupBox("事證上傳設定")
        g1_layout = QVBoxLayout(g1)

        row_auth = QHBoxLayout()
        self.lbl_gdrive_status = QLabel("狀態: 未驗證")
        self.lbl_gdrive_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_gdrive_login = QPushButton("連結 Google 帳號")
        self.btn_gdrive_login.clicked.connect(self.on_gdrive_login)
        row_auth.addWidget(self.lbl_gdrive_status)
        row_auth.addStretch()
        row_auth.addWidget(self.btn_gdrive_login)
        g1_layout.addLayout(row_auth)

        row_folder = QHBoxLayout()
        row_folder.addWidget(QLabel("雲端儲存資料夾名稱:"))
        self.txt_gdrive_folder = QLineEdit("MapleClassic_Reports")
        self.txt_gdrive_folder.setPlaceholderText("例如: MapleClassic_Reports 或 新楓之谷檢舉事證")
        self.btn_open_gdrive_folder = QPushButton("前往雲端資料夾")
        self.btn_open_gdrive_folder.setStyleSheet("""
            QPushButton {
                background-color: #0288d1;
                color: white;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0277bd; }
        """)
        self.btn_open_gdrive_folder.clicked.connect(self.open_gdrive_folder)
        row_folder.addWidget(self.txt_gdrive_folder, 1)
        row_folder.addWidget(self.btn_open_gdrive_folder)
        g1_layout.addLayout(row_folder)

        row_destination = QHBoxLayout()
        row_destination.addWidget(QLabel("上傳目的地："))
        self.combo_upload_destination = QComboBox()
        self.combo_upload_destination.addItem("Google Drive（建議用於官方審查）", "gdrive")
        self.combo_upload_destination.addItem("Discord（短片快速分享）", "discord")
        row_destination.addWidget(self.combo_upload_destination, 1)
        g1_layout.addLayout(row_destination)

        row_discord = QHBoxLayout()
        row_discord.addWidget(QLabel("Discord Webhook URL："))
        self.txt_discord_webhook = QLineEdit()
        self.txt_discord_webhook.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_discord_webhook.setPlaceholderText("設定後每次送出前都必須完成 Discord 備份")
        row_discord.addWidget(self.txt_discord_webhook, 1)
        g1_layout.addLayout(row_discord)

        control_layout.addWidget(g1)

        # Group 2: Capture Settings
        g2 = QGroupBox("錄影設定")
        g2_layout = QVBoxLayout(g2)

        row_win = QHBoxLayout()
        row_win.addWidget(QLabel("選擇目標遊戲視窗:"))
        self.combo_windows = QComboBox()
        self.btn_refresh_wins = QPushButton("重新整理")
        self.btn_refresh_wins.clicked.connect(self.refresh_window_list)
        row_win.addWidget(self.combo_windows, 1)
        row_win.addWidget(self.btn_refresh_wins)
        g2_layout.addLayout(row_win)

        row_rec = QHBoxLayout()
        row_rec.addWidget(QLabel("錄製秒數："))
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(3, 60)
        self.spin_duration.setValue(8)
        self.spin_duration.setSuffix(" 秒")
        row_rec.addWidget(self.spin_duration)

        row_rec.addWidget(QLabel("FPS："))
        self.combo_fps = QComboBox()
        for fps in (15, 20, 24, 30, 45, 60):
            self.combo_fps.addItem(f"{fps} FPS", fps)
        row_rec.addWidget(self.combo_fps)

        row_rec.addWidget(QLabel("錄影前倒數："))
        self.spin_countdown = QSpinBox()
        self.spin_countdown.setRange(0, 10)
        self.spin_countdown.setValue(3)
        self.spin_countdown.setSuffix(" 秒")
        row_rec.addWidget(self.spin_countdown)

        row_rec.addStretch()
        g2_layout.addLayout(row_rec)

        row_opts = QHBoxLayout()
        self.chk_record_audio = QCheckBox("同步錄製系統聲音 (Audio)")
        self.chk_auto_delete = QCheckBox("上傳成功後自動刪除本機事證檔案")
        self.btn_clear_recordings = QPushButton("一鍵清理所有錄製檔案")
        self.btn_clear_recordings.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #c62828; }
        """)
        self.btn_clear_recordings.clicked.connect(self.clear_all_recordings)
        row_opts.addWidget(self.chk_record_audio)
        row_opts.addWidget(self.chk_auto_delete)
        row_opts.addStretch()
        row_opts.addWidget(self.btn_clear_recordings)
        g2_layout.addLayout(row_opts)

        hint = QLabel("較長錄影可取得更多 OCR 影格；同時會增加檔案大小與上傳時間。")
        hint.setObjectName("hint")
        g2_layout.addWidget(hint)

        control_layout.addWidget(g2)

        # Group 3: Default Form Values
        g3 = QGroupBox("表單與辨識設定")
        g3_layout = QVBoxLayout(g3)

        row_s = QHBoxLayout()
        row_s.addWidget(QLabel("預設伺服器:"))
        self.combo_server = QComboBox()
        self.combo_server.addItems(["雪吉拉", "菇菇寶貝"])
        row_s.addWidget(self.combo_server)

        row_s.addWidget(QLabel("預設地圖名稱:"))
        self.txt_map = QLineEdit("維多利亞島")
        row_s.addWidget(self.txt_map, 1)
        g3_layout.addLayout(row_s)

        row_n = QHBoxLayout()
        row_n.addWidget(QLabel("違規說明範本："))
        self.combo_template = QComboBox()
        self.combo_template.currentIndexChanged.connect(self.apply_selected_template)
        row_n.addWidget(self.combo_template, 1)
        self.btn_manage_templates = QPushButton("管理範本")
        self.btn_manage_templates.clicked.connect(self.manage_templates)
        row_n.addWidget(self.btn_manage_templates)
        self.txt_note = QLineEdit("自動打怪/外掛行為")
        self.txt_note.setPlaceholderText("可在這裡微調本次預設內容")
        row_n.addWidget(self.txt_note, 2)
        g3_layout.addLayout(row_n)

        row_ai = QHBoxLayout()
        row_ai.addWidget(QLabel("Gemini API Key（選填）："))
        self.txt_gemini_key = QLineEdit()
        self.txt_gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_gemini_key.setPlaceholderText("可填入 Gemini API 金鑰提升 99%+ 辨識率 (留空則使用 RapidOCR 本地引擎)...")
        row_ai.addWidget(self.txt_gemini_key, 1)
        g3_layout.addLayout(row_ai)

        row_wl = QHBoxLayout()
        row_wl.addWidget(QLabel("ID 白名單（以逗號分隔）："))
        self.txt_whitelist = QLineEdit()
        self.txt_whitelist.setPlaceholderText("可填入自己或隊友 ID（以逗號分隔），將自動從候選清單中過濾...")
        row_wl.addWidget(self.txt_whitelist, 1)
        g3_layout.addLayout(row_wl)

        control_layout.addWidget(g3)

        # Group 3.5: Save Settings Button
        row_save = QHBoxLayout()
        self.btn_save_settings = QPushButton("儲存設定")
        self.btn_save_settings.setStyleSheet("""
            QPushButton {
                background-color: #5c6bc0;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 20px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #3949ab; }
        """)
        self.btn_save_settings.clicked.connect(self.save_settings)
        row_save.addStretch()
        row_save.addWidget(self.btn_save_settings)
        control_layout.addLayout(row_save)

        g4 = QGroupBox("建立回報")
        g4_layout = QHBoxLayout(g4)

        self.btn_trigger_snip = QPushButton("擷取畫面並辨識")
        self.btn_trigger_snip.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                font-size: 15px;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        self.btn_trigger_snip.clicked.connect(self.trigger_snipping)

        self.btn_trigger_video = QPushButton("錄製影片並辨識")
        self.btn_trigger_video.setStyleSheet("""
            QPushButton {
                background-color: #e65100;
                color: white;
                font-weight: bold;
                font-size: 15px;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #ef6c00; }
        """)
        self.btn_trigger_video.clicked.connect(self.trigger_video_report)
        self.btn_select_file = QPushButton("選擇本機事證")
        self.btn_select_file.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                font-size: 15px;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1b5e20; }
        """)
        self.btn_select_file.clicked.connect(self.trigger_local_file_report)

        g4_layout.addWidget(self.btn_trigger_snip)
        g4_layout.addWidget(self.btn_trigger_video)
        g4_layout.addWidget(self.btn_select_file)
        control_layout.addWidget(g4)

        self.tabs.addTab(tab_control, "回報設定")

        # Tab 2: History
        tab_history = QWidget()
        history_layout = QVBoxLayout(tab_history)

        self.table_history = QTableWidget()
        self.table_history.setColumnCount(6)
        self.table_history.setHorizontalHeaderLabels([
            "時間", "外掛 ID", "伺服器", "地圖", "GDrive 網址", "狀態"
        ])
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_history.cellClicked.connect(self.on_history_cell_clicked)
        self.table_history.cellDoubleClicked.connect(self.on_history_cell_clicked)
        history_layout.addWidget(self.table_history)

        self.tabs.addTab(tab_history, "歷史紀錄")

        # Update GDrive UI Status
        self.update_gdrive_ui()

    def open_gdrive_folder(self):
        import webbrowser
        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        if self.drive_mgr.is_authenticated():
            url = self.drive_mgr.get_folder_url(folder_name)
            if url:
                webbrowser.open(url)
                return
        webbrowser.open("https://drive.google.com/drive/my-drive")

    def on_history_cell_clicked(self, row: int, column: int):
        if column == 4:
            item = self.table_history.item(row, column)
            if item and item.text().strip().startswith("http"):
                import webbrowser
                webbrowser.open(item.text().strip())

    def update_gdrive_ui(self):
        if self.drive_mgr.is_authenticated():
            self.lbl_gdrive_status.setText("狀態：已授權 Google 帳號")
            self.lbl_gdrive_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_gdrive_login.setText("重新驗證 Google 帳號")
        else:
            self.lbl_gdrive_status.setText("狀態：未綁定")
            self.lbl_gdrive_status.setStyleSheet("color: red; font-weight: bold;")
            self.btn_gdrive_login.setText("連結 Google 帳號")

    def on_gdrive_login(self):
        ok, msg = self.drive_mgr.authenticate_interactive()
        if ok:
            QMessageBox.information(self, "Google 驗證", msg)
        else:
            QMessageBox.warning(self, "Google 驗證失敗", msg)
        self.update_gdrive_ui()

    def refresh_window_list(self):
        titles = get_active_window_titles()
        # Filter out tool's own window
        titles = [
            t for t in titles
            if "maplestory classic auto reporter" not in t.lower() and "自動外掛檢舉工具" not in t
        ]
        self.combo_windows.clear()
        self.combo_windows.addItems(titles)

        selected_idx = -1

        # Priority 1: "新楓之谷：經典版"
        for i, t in enumerate(titles):
            if "新楓之谷：經典版" in t:
                selected_idx = i
                break

        # Priority 2: "新楓之谷"
        if selected_idx == -1:
            for i, t in enumerate(titles):
                if "新楓之谷" in t:
                    selected_idx = i
                    break

        # Priority 3: "maple" or "楓"
        if selected_idx == -1:
            for i, t in enumerate(titles):
                if "maple" in t.lower() or "楓" in t:
                    selected_idx = i
                    break

        # Priority 4: Saved config title
        if selected_idx == -1 and self.cfg.get("selected_window_title"):
            saved_title = self.cfg.get("selected_window_title")
            for i, t in enumerate(titles):
                if t == saved_title:
                    selected_idx = i
                    break

        if selected_idx != -1:
            self.combo_windows.setCurrentIndex(selected_idx)
        elif titles:
            self.combo_windows.setCurrentIndex(0)

    def load_settings_to_ui(self):
        self.refresh_window_list()
        self.combo_server.setCurrentText(self.cfg.get("default_server", "雪吉拉"))
        self.txt_map.setText(self.cfg.get("default_map", "維多利亞島"))
        self.load_templates()
        self.spin_duration.setValue(self.cfg.get("record_duration_sec", 8))
        fps_index = self.combo_fps.findData(self.cfg.get("record_fps", 20))
        self.combo_fps.setCurrentIndex(max(0, fps_index))
        self.spin_countdown.setValue(self.cfg.get("record_countdown_sec", 3))
        self.txt_gdrive_folder.setText(self.cfg.get("gdrive_folder_name", "MapleClassic_Reports"))
        self.txt_gemini_key.setText(self.cfg.get("gemini_api_key", ""))
        self.txt_discord_webhook.setText(self.cfg.get("discord_webhook_url", ""))
        destination_index = self.combo_upload_destination.findData(self.cfg.get("upload_destination", "gdrive"))
        self.combo_upload_destination.setCurrentIndex(max(0, destination_index))
        wl = self.cfg.get("whitelist", [])
        self.txt_whitelist.setText(", ".join(wl) if isinstance(wl, list) else str(wl))
        self.chk_auto_delete.setChecked(self.cfg.get("auto_delete_after_upload", False))
        self.chk_record_audio.setChecked(self.cfg.get("record_audio", True))

    def load_templates(self):
        templates = self.cfg.get("violation_templates", [])
        if not templates:
            templates = [{"name": "自動打怪／外掛行為", "content": self.cfg.get("default_note", "自動打怪/外掛行為")}]
            self.cfg["violation_templates"] = templates
        self.combo_template.blockSignals(True)
        self.combo_template.clear()
        for item in templates:
            self.combo_template.addItem(item.get("name", "未命名範本"), item.get("content", ""))
        self.combo_template.blockSignals(False)
        self.apply_selected_template()

    def apply_selected_template(self):
        content = self.combo_template.currentData()
        if content is not None:
            self.txt_note.setText(str(content))

    def manage_templates(self):
        action, ok = QInputDialog.getItem(self, "管理違規範本", "選擇操作：", ["新增", "編輯目前範本", "刪除目前範本"], 0, False)
        if not ok:
            return
        templates = list(self.cfg.get("violation_templates", []))
        index = self.combo_template.currentIndex()
        if action == "新增":
            name, ok = QInputDialog.getText(self, "新增範本", "範本名稱：")
            if not ok or not name.strip(): return
            content, ok = QInputDialog.getText(self, "新增範本", "違規說明：")
            if not ok or not content.strip(): return
            templates.append({"name": name.strip(), "content": content.strip()})
        elif action == "編輯目前範本" and index >= 0:
            name, ok = QInputDialog.getText(self, "編輯範本", "範本名稱：", text=templates[index]["name"])
            if not ok or not name.strip(): return
            content, ok = QInputDialog.getText(self, "編輯範本", "違規說明：", text=templates[index]["content"])
            if not ok or not content.strip(): return
            templates[index] = {"name": name.strip(), "content": content.strip()}
        elif action == "刪除目前範本" and index >= 0:
            if len(templates) == 1:
                QMessageBox.warning(self, "無法刪除", "至少要保留一個違規範本。")
                return
            templates.pop(index)
        self.cfg["violation_templates"] = templates
        self.load_templates()

    def show_onboarding(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("開始使用")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("新楓之谷檢舉助手"))
        guide = QLabel("1. 選擇上傳目的地並完成帳號或 Webhook 設定。\n2. 選擇遊戲視窗與錄影品質。\n3. 錄製或匯入事證，確認 OCR 結果後送出。")
        guide.setWordWrap(True)
        layout.addWidget(guide)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("開始設定")
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()
        self.cfg["onboarding_completed"] = True
        save_config(self.cfg)

    def trigger_snipping(self):
        self.hide()
        time.sleep(0.3)
        self.snipper_overlay.start_snipping()

    def on_snippet_captured(self, pil_img, bounds):
        self.show()
        # Save the already-cropped PIL image from overlay directly (do NOT re-screenshot with mss,
        # as the main window would then be visible and obscure the game capture).
        from maple_reporter.utils.config import get_recordings_dir
        import time as _time
        rec_dir = str(get_recordings_dir())
        file_path = os.path.join(rec_dir, f"maple_evidence_{int(_time.time())}.png")
        pil_img.convert("RGB").save(file_path)

        from maple_reporter.ocr.ocr_worker import OcrWorkerThread
        api_key = self.txt_gemini_key.text().strip()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread([pil_img], api_key=api_key, whitelist=wl_list, parent=self)

        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        data = {
            "suspect_id": "",
            "candidate_ids": [],
            "server_name": self.combo_server.currentText(),
            "map_name": self.txt_map.text().strip(),
            "note": self.txt_note.text().strip(),
            "evidence_url": "",
            "file_path": file_path
        }

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()

    def trigger_video_report(self):
        win_title = self.combo_windows.currentText()
        if not win_title:
            QMessageBox.warning(self, "警告", "請先選擇目標遊戲視窗！")
            return

        duration = self.spin_duration.value()
        fps = int(self.combo_fps.currentData())
        countdown = self.spin_countdown.value()

        # Focus game window
        focus_window(win_title)

        # Countdown phase
        if countdown > 0:
            from PySide6.QtCore import QCoreApplication
            progress_cd = QProgressDialog(f"準備錄影中，倒數 {countdown} 秒", "取消", 0, countdown, self)
            progress_cd.setWindowTitle("錄影倒數計時")
            progress_cd.setWindowModality(Qt.WindowModality.WindowModal)
            progress_cd.setAutoReset(False)
            progress_cd.setAutoClose(False)
            progress_cd.show()

            for i in range(countdown, 0, -1):
                if progress_cd.wasCanceled():
                    progress_cd.close()
                    return
                progress_cd.setLabelText(f"倒數 {i} 秒後開始錄製遊戲視窗")
                progress_cd.setValue(countdown - i)
                QCoreApplication.processEvents()
                time.sleep(1)
            progress_cd.close()

        # Re-focus right before grabbing video
        focus_window(win_title)

        progress = QProgressDialog(f"正在錄製遊戲視窗（{duration} 秒 @ {fps} FPS）", "取消", 0, 100, self)
        progress.setWindowTitle("錄影中")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoReset(False)
        progress.setAutoClose(False)
        progress.show()

        def update_progress(val):
            progress.setValue(int(val * 100))
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()

        # Record video and extract keyframes
        file_path, keyframes = record_short_video(
            win_title,
            duration_sec=duration,
            fps=fps,
            progress_callback=update_progress,
            cancel_checker=lambda: progress.wasCanceled(),
            record_audio=self.chk_record_audio.isChecked()
        )

        user_canceled = progress.wasCanceled()
        progress.close()

        if user_canceled or not file_path:
            return

        # Open the preview immediately; the background worker runs local OCR only.
        from maple_reporter.ocr.ocr_worker import OcrWorkerThread
        api_key = self.txt_gemini_key.text().strip()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread(keyframes, api_key=api_key, whitelist=wl_list, parent=self)

        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        data = {
            "suspect_id": "",
            "candidate_ids": [],
            "server_name": self.combo_server.currentText(),
            "map_name": self.txt_map.text().strip(),
            "note": self.txt_note.text().strip(),
            "evidence_url": "",
            "file_path": file_path
        }

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()

    def trigger_local_file_report(self):
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇本地影片或圖片檔案進行 OCR 與檢舉",
            "",
            "媒體檔案 (*.mp4 *.mkv *.avi *.mov *.png *.jpg *.jpeg);;所有檔案 (*.*)"
        )
        if not file_path or not os.path.exists(file_path):
            return

        ext = os.path.splitext(file_path)[1].lower()
        keyframes = []

        if ext in [".mp4", ".mkv", ".avi", ".mov"]:
            import cv2
            cap = cv2.VideoCapture(file_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 20
            step = max(1, int(fps * 1.5))
            frame_idx = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % step == 0:
                    keyframes.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                frame_idx += 1
            cap.release()
        else:
            try:
                keyframes = [Image.open(file_path)]
            except Exception as e:
                QMessageBox.warning(self, "讀取失敗", f"無法開啟圖片檔案: {str(e)}")
                return

        from maple_reporter.ocr.ocr_worker import OcrWorkerThread
        api_key = self.txt_gemini_key.text().strip()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread(keyframes, api_key=api_key, whitelist=wl_list, parent=self)

        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        data = {
            "suspect_id": "",
            "candidate_ids": [],
            "server_name": self.combo_server.currentText(),
            "map_name": self.txt_map.text().strip(),
            "note": self.txt_note.text().strip(),
            "evidence_url": "",
            "file_path": file_path
        }

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()

    def save_settings(self):
        """Persist all current UI field values to config.json."""
        self.cfg["default_server"] = self.combo_server.currentText()
        self.cfg["default_map"] = self.txt_map.text().strip()
        self.cfg["default_note"] = self.txt_note.text().strip()
        self.cfg["selected_window_title"] = self.combo_windows.currentText()
        self.cfg["record_duration_sec"] = self.spin_duration.value()
        self.cfg["record_fps"] = int(self.combo_fps.currentData())
        self.cfg["record_countdown_sec"] = self.spin_countdown.value()
        self.cfg["gdrive_folder_name"] = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        self.cfg["gemini_api_key"] = self.txt_gemini_key.text().strip()
        self.cfg["discord_webhook_url"] = self.txt_discord_webhook.text().strip()
        self.cfg["upload_destination"] = self.combo_upload_destination.currentData()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]
        self.cfg["whitelist"] = wl_list
        self.cfg["auto_delete_after_upload"] = self.chk_auto_delete.isChecked()
        self.cfg["record_audio"] = self.chk_record_audio.isChecked()
        save_config(self.cfg)
        self.btn_save_settings.setText("已儲存")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.btn_save_settings.setText("儲存設定"))

    def execute_submission(self, confirmed_data: dict):
        self.cfg["default_server"] = confirmed_data.get("server_name", "雪吉拉")
        self.cfg["default_map"] = confirmed_data.get("map_name", "維多利亞島")
        self.txt_map.setText(self.cfg["default_map"])
        self.cfg["default_note"] = confirmed_data.get("note", "自動打怪/外掛行為")
        self.cfg["selected_window_title"] = self.combo_windows.currentText()
        self.cfg["record_duration_sec"] = self.spin_duration.value()
        self.cfg["record_fps"] = int(self.combo_fps.currentData())
        self.cfg["record_countdown_sec"] = self.spin_countdown.value()
        self.cfg["gdrive_folder_name"] = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        self.cfg["gemini_api_key"] = self.txt_gemini_key.text().strip()
        self.cfg["discord_webhook_url"] = self.txt_discord_webhook.text().strip()
        self.cfg["upload_destination"] = self.combo_upload_destination.currentData()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]
        self.cfg["whitelist"] = wl_list
        self.cfg["auto_delete_after_upload"] = self.chk_auto_delete.isChecked()
        save_config(self.cfg)
        self.submit_thread = SubmitThread(confirmed_data)
        self.submit_thread.finished_signal.connect(
            lambda ok, msg, error: self.on_submission_finished(ok, msg, confirmed_data, error)
        )
        self.submit_thread.start()

    def clear_all_recordings(self):
        from maple_reporter.utils.config import get_recordings_dir
        rec_dir = get_recordings_dir()
        files = [f for f in rec_dir.iterdir() if f.is_file()]
        if not files:
            QMessageBox.information(self, "清理檔案", "本機錄影資料夾中目前沒有任何檔案。")
            return

        reply = QMessageBox.question(
            self,
            "確認清理檔案",
            f"確定要刪除錄影資料夾中的 {len(files)} 個檔案嗎？此操作無法復原。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted = 0
            for f in files:
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass
            QMessageBox.information(self, "清理完成", f"已成功刪除 {deleted} 個檔案！")

    def closeEvent(self, event):
        """Persist local settings, including the masked Gemini key, on exit."""
        self.save_settings()
        event.accept()

    def on_submission_finished(self, ok: bool, msg: str, data: dict, error=None):
        status_str = "成功" if ok else "失敗"
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "suspect_id": data["suspect_id"],
            "server": data["server_name"],
            "map": data["map_name"],
            "url": data.get("evidence_url", ""),
            "status": status_str
        }
        add_history_entry(entry)
        self.refresh_history_table()

        if ok:
            if self.chk_auto_delete.isChecked():
                file_path = data.get("file_path")
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            QMessageBox.information(self, "成功", msg)
        elif isinstance(error, PlaywrightBrowserError):
            show_playwright_error_dialog(self, error)
        else:
            QMessageBox.critical(self, "失敗", msg)

    def refresh_history_table(self):
        history = load_history()
        self.table_history.setRowCount(len(history))
        for row, item in enumerate(history):
            self.table_history.setItem(row, 0, QTableWidgetItem(item.get("time", "")))
            self.table_history.setItem(row, 1, QTableWidgetItem(item.get("suspect_id", "")))
            self.table_history.setItem(row, 2, QTableWidgetItem(item.get("server", "")))
            self.table_history.setItem(row, 3, QTableWidgetItem(item.get("map", "")))

            url_text = item.get("url", "")
            url_item = QTableWidgetItem(url_text)
            if url_text.startswith("http"):
                url_item.setForeground(Qt.GlobalColor.blue)
                font = url_item.font()
                font.setUnderline(True)
                url_item.setFont(font)
                url_item.setToolTip("點擊前往開啟雲端事證網址")
            self.table_history.setItem(row, 4, url_item)
            self.table_history.setItem(row, 5, QTableWidgetItem(item.get("status", "")))
