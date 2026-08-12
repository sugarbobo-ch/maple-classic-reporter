import os
import time
import logging
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget, QCheckBox,
    QProgressDialog, QDialog, QDialogButtonBox, QInputDialog, QScrollArea
)

from maple_reporter import __version__
from maple_reporter.utils.config import get_recordings_dir, get_user_app_data_dir
from maple_reporter.recorder.window_recorder import (
    get_active_window_titles, focus_window
)
from maple_reporter.recorder.audio_capture import (
    get_audio_output_devices,
    get_default_audio_output_name,
)
from maple_reporter.gdrive.drive_service import GoogleDriveManager
from maple_reporter.automation.playwright_runtime import PlaywrightBrowserError
from maple_reporter.gui.overlay import ScreenSnipperOverlay
from maple_reporter.gui.preview_modal import ReportPreviewModal
from maple_reporter.gui.playwright_error_dialog import show_playwright_error_dialog
from maple_reporter.gui.evidence_capture_controller import EvidenceCaptureController
from maple_reporter.gui.history_controller import HistoryController
from maple_reporter.gui.replay_controller import ReplayController
from maple_reporter.gui.settings_controller import SettingsController
from maple_reporter.gui.submission_controller import SubmissionController


LOGGER = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"新楓之谷：經典版《自動外掛檢舉工具》｜v{__version__}｜快速啟動版"
        )
        self.resize(900, 650)

        self.settings_controller = SettingsController()
        self.cfg = self.settings_controller.config
        self.history_controller = HistoryController()
        self.capture_controller = EvidenceCaptureController()
        self.replay_controller = ReplayController(self)
        self.submission_controller = SubmissionController(self)
        self.drive_mgr = GoogleDriveManager()
        # Keep the attribute name for integrations that access the recorder,
        # while lifecycle ownership now belongs to ReplayController.
        self.replay_recorder = self.replay_controller.recorder
        self.replay_recorder.state_changed.connect(self.on_replay_state_changed)
        self.replay_recorder.replay_saved.connect(self.on_replay_saved)
        self.replay_recorder.error_occurred.connect(self.on_replay_error)
        self.replay_recorder.warning_occurred.connect(self.on_replay_warning)
        self.replay_recorder.audio_source_changed.connect(
            self.on_replay_audio_source_changed
        )
        self.submission_controller.finished.connect(self.on_submission_finished)
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

        row_local_folder = QHBoxLayout()
        row_local_folder.addWidget(QLabel("本機專案資料夾："))
        self.txt_app_data_dir = QLineEdit(str(get_user_app_data_dir()))
        self.txt_app_data_dir.setReadOnly(True)
        self.txt_app_data_dir.setToolTip(
            "程式設定、歷史紀錄、錄影與受保護設定的本機位置"
        )
        self.btn_open_app_data_folder = QPushButton("開啟專案資料夾")
        self.btn_open_app_data_folder.setToolTip(
            f"在檔案總管開啟 {get_user_app_data_dir()}"
        )
        self.btn_open_app_data_folder.setAccessibleName("開啟專案本機資料夾")
        self.btn_open_app_data_folder.clicked.connect(self.open_app_data_folder)
        row_local_folder.addWidget(self.txt_app_data_dir, 1)
        row_local_folder.addWidget(self.btn_open_app_data_folder)
        g1_layout.addLayout(row_local_folder)

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

        row_audio = QHBoxLayout()
        row_audio.addWidget(QLabel("系統聲音來源："))
        self.combo_audio_output = QComboBox()
        self.combo_audio_output.setAccessibleName("系統聲音錄製來源")
        self.combo_audio_output.setToolTip("選擇目前實際播放遊戲聲音的 Windows 輸出裝置")
        self.combo_audio_output.currentIndexChanged.connect(
            self.on_audio_output_changed
        )
        self.btn_refresh_audio = QPushButton("重新整理音訊裝置")
        self.btn_refresh_audio.clicked.connect(self.refresh_audio_devices)
        row_audio.addWidget(self.combo_audio_output, 1)
        row_audio.addWidget(self.btn_refresh_audio)
        g2_layout.addLayout(row_audio)
        self.chk_record_audio.toggled.connect(self.on_record_audio_toggled)

        hint = QLabel("一般錄影會在按下後開始；下方的回放緩衝會持續保留最近一段畫面。")
        hint.setObjectName("hint")
        g2_layout.addWidget(hint)

        replay_group = QGroupBox("回放緩衝設定")
        replay_layout = QVBoxLayout(replay_group)
        replay_layout.setSpacing(10)

        replay_settings = QHBoxLayout()
        replay_settings.addWidget(QLabel("保留最近："))
        self.spin_replay_seconds = QSpinBox()
        self.spin_replay_seconds.setRange(10, 60)
        self.spin_replay_seconds.setValue(30)
        self.spin_replay_seconds.setSuffix(" 秒")
        self.spin_replay_seconds.setAccessibleName("回放緩衝秒數")
        replay_settings.addWidget(self.spin_replay_seconds)
        replay_settings.addSpacing(12)
        replay_settings.addWidget(QLabel("快速選擇："))
        self.combo_replay_seconds = QComboBox()
        for seconds in (10, 15, 30, 45, 60):
            self.combo_replay_seconds.addItem(f"{seconds} 秒", seconds)
        self.combo_replay_seconds.addItem("自訂", None)
        self.combo_replay_seconds.setCurrentIndex(
            self.combo_replay_seconds.findData(30)
        )
        self.combo_replay_seconds.setAccessibleName("快速選擇回放緩衝秒數")
        self.combo_replay_seconds.setToolTip("快速套用常用的回放緩衝長度")
        replay_settings.addWidget(self.combo_replay_seconds)
        replay_settings.addStretch()
        replay_layout.addLayout(replay_settings)

        self.lbl_replay_hint = QLabel(
            "功能說明：啟動後會像滑動時間線一樣，持續保留最近一段畫面與聲音；"
            "超過設定秒數的內容會自動淘汰。按下「儲存最近片段」只會保存當下時間窗，"
            "不會停止或重設背景緩衝。"
        )
        self.lbl_replay_hint.setWordWrap(True)
        self.lbl_replay_hint.setObjectName("hint")
        replay_layout.addWidget(self.lbl_replay_hint)
        self.spin_replay_seconds.valueChanged.connect(self.on_replay_seconds_changed)
        self.combo_replay_seconds.currentIndexChanged.connect(
            self.on_replay_preset_changed
        )
        g2_layout.addWidget(replay_group)

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
        g4_layout = QVBoxLayout(g4)

        replay_status_row = QHBoxLayout()
        self.lbl_replay_status = QLabel("● 未啟動")
        self.lbl_replay_status.setAccessibleName("回放緩衝狀態")
        self.lbl_replay_status.setStyleSheet("color: #616161; font-weight: bold;")
        self.lbl_replay_time = QLabel("00:00 / 00:30")
        self.lbl_replay_time.setAccessibleName("目前可儲存的回放長度")
        replay_status_row.addWidget(QLabel("回放緩衝："))
        replay_status_row.addWidget(self.lbl_replay_status)
        replay_status_row.addStretch()
        replay_status_row.addWidget(self.lbl_replay_time)
        g4_layout.addLayout(replay_status_row)

        self.lbl_replay_audio_source = QLabel("音訊來源：尚未選擇")
        self.lbl_replay_audio_source.setObjectName("hint")
        self.lbl_replay_audio_source.setAccessibleName("回放緩衝音訊來源")
        g4_layout.addWidget(self.lbl_replay_audio_source)

        replay_actions = QHBoxLayout()
        self.btn_toggle_replay = QPushButton("啟動回放緩衝")
        self.btn_toggle_replay.setMinimumHeight(44)
        self.btn_toggle_replay.setToolTip("持續保留所選遊戲視窗最近的畫面與聲音")
        self.btn_toggle_replay.clicked.connect(self.toggle_replay_buffer)
        self.btn_save_replay = QPushButton("儲存最近片段")
        self.btn_save_replay.setMinimumHeight(44)
        self.btn_save_replay.setEnabled(False)
        self.btn_save_replay.setToolTip("儲存目前時間窗；背景緩衝不會停止或重設")
        self.btn_save_replay.clicked.connect(self.save_replay_segment)
        replay_actions.addWidget(self.btn_toggle_replay)
        replay_actions.addWidget(self.btn_save_replay, 1)
        g4_layout.addLayout(replay_actions)

        capture_actions = QHBoxLayout()

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

        capture_actions.addWidget(self.btn_trigger_snip)
        capture_actions.addWidget(self.btn_trigger_video)
        capture_actions.addWidget(self.btn_select_file)
        g4_layout.addLayout(capture_actions)
        control_layout.addWidget(g4)

        control_scroll = QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        control_scroll.setWidget(tab_control)
        self.tabs.addTab(control_scroll, "回報設定")

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

    def open_app_data_folder(self):
        folder = get_user_app_data_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                raise OSError("Windows 檔案總管無法開啟資料夾")
        except (OSError, RuntimeError) as error:
            LOGGER.warning("開啟專案資料夾失敗 (%s)", type(error).__name__)
            QMessageBox.warning(
                self,
                "無法開啟專案資料夾",
                f"請手動開啟以下路徑：\n{folder}",
            )

    def on_history_cell_clicked(self, row: int, column: int):
        self.history_controller.open_url_from_cell(self.table_history, row, column)

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
        self.settings_controller.apply_to_window(self)

    def load_templates(self):
        self.settings_controller.load_templates(self)

    def apply_selected_template(self):
        self.settings_controller.apply_selected_template(self)

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
        self.settings_controller.mark_onboarding_completed()

    def trigger_snipping(self):
        self.hide()
        time.sleep(0.3)
        self.snipper_overlay.start_snipping()

    def on_snippet_captured(self, pil_img, bounds):
        self.show()
        # Save the already-cropped PIL image from overlay directly (do NOT re-screenshot with mss,
        # as the main window would then be visible and obscure the game capture).
        file_path = self.capture_controller.save_snippet(pil_img)

        from maple_reporter.ocr.ocr_worker import OcrWorkerThread
        api_key = self.txt_gemini_key.text().strip()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread([pil_img], api_key=api_key, whitelist=wl_list, parent=self)
        ocr_thread.finished.connect(ocr_thread.release_keyframes)
        ocr_thread.finished.connect(ocr_thread.deleteLater)

        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        data = {
            "suspect_id": "",
            "candidate_ids": [],
            "server_name": self.combo_server.currentText(),
            "map_name": "",
            "default_map_name": self.txt_map.text().strip(),
            "note": self.txt_note.text().strip(),
            "evidence_url": "",
            "file_path": file_path,
            "file_origin": "generated",
        }

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()
        modal.dispose_when_idle()

    def toggle_replay_buffer(self):
        if self.replay_controller.is_running:
            self.replay_controller.stop()
            return

        win_title = self.combo_windows.currentText().strip()
        if not win_title:
            QMessageBox.warning(self, "無法啟動回放緩衝", "請先選擇目標遊戲視窗。")
            return
        selected_audio_device_id = self.combo_audio_output.currentData() or ""
        self.cfg["record_audio"] = self.chk_record_audio.isChecked()
        self.cfg["audio_output_device_id"] = selected_audio_device_id
        self.settings_controller.save_model()
        if not self.chk_record_audio.isChecked():
            self.lbl_replay_audio_source.setText("音訊來源：未錄製系統聲音")
        self.replay_controller.start(
            win_title,
            fps=int(self.combo_fps.currentData()),
            buffer_seconds=self.spin_replay_seconds.value(),
            record_audio=self.chk_record_audio.isChecked(),
            audio_device_id=selected_audio_device_id or None,
        )

    def refresh_audio_devices(self, preferred_device_id=None):
        if isinstance(preferred_device_id, bool):
            preferred_device_id = self.combo_audio_output.currentData() or ""
        preferred_device_id = str(preferred_device_id or "")
        default_name = get_default_audio_output_name()

        self.combo_audio_output.blockSignals(True)
        self.combo_audio_output.clear()
        self.combo_audio_output.addItem(f"系統預設（{default_name}）", "")
        for device_id, name in get_audio_output_devices():
            self.combo_audio_output.addItem(name, device_id)
        selected_index = self.combo_audio_output.findData(preferred_device_id)
        if preferred_device_id and selected_index < 0:
            self.combo_audio_output.addItem(
                "先前選擇的音訊裝置目前未連線", preferred_device_id
            )
            selected_index = self.combo_audio_output.count() - 1
        self.combo_audio_output.setCurrentIndex(max(0, selected_index))
        self.combo_audio_output.blockSignals(False)
        self.on_record_audio_toggled(self.chk_record_audio.isChecked())
        self.update_audio_source_label()

    def on_audio_output_changed(self, _index: int):
        self.cfg["audio_output_device_id"] = (
            self.combo_audio_output.currentData() or ""
        )
        self.settings_controller.save_model()
        self.update_audio_source_label()

    def update_audio_source_label(self):
        if not hasattr(self, "lbl_replay_audio_source"):
            return
        if not self.chk_record_audio.isChecked():
            text = "音訊來源：未錄製系統聲音"
        else:
            device_name = self.combo_audio_output.currentText().strip()
            text = f"音訊來源：{device_name or '找不到可用裝置'}"
        self.lbl_replay_audio_source.setText(text)
        self.lbl_replay_audio_source.setAccessibleDescription(text)

    def on_record_audio_toggled(self, enabled: bool):
        editable = enabled and not self.replay_controller.is_running
        self.combo_audio_output.setEnabled(editable)
        self.btn_refresh_audio.setEnabled(editable)
        self.update_audio_source_label()

    def on_replay_audio_source_changed(self, device_name: str):
        text = f"正在錄製音訊：{device_name}"
        self.lbl_replay_audio_source.setText(text)
        self.lbl_replay_audio_source.setAccessibleDescription(text)

    def on_replay_seconds_changed(self, _value: int):
        preset_index = self.combo_replay_seconds.findData(_value)
        if preset_index < 0:
            preset_index = self.combo_replay_seconds.count() - 1
        self.combo_replay_seconds.blockSignals(True)
        self.combo_replay_seconds.setCurrentIndex(preset_index)
        self.combo_replay_seconds.blockSignals(False)
        if not self.replay_controller.is_running:
            self.on_replay_state_changed("idle", 0.0)

    def on_replay_preset_changed(self, _index: int):
        seconds = self.combo_replay_seconds.currentData()
        if seconds is not None:
            self.spin_replay_seconds.setValue(int(seconds))

    def save_replay_segment(self):
        if not self.replay_controller.save():
            QMessageBox.information(
                self,
                "片段尚未就緒",
                "請先啟動回放緩衝並等待至少幾秒，再儲存最近片段。",
            )

    def on_replay_state_changed(self, state: str, duration: float):
        total = self.spin_replay_seconds.value()
        elapsed = min(total, max(0, int(duration)))

        def clock(seconds: int) -> str:
            return f"{seconds // 60:02d}:{seconds % 60:02d}"

        self.lbl_replay_time.setText(f"{clock(elapsed)} / {clock(total)}")
        self.lbl_replay_time.setAccessibleDescription(
            f"已緩衝 {elapsed} 秒，共可保留 {total} 秒"
        )

        running_states = {"warming", "ready", "saving", "stopping"}
        running = state in running_states
        saving = state == "saving"
        self.combo_windows.setEnabled(not running)
        self.btn_refresh_wins.setEnabled(not running)
        self.combo_fps.setEnabled(not running)
        self.chk_record_audio.setEnabled(not running)
        self.combo_audio_output.setEnabled(not running and self.chk_record_audio.isChecked())
        self.btn_refresh_audio.setEnabled(not running and self.chk_record_audio.isChecked())
        self.spin_replay_seconds.setEnabled(not running)
        self.combo_replay_seconds.setEnabled(not running)
        self.btn_toggle_replay.setEnabled(state not in {"saving", "stopping"})

        if state == "idle":
            self.update_audio_source_label()
            self.lbl_replay_status.setText("● 未啟動")
            self.lbl_replay_status.setStyleSheet("color: #616161; font-weight: bold;")
            self.btn_toggle_replay.setText("啟動回放緩衝")
            self.btn_save_replay.setText("儲存最近片段")
            self.btn_save_replay.setEnabled(False)
        elif state == "warming":
            self.lbl_replay_status.setText("● 正在建立緩衝")
            self.lbl_replay_status.setStyleSheet("color: #ad6800; font-weight: bold;")
            self.btn_toggle_replay.setText("停止回放緩衝")
            self.btn_save_replay.setText("儲存目前片段")
            self.btn_save_replay.setEnabled(duration >= 3.0)
        elif state == "ready":
            self.lbl_replay_status.setText("● 可儲存最近片段")
            self.lbl_replay_status.setStyleSheet("color: #1b5e20; font-weight: bold;")
            self.btn_toggle_replay.setText("停止回放緩衝")
            self.btn_save_replay.setText(f"儲存最近 {total} 秒")
            self.btn_save_replay.setEnabled(True)
        elif state == "saving":
            self.lbl_replay_status.setText("● 正在儲存片段，緩衝持續中")
            self.lbl_replay_status.setStyleSheet("color: #0d47a1; font-weight: bold;")
            self.btn_toggle_replay.setText("停止回放緩衝")
            self.btn_save_replay.setText("正在儲存片段…")
            self.btn_save_replay.setEnabled(False)
        elif state == "stopping":
            self.lbl_replay_status.setText("● 正在停止回放緩衝")
            self.lbl_replay_status.setStyleSheet("color: #616161; font-weight: bold;")
            self.btn_toggle_replay.setText("正在停止…")
            self.btn_save_replay.setText("無法儲存")
            self.btn_save_replay.setEnabled(False)
        elif state == "error":
            self.lbl_replay_status.setText("● 回放緩衝發生錯誤")
            self.lbl_replay_status.setStyleSheet("color: #b71c1c; font-weight: bold;")
            self.btn_toggle_replay.setText("重新啟動回放緩衝")
            self.btn_save_replay.setText("無法儲存")
            self.btn_save_replay.setEnabled(False)

        self.lbl_replay_status.setAccessibleDescription(self.lbl_replay_status.text())

    def on_replay_saved(self, file_path: str, keyframes):
        self.open_generated_video_preview(file_path, keyframes)

    def on_replay_error(self, message: str):
        if not self.replay_controller.is_running:
            self.replay_controller.stop()
        QMessageBox.warning(self, "回放緩衝", message)

    def on_replay_warning(self, message: str):
        QMessageBox.information(self, "回放緩衝音訊", message)

    def open_generated_video_preview(self, file_path: str, keyframes):
        from maple_reporter.ocr.ocr_worker import OcrWorkerThread

        api_key = self.txt_gemini_key.text().strip()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]
        ocr_thread = OcrWorkerThread(
            keyframes, api_key=api_key, whitelist=wl_list, parent=self
        )
        ocr_thread.finished.connect(ocr_thread.release_keyframes)
        ocr_thread.finished.connect(ocr_thread.deleteLater)
        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        data = {
            "suspect_id": "",
            "candidate_ids": [],
            "server_name": self.combo_server.currentText(),
            "map_name": "",
            "default_map_name": self.txt_map.text().strip(),
            "note": self.txt_note.text().strip(),
            "evidence_url": "",
            "file_path": file_path,
            "file_origin": "generated",
        }
        modal = ReportPreviewModal(
            data,
            drive_mgr=self.drive_mgr,
            folder_name=folder_name,
            discord_webhook_url=self.txt_discord_webhook.text(),
            upload_destination=self.combo_upload_destination.currentData(),
            ocr_thread=ocr_thread,
            parent=self,
        )
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()
        modal.dispose_when_idle()

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
        file_path, keyframes = self.capture_controller.record_video(
            win_title,
            duration_sec=duration,
            fps=fps,
            progress_callback=update_progress,
            cancel_checker=lambda: progress.wasCanceled(),
            record_audio=self.chk_record_audio.isChecked(),
            audio_device_id=self.combo_audio_output.currentData() or None,
        )

        user_canceled = progress.wasCanceled()
        progress.close()

        if user_canceled or not file_path:
            return

        self.open_generated_video_preview(file_path, keyframes)

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

        keyframes = self.capture_controller.load_keyframes(file_path)
        if not keyframes:
            QMessageBox.warning(self, "讀取失敗", "無法從本機事證讀取可辨識的影格。")
            return

        from maple_reporter.ocr.ocr_worker import OcrWorkerThread
        api_key = self.txt_gemini_key.text().strip()
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread(keyframes, api_key=api_key, whitelist=wl_list, parent=self)
        ocr_thread.finished.connect(ocr_thread.release_keyframes)
        ocr_thread.finished.connect(ocr_thread.deleteLater)

        folder_name = self.txt_gdrive_folder.text().strip() or "MapleClassic_Reports"
        data = {
            "suspect_id": "",
            "candidate_ids": [],
            "server_name": self.combo_server.currentText(),
            "map_name": "",
            "default_map_name": self.txt_map.text().strip(),
            "note": self.txt_note.text().strip(),
            "evidence_url": "",
            "file_path": file_path,
            "file_origin": "imported",
        }

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()
        modal.dispose_when_idle()

    def save_settings(self):
        """Persist all current UI field values to config.json."""
        self.settings_controller.save_from_window(self)
        self.btn_save_settings.setText("已儲存")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.btn_save_settings.setText("儲存設定"))

    def execute_submission(self, confirmed_data: dict):
        self.txt_map.setText(confirmed_data.get("map_name", "維多利亞島"))
        self.settings_controller.save_from_window(self)
        if not self.submission_controller.submit(confirmed_data):
            QMessageBox.information(self, "送出中", "已有另一筆表單正在送出，請稍候。")

    def clear_all_recordings(self):
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
                except OSError as error:
                    LOGGER.warning(
                        "清理錄影檔案失敗 (%s: %s)", f.name, type(error).__name__
                    )
            QMessageBox.information(self, "清理完成", f"已成功刪除 {deleted} 個檔案！")

    def closeEvent(self, event):
        """Persist local settings, including the masked Gemini key, on exit."""
        self.replay_controller.stop()
        self.save_settings()
        event.accept()

    def on_submission_finished(self, ok: bool, msg: str, error, data: dict):
        status_str = "成功" if ok else "失敗"
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "suspect_id": data["suspect_id"],
            "server": data["server_name"],
            "map": data["map_name"],
            "url": data.get("evidence_url", ""),
            "status": status_str
        }
        self.history_controller.add(entry)
        self.refresh_history_table()

        if ok:
            if self.chk_auto_delete.isChecked() and SubmissionController.can_delete_evidence(
                data, form_confirmed=True
            ):
                SubmissionController.delete_confirmed_evidence(data)
            QMessageBox.information(self, "成功", msg)
        elif isinstance(error, PlaywrightBrowserError):
            show_playwright_error_dialog(self, error)
        else:
            QMessageBox.critical(self, "失敗", msg)

    def refresh_history_table(self):
        self.history_controller.refresh_table(self.table_history)
