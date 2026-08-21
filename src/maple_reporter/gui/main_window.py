import os
import time
import math
import logging
from PySide6.QtCore import QCoreApplication, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QTabWidget, QCheckBox,
    QProgressBar, QDialog, QDialogButtonBox, QInputDialog, QScrollArea
)

from maple_reporter import __version__
from maple_reporter.utils.config import (
    get_recordings_dir,
    get_user_app_data_dir,
)
from maple_reporter.recorder.window_recorder import (
    focus_window, get_active_window_titles
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
from maple_reporter.gui.quick_links_controller import QuickLinksController
from maple_reporter.gui.replay_controller import ReplayController
from maple_reporter.gui.settings_controller import SettingsController
from maple_reporter.gui.submission_controller import SubmissionController
from maple_reporter.gui.widgets import WheelSafeComboBox
from maple_reporter.platform.global_hotkeys import (
    ACTION_RECORD_VIDEO,
    ACTION_SAVE_REPLAY,
    DEFAULT_RECORD_VIDEO_HOTKEY,
    DEFAULT_RECORD_VIDEO_KEY,
    DEFAULT_SAVE_REPLAY_HOTKEY,
    DEFAULT_SAVE_REPLAY_KEY,
    GlobalHotkeyManager,
    HOTKEY_KEY_OPTIONS,
    fixed_hotkey_for_key,
    hotkey_key_from_shortcut,
)


LOGGER = logging.getLogger(__name__)

VIDEO_TRIGGER_DEFAULT_STYLE = """
    QPushButton {
        background-color: #e65100;
        color: white;
        font-weight: bold;
        font-size: 15px;
        padding: 12px;
        border-radius: 6px;
    }
    QPushButton:hover { background-color: #ef6c00; }
"""

VIDEO_TRIGGER_ACTIVE_STYLE = """
    QPushButton {
        background-color: #757575;
        color: white;
        font-weight: bold;
        font-size: 15px;
        padding: 12px;
        border-radius: 6px;
    }
    QPushButton:hover { background-color: #616161; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            f"新楓之谷：經典版《自動外掛檢舉工具》｜v{__version__}"
        )
        self.resize(900, 650)

        self.settings_controller = SettingsController()
        self.cfg = self.settings_controller.config
        self.history_controller = HistoryController()
        self.quick_links_controller = QuickLinksController(self.cfg)
        self.capture_controller = EvidenceCaptureController()
        self.replay_controller = ReplayController(self)
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.hotkey_manager.activated.connect(self.on_global_hotkey)
        self.hotkey_manager.registration_changed.connect(
            self.on_hotkey_registration_changed
        )
        self._hotkey_statuses = {}
        self._hotkey_recording_active = False
        self._video_workflow_active = False
        self._video_cancel_requested = False
        self._video_progress_value = 0
        self._replay_save_workflow_active = False
        self._closing = False
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
        self.configure_global_hotkeys()
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
        g1 = QGroupBox("檢舉證據上傳設定")
        g1_layout = QVBoxLayout(g1)

        row_auth = QHBoxLayout()
        self.lbl_gdrive_status = QLabel("狀態：尚未登入")
        self.lbl_gdrive_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_gdrive_login = QPushButton("登入 Google 帳號")
        self.btn_gdrive_login.clicked.connect(self.on_gdrive_login)
        row_auth.addWidget(self.lbl_gdrive_status)
        row_auth.addStretch()
        row_auth.addWidget(self.btn_gdrive_login)
        g1_layout.addLayout(row_auth)

        row_folder = QHBoxLayout()
        row_folder.addWidget(QLabel("雲端儲存資料夾名稱:"))
        self.txt_gdrive_folder = QLineEdit("MapleClassic_Reports")
        self.txt_gdrive_folder.setPlaceholderText("例如: MapleClassic_Reports 或 新楓之谷檢舉證據")
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
        self.combo_upload_destination = WheelSafeComboBox()
        self.combo_upload_destination.addItem("Google Drive（建議用於官方審查）", "gdrive")
        self.combo_upload_destination.addItem("Discord（影片快速分享）", "discord")
        row_destination.addWidget(self.combo_upload_destination, 1)
        g1_layout.addLayout(row_destination)

        row_discord = QHBoxLayout()
        row_discord.addWidget(QLabel("Discord 頻道連結："))
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
        self.combo_windows = WheelSafeComboBox()
        self.btn_refresh_wins = QPushButton("重新整理")
        self.btn_refresh_wins.clicked.connect(self.refresh_window_list)
        row_win.addWidget(self.combo_windows, 1)
        row_win.addWidget(self.btn_refresh_wins)
        g2_layout.addLayout(row_win)

        row_rec = QHBoxLayout()
        row_rec.addWidget(QLabel("錄影秒數："))
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(3, 60)
        self.spin_duration.setValue(8)
        self.spin_duration.setSuffix(" 秒")
        row_rec.addWidget(self.spin_duration)

        row_rec.addWidget(QLabel("FPS："))
        self.combo_fps = WheelSafeComboBox()
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
        self.chk_record_audio = QCheckBox("同步錄音 (Audio)")
        self.chk_auto_delete = QCheckBox("上傳成功後自動刪除本機檢舉證據檔案")
        self.btn_clear_recordings = QPushButton("一鍵清理所有影片檔案")
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

        ocr_group = QGroupBox("文字辨識（OCR）自動帶入")
        ocr_layout = QVBoxLayout(ocr_group)
        self.chk_ocr_autofill = QCheckBox("啟用文字辨識（OCR）自動帶入")
        self.chk_ocr_autofill.setTristate(True)
        self.chk_ocr_autofill.setChecked(True)
        self.chk_ocr_autofill.setAccessibleName("啟用文字辨識（OCR）自動帶入")
        self.chk_ocr_autofill.setToolTip(
            "控制是否將辨識到的角色 ID 與地圖名稱自動帶入預覽表單；"
            "部分勾選代表只啟用其中一項。"
        )
        ocr_layout.addWidget(self.chk_ocr_autofill)

        ocr_fields = QHBoxLayout()
        ocr_fields.addSpacing(24)
        self.chk_ocr_id = QCheckBox("角色 ID")
        self.chk_ocr_id.setChecked(True)
        self.chk_ocr_id.setAccessibleName("啟用角色 ID 自動帶入")
        self.chk_ocr_id.setToolTip("啟用後，自動辨識並帶入外掛玩家角色 ID")
        self.chk_ocr_map = QCheckBox("地圖名稱")
        self.chk_ocr_map.setChecked(True)
        self.chk_ocr_map.setAccessibleName("啟用地圖名稱自動帶入")
        self.chk_ocr_map.setToolTip("啟用後，自動辨識並帶入所在地圖名稱")
        self.chk_ocr_id.toggled.connect(self._on_ocr_autofill_child_toggled)
        self.chk_ocr_map.toggled.connect(self._on_ocr_autofill_child_toggled)
        self.chk_ocr_autofill.stateChanged.connect(
            self._on_ocr_autofill_master_changed
        )
        ocr_fields.addWidget(self.chk_ocr_id)
        ocr_fields.addWidget(self.chk_ocr_map)
        ocr_fields.addStretch()
        ocr_layout.addLayout(ocr_fields)
        g2_layout.addWidget(ocr_group)
        self.sync_ocr_autofill_checkboxes()

        row_audio = QHBoxLayout()
        row_audio.addWidget(QLabel("系統聲音來源："))
        self.combo_audio_output = WheelSafeComboBox()
        self.combo_audio_output.setAccessibleName("系統聲音來源")
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

        hint = QLabel("一般錄影會在按下後開始；下方的循環錄影會持續保留最近一段畫面。")
        hint.setObjectName("hint")
        g2_layout.addWidget(hint)

        replay_group = QGroupBox("循環錄影設定")
        replay_layout = QVBoxLayout(replay_group)
        replay_layout.setSpacing(10)

        replay_settings = QHBoxLayout()
        replay_settings.addWidget(QLabel("保留最近："))
        self.spin_replay_seconds = QSpinBox()
        self.spin_replay_seconds.setRange(10, 60)
        self.spin_replay_seconds.setValue(30)
        self.spin_replay_seconds.setSuffix(" 秒")
        self.spin_replay_seconds.setAccessibleName("循環錄影保留秒數")
        replay_settings.addWidget(self.spin_replay_seconds)
        replay_settings.addSpacing(12)
        replay_settings.addWidget(QLabel("快速選擇："))
        self.combo_replay_seconds = WheelSafeComboBox()
        for seconds in (10, 15, 30, 45, 60):
            self.combo_replay_seconds.addItem(f"{seconds} 秒", seconds)
        self.combo_replay_seconds.addItem("自訂", None)
        self.combo_replay_seconds.setCurrentIndex(
            self.combo_replay_seconds.findData(30)
        )
        self.combo_replay_seconds.setAccessibleName("快速選擇循環錄影保留秒數")
        self.combo_replay_seconds.setToolTip("快速套用常用的循環錄影保留時間")
        replay_settings.addWidget(self.combo_replay_seconds)
        replay_settings.addStretch()
        replay_layout.addLayout(replay_settings)

        self.lbl_replay_hint = QLabel(
            "功能說明：啟動後會像滑動時間線一樣，持續保留最近一段畫面與聲音；"
            "超過設定秒數的內容會自動淘汰。按下「儲存最近片段」只會保存當下時間窗，"
            "最後 5 秒會加密取樣截圖，增加事件尾端的辨識機會；"
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

        hotkey_group = QGroupBox("全域快捷鍵")
        hotkey_layout = QVBoxLayout(hotkey_group)
        hotkey_layout.setSpacing(8)

        self.chk_global_hotkeys = QCheckBox("啟用全域快捷鍵")
        self.chk_global_hotkeys.setAccessibleName("啟用全域快捷鍵")
        self.chk_global_hotkeys.setToolTip(
            "遊戲視窗在前景時仍可使用快捷鍵；快捷鍵不會攔截遊戲的其他按鍵。"
        )
        hotkey_layout.addWidget(self.chk_global_hotkeys)

        row_save_hotkey = QHBoxLayout()
        row_save_hotkey.addWidget(QLabel("儲存最近片段：Ctrl + Shift +"))
        self.combo_save_replay_hotkey_key = WheelSafeComboBox()
        for key in HOTKEY_KEY_OPTIONS:
            self.combo_save_replay_hotkey_key.addItem(key, key)
        self.combo_save_replay_hotkey_key.setCurrentIndex(
            self.combo_save_replay_hotkey_key.findData(DEFAULT_SAVE_REPLAY_KEY)
        )
        self.combo_save_replay_hotkey_key.setAccessibleName(
            "儲存最近片段第三個鍵位"
        )
        self.combo_save_replay_hotkey_key.setToolTip(
            "Ctrl 與 Shift 固定，請選擇最後一個鍵位。"
        )
        row_save_hotkey.addWidget(self.combo_save_replay_hotkey_key, 1)
        hotkey_layout.addLayout(row_save_hotkey)

        row_record_hotkey = QHBoxLayout()
        row_record_hotkey.addWidget(QLabel("開始一般錄影：Ctrl + Shift +"))
        self.combo_record_video_hotkey_key = WheelSafeComboBox()
        for key in HOTKEY_KEY_OPTIONS:
            self.combo_record_video_hotkey_key.addItem(key, key)
        self.combo_record_video_hotkey_key.setCurrentIndex(
            self.combo_record_video_hotkey_key.findData(DEFAULT_RECORD_VIDEO_KEY)
        )
        self.combo_record_video_hotkey_key.setAccessibleName(
            "開始一般錄影第三個鍵位"
        )
        self.combo_record_video_hotkey_key.setToolTip(
            "Ctrl 與 Shift 固定，請選擇最後一個鍵位。"
        )
        row_record_hotkey.addWidget(self.combo_record_video_hotkey_key, 1)
        hotkey_layout.addLayout(row_record_hotkey)

        self.lbl_hotkey_status = QLabel("尚未註冊")
        self.lbl_hotkey_status.setObjectName("hint")
        self.lbl_hotkey_status.setAccessibleName("全域快捷鍵狀態")
        hotkey_layout.addWidget(self.lbl_hotkey_status)
        self.lbl_hotkey_hint = QLabel(
            "第一次按 F9 會啟動循環錄影；累積幾秒後再次按 F9 儲存影片片段。"
            "按住快捷鍵不會重複觸發。"
        )
        self.lbl_hotkey_hint.setWordWrap(True)
        self.lbl_hotkey_hint.setObjectName("hint")
        self.lbl_hotkey_hint.setAccessibleName("全域快捷鍵使用說明")
        hotkey_layout.addWidget(self.lbl_hotkey_hint)
        self.chk_global_hotkeys.toggled.connect(
            self.on_global_hotkeys_enabled_toggled
        )
        g2_layout.addWidget(hotkey_group)

        control_layout.addWidget(g2)

        # Group 3: Default Form Values
        g3 = QGroupBox("表單與辨識設定")
        g3_layout = QVBoxLayout(g3)

        row_s = QHBoxLayout()
        row_s.addWidget(QLabel("預設伺服器:"))
        self.combo_server = WheelSafeComboBox()
        self.combo_server.addItems(["雪吉拉", "菇菇寶貝"])
        row_s.addWidget(self.combo_server)

        row_s.addWidget(QLabel("預設地圖名稱:"))
        self.txt_map = QLineEdit("")
        row_s.addWidget(self.txt_map, 1)
        g3_layout.addLayout(row_s)

        row_n = QHBoxLayout()
        row_n.addWidget(QLabel("違規說明範本："))
        self.combo_template = WheelSafeComboBox()
        self.combo_template.currentIndexChanged.connect(self.apply_selected_template)
        row_n.addWidget(self.combo_template, 1)
        self.btn_manage_templates = QPushButton("管理範本")
        self.btn_manage_templates.clicked.connect(self.manage_templates)
        row_n.addWidget(self.btn_manage_templates)
        self.txt_note = QLineEdit("自動打怪/外掛行為")
        self.txt_note.setPlaceholderText("可在這裡微調本次預設內容")
        row_n.addWidget(self.txt_note, 2)
        g3_layout.addLayout(row_n)

        row_submission = QHBoxLayout()
        self.chk_form_submit_headless = QCheckBox("背景靜默送出檢舉")
        self.chk_form_submit_headless.setToolTip(
            "啟用時由 Playwright 在背景填寫官方表單；關閉時開啟可見瀏覽器。"
        )
        self.chk_dev_mode = QCheckBox("開發者模式 (Dry-Run)")
        self.chk_dev_mode.setToolTip(
            "啟用時不會真正送出官方表單，只記錄測試歷史並開啟表單網址。"
        )
        row_submission.addWidget(self.chk_form_submit_headless)
        row_submission.addWidget(self.chk_dev_mode)
        row_submission.addStretch()
        g3_layout.addLayout(row_submission)

        row_wl = QHBoxLayout()
        row_wl.addWidget(QLabel("ID 略過名單（白名單，以逗號分隔）："))
        self.txt_whitelist = QLineEdit()
        self.txt_whitelist.setPlaceholderText("可填入自己或隊友 ID（以逗號分隔），將自動從候選清單中過濾...")
        row_wl.addWidget(self.txt_whitelist, 1)
        g3_layout.addLayout(row_wl)

        control_layout.addWidget(g3)

        quick_links_group = QGroupBox("快捷連結")
        quick_links_layout = QVBoxLayout(quick_links_group)
        self.table_quick_links = QTableWidget()
        self.table_quick_links.setColumnCount(2)
        self.table_quick_links.setHorizontalHeaderLabels(["名稱", "URL"])
        self.table_quick_links.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_quick_links.setMinimumHeight(130)
        self.table_quick_links.cellDoubleClicked.connect(
            lambda row, _column: self.open_quick_link(row)
        )
        quick_links_layout.addWidget(self.table_quick_links)

        quick_link_actions = QHBoxLayout()
        self.btn_add_quick_link = QPushButton("新增")
        self.btn_add_quick_link.clicked.connect(self.add_quick_link)
        self.btn_edit_quick_link = QPushButton("編輯")
        self.btn_edit_quick_link.clicked.connect(self.edit_quick_link)
        self.btn_delete_quick_link = QPushButton("刪除")
        self.btn_delete_quick_link.clicked.connect(self.delete_quick_link)
        self.btn_move_quick_link_up = QPushButton("上移")
        self.btn_move_quick_link_up.clicked.connect(
            lambda: self.move_quick_link(-1)
        )
        self.btn_move_quick_link_down = QPushButton("下移")
        self.btn_move_quick_link_down.clicked.connect(
            lambda: self.move_quick_link(1)
        )
        self.btn_open_quick_link = QPushButton("開啟")
        self.btn_open_quick_link.clicked.connect(self.open_selected_quick_link)
        for button in (
            self.btn_add_quick_link,
            self.btn_edit_quick_link,
            self.btn_delete_quick_link,
            self.btn_move_quick_link_up,
            self.btn_move_quick_link_down,
            self.btn_open_quick_link,
        ):
            quick_link_actions.addWidget(button)
        quick_link_actions.addStretch()
        quick_links_layout.addLayout(quick_link_actions)
        control_layout.addWidget(quick_links_group)
        self.refresh_quick_links()

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
        self.lbl_replay_status.setAccessibleName("循環錄影狀態")
        self.lbl_replay_status.setStyleSheet("color: #616161; font-weight: bold;")
        self.lbl_replay_time = QLabel("00:00 / 00:30")
        self.lbl_replay_time.setAccessibleName("目前可儲存的回放長度")
        replay_status_row.addWidget(QLabel("循環錄影："))
        replay_status_row.addWidget(self.lbl_replay_status)
        replay_status_row.addStretch()
        replay_status_row.addWidget(self.lbl_replay_time)
        g4_layout.addLayout(replay_status_row)

        self.lbl_replay_audio_source = QLabel("音訊來源：尚未選擇")
        self.lbl_replay_audio_source.setObjectName("hint")
        self.lbl_replay_audio_source.setAccessibleName("循環錄影音訊來源")
        g4_layout.addWidget(self.lbl_replay_audio_source)

        replay_actions = QHBoxLayout()
        self.btn_toggle_replay = QPushButton("啟動循環錄影")
        self.btn_toggle_replay.setMinimumHeight(44)
        self.btn_toggle_replay.setToolTip("持續保留所選遊戲視窗最近的畫面與聲音")
        self.btn_toggle_replay.clicked.connect(self.toggle_replay_buffer)
        self.btn_save_replay = QPushButton("儲存影片片段")
        self.btn_save_replay.setMinimumHeight(44)
        self.btn_save_replay.setEnabled(False)
        self.btn_save_replay.setToolTip(
            "儲存目前時間窗；最後 5 秒會加密取樣截圖，背景緩衝不會停止或重設"
        )
        self.btn_save_replay.clicked.connect(self.save_replay_segment)
        replay_actions.addWidget(self.btn_toggle_replay)
        replay_actions.addWidget(self.btn_save_replay, 1)
        g4_layout.addLayout(replay_actions)

        capture_actions = QHBoxLayout()

        self.btn_trigger_snip = QPushButton("截圖並辨識")
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

        self.btn_trigger_video = QPushButton("錄影並辨識")
        self.btn_trigger_video.setStyleSheet(VIDEO_TRIGGER_DEFAULT_STYLE)
        self.btn_trigger_video.clicked.connect(self.trigger_video_report)
        self.btn_select_file = QPushButton("選擇本機檢舉證據")
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

        history_actions = QHBoxLayout()
        self.btn_copy_history_url = QPushButton("複製選取連結")
        self.btn_copy_history_url.clicked.connect(self.copy_selected_history_url)
        self.btn_clear_history = QPushButton("清空紀錄")
        self.btn_clear_history.clicked.connect(self.clear_history)
        history_actions.addStretch()
        history_actions.addWidget(self.btn_copy_history_url)
        history_actions.addWidget(self.btn_clear_history)
        history_layout.addLayout(history_actions)

        self.tabs.addTab(tab_history, "歷史紀錄")

        # Update GDrive UI Status
        self.update_gdrive_ui()

        self.lbl_recording_progress = QLabel("未錄影")
        self.lbl_recording_progress.setObjectName("recordingProgressLabel")
        self.lbl_recording_progress.setAccessibleName("錄影目前狀態")
        self.lbl_recording_progress.setMinimumWidth(160)
        self.lbl_recording_progress.setStyleSheet("color: #616161; font-weight: bold;")

        self.progress_recording = QProgressBar()
        self.progress_recording.setObjectName("recordingProgressBar")
        self.progress_recording.setAccessibleName("錄影進度")
        self.progress_recording.setToolTip("目前沒有進行中的錄影")
        self.progress_recording.setRange(0, 100)
        self.progress_recording.setValue(0)
        self.progress_recording.setTextVisible(False)
        self.progress_recording.setMinimumWidth(220)
        self.progress_recording.setMaximumWidth(480)
        self.progress_recording.setFixedHeight(16)
        self.progress_recording.hide()
        self.statusBar().addWidget(self.lbl_recording_progress)
        self.statusBar().addWidget(self.progress_recording, 1)

        self.btn_recording_status = QPushButton("未錄影")
        self.btn_recording_status.setObjectName("recordingStatusButton")
        self.btn_recording_status.setAccessibleName("錄影狀態")
        self.btn_recording_status.setFixedHeight(24)
        self.btn_recording_status.setMinimumWidth(150)
        self.btn_recording_status.clicked.connect(self.cancel_video_recording)
        self.statusBar().addPermanentWidget(self.btn_recording_status)
        self._set_recording_status(False)

    def sync_ocr_autofill_checkboxes(self):
        """Reflect the two OCR options in the tri-state master checkbox."""

        id_enabled = self.chk_ocr_id.isChecked()
        map_enabled = self.chk_ocr_map.isChecked()
        if id_enabled and map_enabled:
            state = Qt.CheckState.Checked
        elif id_enabled or map_enabled:
            state = Qt.CheckState.PartiallyChecked
        else:
            state = Qt.CheckState.Unchecked

        self.chk_ocr_autofill.blockSignals(True)
        self.chk_ocr_autofill.setCheckState(state)
        self.chk_ocr_autofill.blockSignals(False)
        self.chk_ocr_autofill.setAccessibleDescription(
            "角色 ID 與地圖名稱文字辨識（OCR）自動帶入："
            f"{'全部啟用' if state == Qt.CheckState.Checked else '部分啟用' if state == Qt.CheckState.PartiallyChecked else '全部停用'}"
        )

    def _on_ocr_autofill_child_toggled(self, _checked: bool):
        self.sync_ocr_autofill_checkboxes()

    def _on_ocr_autofill_master_changed(self, state: int):
        # Clicking an unchecked or partially checked master enables the whole
        # group; the next click on a checked master disables it.
        state_value = getattr(state, "value", state)
        enabled = state_value != Qt.CheckState.Unchecked.value
        self.chk_ocr_id.setChecked(enabled)
        self.chk_ocr_map.setChecked(enabled)
        self.sync_ocr_autofill_checkboxes()

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

    def copy_selected_history_url(self):
        row = self.table_history.currentRow()
        if row < 0 or not self.history_controller.copy_url_from_cell(self.table_history, row):
            QMessageBox.information(self, "複製連結", "請先選取含有安全 HTTPS 檢舉證據連結的紀錄。")

    def clear_history(self):
        reply = QMessageBox.question(
            self,
            "確認清空紀錄",
            "確定要清空所有歷史紀錄嗎？此操作無法復原。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self.history_controller.clear():
            self.refresh_history_table()
        else:
            QMessageBox.warning(self, "清空失敗", "無法清除歷史紀錄，請稍後再試。")

    def refresh_quick_links(self):
        if not hasattr(self, "table_quick_links"):
            return
        links = self.quick_links_controller.links()
        self.table_quick_links.setRowCount(len(links))
        for row, link in enumerate(links):
            self.table_quick_links.setItem(row, 0, QTableWidgetItem(str(link.get("title", ""))))
            self.table_quick_links.setItem(row, 1, QTableWidgetItem(str(link.get("url", ""))))

    def _selected_quick_link_index(self) -> int:
        if not hasattr(self, "table_quick_links"):
            return -1
        return self.table_quick_links.currentRow()

    def _save_quick_links_and_refresh(self, success: bool):
        if success:
            self.refresh_quick_links()
            return True
        QMessageBox.warning(self, "快捷連結儲存失敗", "無法儲存快捷連結設定，請稍後再試。")
        return False

    def add_quick_link(self):
        title, ok = QInputDialog.getText(self, "新增快捷連結", "名稱：")
        if not ok or not title.strip():
            return
        url, ok = QInputDialog.getText(self, "新增快捷連結", "HTTPS URL：")
        if not ok:
            return
        if not self._save_quick_links_and_refresh(
            self.quick_links_controller.add(title, url)
        ):
            return

    def edit_quick_link(self):
        index = self._selected_quick_link_index()
        links = self.quick_links_controller.links()
        if not 0 <= index < len(links):
            QMessageBox.information(self, "編輯快捷連結", "請先選取要編輯的快捷連結。")
            return
        current = links[index]
        title, ok = QInputDialog.getText(
            self, "編輯快捷連結", "名稱：", text=str(current.get("title", ""))
        )
        if not ok or not title.strip():
            return
        url, ok = QInputDialog.getText(
            self, "編輯快捷連結", "HTTPS URL：", text=str(current.get("url", ""))
        )
        if not ok:
            return
        self._save_quick_links_and_refresh(
            self.quick_links_controller.update(
                index,
                title,
                url,
                icon=str(current.get("icon", "Globe")),
            )
        )

    def delete_quick_link(self):
        index = self._selected_quick_link_index()
        links = self.quick_links_controller.links()
        if not 0 <= index < len(links):
            QMessageBox.information(self, "刪除快捷連結", "請先選取要刪除的快捷連結。")
            return
        reply = QMessageBox.question(
            self,
            "確認刪除快捷連結",
            f"確定要刪除「{links[index].get('title', '')}」嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._save_quick_links_and_refresh(self.quick_links_controller.remove(index))

    def move_quick_link(self, delta: int):
        index = self._selected_quick_link_index()
        if self.quick_links_controller.move(index, delta):
            self.refresh_quick_links()
            self.table_quick_links.selectRow(index + delta)

    def open_quick_link(self, index: int):
        if not self.quick_links_controller.open(index):
            QMessageBox.warning(
                self,
                "無法開啟快捷連結",
                "只允許開啟安全的 HTTPS 快捷連結。",
            )

    def open_selected_quick_link(self):
        self.open_quick_link(self._selected_quick_link_index())

    def update_gdrive_ui(self):
        if self.drive_mgr.is_authenticated():
            self.lbl_gdrive_status.setText("狀態：Google 帳號已登入")
            self.lbl_gdrive_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_gdrive_login.setText("重新驗證 Google 帳號")
        else:
            self.lbl_gdrive_status.setText("狀態：尚未登入")
            self.lbl_gdrive_status.setStyleSheet("color: red; font-weight: bold;")
            self.btn_gdrive_login.setText("登入 Google 帳號")

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

    def configure_global_hotkeys(self) -> bool:
        """Apply the current shortcut fields without taking focus from the game."""

        configured = self.hotkey_manager.configure(
            int(self.winId()),
            enabled=self.chk_global_hotkeys.isChecked(),
            bindings={
                ACTION_SAVE_REPLAY: fixed_hotkey_for_key(
                    self.combo_save_replay_hotkey_key.currentData()
                    or DEFAULT_SAVE_REPLAY_KEY
                ),
                ACTION_RECORD_VIDEO: fixed_hotkey_for_key(
                    self.combo_record_video_hotkey_key.currentData()
                    or DEFAULT_RECORD_VIDEO_KEY
                ),
            },
        )
        self.on_hotkey_registration_changed("", configured, "", "")
        return configured

    def on_global_hotkeys_enabled_toggled(self, enabled: bool):
        self.combo_save_replay_hotkey_key.setEnabled(enabled)
        self.combo_record_video_hotkey_key.setEnabled(enabled)
        if not enabled:
            self.lbl_hotkey_status.setText("儲存設定後停用全域快捷鍵")
            self.lbl_hotkey_status.setStyleSheet("color: #616161;")

    def on_hotkey_registration_changed(
        self,
        action: str,
        registered: bool,
        shortcut: str,
        message: str,
    ):
        if action:
            self._hotkey_statuses[action] = (registered, shortcut, message)

        if not self.chk_global_hotkeys.isChecked():
            text = "全域快捷鍵已停用"
            color = "#616161"
        elif self.hotkey_manager.last_error:
            text = f"快捷鍵未套用：{self.hotkey_manager.last_error} 目前設定未變更。"
            color = "#b71c1c"
        else:
            active = self.hotkey_manager.active_bindings
            labels = []
            if ACTION_SAVE_REPLAY in active:
                labels.append(f"儲存片段 {active[ACTION_SAVE_REPLAY]}")
            if ACTION_RECORD_VIDEO in active:
                labels.append(f"一般錄影 {active[ACTION_RECORD_VIDEO]}")
            text = "全域快捷鍵已啟用：" + "；".join(labels)
            color = "#1b5e20"

        self.lbl_hotkey_status.setText(text)
        self.lbl_hotkey_status.setAccessibleDescription(text)
        self.lbl_hotkey_status.setStyleSheet(f"color: {color};")

    def on_global_hotkey(self, action: str):
        """Dispatch a Windows hotkey without requiring the Reporter to be focused."""

        if action == ACTION_SAVE_REPLAY:
            self.handle_save_replay_hotkey()
        elif action == ACTION_RECORD_VIDEO:
            self.trigger_video_report(from_hotkey=True)

    def handle_save_replay_hotkey(self):
        """Start the replay buffer first, then save it on later F9 presses."""

        if self._closing or self._replay_save_workflow_active:
            return
        if self.replay_controller.is_running:
            self.save_replay_segment(from_hotkey=True)
        else:
            self.toggle_replay_buffer(from_hotkey=True)

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
        guide = QLabel("1. 選擇上傳目的地並完成帳號或 Discord 頻道連結設定。\n2. 選擇遊戲視窗與錄影模式。\n3. 錄影或匯入檢舉證據，確認辨識結果後送出。")
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
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread(
            [pil_img],
            whitelist=wl_list,
            parent=self,
            recognize_id=self.chk_ocr_id.isChecked(),
            recognize_map=self.chk_ocr_map.isChecked(),
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

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()
        modal.dispose_when_idle()

    def toggle_replay_buffer(self, from_hotkey: bool = False):
        if self.replay_controller.is_running:
            if from_hotkey:
                self.save_replay_segment(from_hotkey=True)
            else:
                self.replay_controller.stop()
            return

        win_title = self.combo_windows.currentText().strip()
        if not win_title:
            message = "無法啟動循環錄影：請先選擇目標遊戲視窗。"
            if from_hotkey:
                self.statusBar().showMessage(message, 5000)
            else:
                QMessageBox.warning(self, "無法啟動循環錄影", message)
            return
        selected_audio_device_id = self.combo_audio_output.currentData() or ""
        self.cfg["record_audio"] = self.chk_record_audio.isChecked()
        audio_mode = str(self.cfg.get("audio_capture_mode", "")).casefold()
        if audio_mode not in {"process", "system", "off"}:
            audio_mode = "system" if self.chk_record_audio.isChecked() else "off"
        self.cfg["audio_output_device_id"] = selected_audio_device_id
        self.settings_controller.save_model()
        if not self.chk_record_audio.isChecked():
            self.lbl_replay_audio_source.setText("音訊來源：未錄音系統聲音")
        started = self.replay_controller.start(
            win_title,
            fps=int(self.combo_fps.currentData()),
            buffer_seconds=self.spin_replay_seconds.value(),
            record_audio=self.chk_record_audio.isChecked(),
            audio_device_id=selected_audio_device_id or None,
            audio_capture_mode=audio_mode,
        )
        if from_hotkey:
            if started:
                self.statusBar().showMessage(
                    "F9 已啟動循環錄影；累積幾秒後再次按 F9 儲存影片片段。",
                    5000,
                )
            else:
                self.statusBar().showMessage("循環錄影啟動失敗。", 5000)

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
            text = "音訊來源：未錄音系統聲音"
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
        text = f"正在錄音：{device_name}"
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

    def save_replay_segment(self, from_hotkey: bool = False):
        if from_hotkey and self._replay_save_workflow_active:
            return
        saved = self.replay_controller.save()
        if not saved:
            if from_hotkey:
                self.statusBar().showMessage(
                    "循環錄影尚未累積足夠畫面，請稍候再按 F9。",
                    5000,
                )
                return
            QMessageBox.information(
                self,
                "片段尚未就緒",
                "請先啟動循環錄影並等待至少幾秒，再儲存影片片段。",
            )
            return
        self._replay_save_workflow_active = True

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
            self.btn_toggle_replay.setText("啟動循環錄影")
            self.btn_save_replay.setText("儲存最近片段")
            self.btn_save_replay.setEnabled(False)
        elif state == "warming":
            self.lbl_replay_status.setText("● 正在建立緩衝")
            self.lbl_replay_status.setStyleSheet("color: #ad6800; font-weight: bold;")
            self.btn_toggle_replay.setText("停止循環錄影")
            self.btn_save_replay.setText("儲存目前片段")
            self.btn_save_replay.setEnabled(duration >= 3.0)
        elif state == "ready":
            self.lbl_replay_status.setText("● 可儲存最近片段")
            self.lbl_replay_status.setStyleSheet("color: #1b5e20; font-weight: bold;")
            self.btn_toggle_replay.setText("停止循環錄影")
            self.btn_save_replay.setText(f"儲存最近 {total} 秒")
            self.btn_save_replay.setEnabled(True)
        elif state == "saving":
            self.lbl_replay_status.setText("● 正在儲存片段，緩衝持續中")
            self.lbl_replay_status.setStyleSheet("color: #0d47a1; font-weight: bold;")
            self.btn_toggle_replay.setText("停止循環錄影")
            self.btn_save_replay.setText("正在儲存片段…")
            self.btn_save_replay.setEnabled(False)
        elif state == "stopping":
            self.lbl_replay_status.setText("● 正在停止循環錄影")
            self.lbl_replay_status.setStyleSheet("color: #616161; font-weight: bold;")
            self.btn_toggle_replay.setText("正在停止…")
            self.btn_save_replay.setText("無法儲存")
            self.btn_save_replay.setEnabled(False)
        elif state == "error":
            self.lbl_replay_status.setText("● 循環錄影發生錯誤")
            self.lbl_replay_status.setStyleSheet("color: #b71c1c; font-weight: bold;")
            self.btn_toggle_replay.setText("重新啟動循環錄影")
            self.btn_save_replay.setText("無法儲存")
            self.btn_save_replay.setEnabled(False)

        self.lbl_replay_status.setAccessibleDescription(self.lbl_replay_status.text())

    def on_replay_saved(self, file_path: str, keyframes):
        try:
            self.open_generated_video_preview(file_path, keyframes)
        finally:
            self._replay_save_workflow_active = False

    def on_replay_error(self, message: str):
        self._replay_save_workflow_active = False
        if not self.replay_controller.is_running:
            self.replay_controller.stop()
        QMessageBox.warning(self, "循環錄影", message)

    def on_replay_warning(self, message: str):
        QMessageBox.information(self, "循環錄影音訊", message)

    def open_generated_video_preview(self, file_path: str, keyframes):
        from maple_reporter.ocr.ocr_worker import OcrWorkerThread

        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]
        ocr_thread = OcrWorkerThread(
            keyframes,
            whitelist=wl_list,
            parent=self,
            recognize_id=self.chk_ocr_id.isChecked(),
            recognize_map=self.chk_ocr_map.isChecked(),
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

    def trigger_video_report(self, from_hotkey: bool = False):
        """Run one video workflow; a repeated trigger cancels the active capture."""

        if self._video_workflow_active:
            self.cancel_video_recording()
            return

        self._video_workflow_active = True
        self._video_cancel_requested = False
        self._set_video_trigger_active(True)
        try:
            self._perform_video_report(from_hotkey=from_hotkey)
        finally:
            self._video_workflow_active = False
            self._video_cancel_requested = False
            self._set_video_trigger_active(False)

    def _set_video_trigger_active(self, active: bool):
        self._set_recording_status(active)
        self.btn_trigger_video.setEnabled(True)
        if active:
            self.btn_trigger_video.setStyleSheet(VIDEO_TRIGGER_ACTIVE_STYLE)
            self.btn_trigger_video.setText("取消錄影")
            self.btn_trigger_video.setToolTip("再次按下可取消倒數或正在進行的錄影")
            self.btn_trigger_video.setAccessibleName("取消錄影")
        else:
            self.btn_trigger_video.setStyleSheet(VIDEO_TRIGGER_DEFAULT_STYLE)
            self.btn_trigger_video.setText("錄影並辨識")
            self.btn_trigger_video.setToolTip("開始錄影並辨識；錄影中再次按下可取消")
            self.btn_trigger_video.setAccessibleName("錄影並辨識")

    def _set_recording_progress(self, message: str, progress: int | None = None):
        """Update the status text and progress bar without opening a window."""

        label = getattr(self, "lbl_recording_progress", None)
        progress_bar = getattr(self, "progress_recording", None)
        if label is None or progress_bar is None:
            return

        label.setText(message)
        label.setAccessibleDescription(message)
        label.setToolTip(message)
        progress_bar.setAccessibleDescription(message)
        progress_bar.setToolTip(message)
        if progress is None:
            self._video_progress_value = 0
            progress_bar.setValue(0)
            progress_bar.hide()
            return

        value = max(0, min(100, int(progress)))
        self._video_progress_value = value
        progress_bar.setValue(value)
        progress_bar.show()

    def _set_video_cancelling(self):
        """Give immediate visual feedback while the recorder drains its loop."""

        self._set_recording_progress("正在取消錄影…", self._video_progress_value)
        self.btn_trigger_video.setText("取消中…")
        self.btn_trigger_video.setToolTip("正在停止錄影，請稍候…")
        self.btn_trigger_video.setAccessibleName("取消中")
        self.btn_trigger_video.setEnabled(False)
        self.btn_recording_status.setText("取消中…")
        self.btn_recording_status.setToolTip("正在停止錄影，請稍候…")
        self.btn_recording_status.setAccessibleDescription("正在停止錄影，請稍候")
        self.btn_recording_status.setEnabled(False)

    def _set_recording_status(self, active: bool):
        """Update the status-bar recording indicator and cancellation button."""

        if active:
            self.btn_recording_status.setText("取消錄影")
            self.btn_recording_status.setToolTip("取消目前正在進行的錄影")
            self.btn_recording_status.setAccessibleDescription(
                "錄影正在進行中，按此取消錄影"
            )
            self.btn_recording_status.setEnabled(True)
            self.btn_recording_status.setStyleSheet(
                """
                QPushButton {
                    background-color: #757575;
                    color: white;
                    font-weight: bold;
                    border: 1px solid #616161;
                    border-radius: 3px;
                    padding: 1px 8px;
                }
                QPushButton:hover { background-color: #616161; }
                """
            )
            self._set_recording_progress("錄影準備中…", 0)
        else:
            self.btn_recording_status.setText("未錄影")
            self.btn_recording_status.setToolTip("目前沒有進行中的錄影")
            self.btn_recording_status.setAccessibleDescription("目前沒有進行中的錄影")
            self.btn_recording_status.setEnabled(False)
            self.btn_recording_status.setStyleSheet(
                """
                QPushButton {
                    color: #757575;
                    border: 1px solid #bdbdbd;
                    border-radius: 3px;
                    padding: 1px 8px;
                }
                """
            )
            self._set_recording_progress("未錄影")

    def cancel_video_recording(self):
        """Request cancellation and immediately update both cancel controls."""

        if not getattr(self, "_video_workflow_active", False):
            return False
        if getattr(self, "_video_cancel_requested", False):
            return True
        self._video_cancel_requested = True
        self._set_video_cancelling()
        QCoreApplication.processEvents()
        return True

    def _perform_video_report(self, from_hotkey: bool = False):
        if self._hotkey_recording_active:
            return

        win_title = self.combo_windows.currentText()
        if not win_title:
            if from_hotkey:
                self.statusBar().showMessage("無法錄影：請先選擇目標遊戲視窗。", 5000)
            else:
                QMessageBox.warning(self, "警告", "請先選擇目標遊戲視窗！")
            return

        duration = self.spin_duration.value()
        fps = int(self.combo_fps.currentData())
        countdown = self.spin_countdown.value()

        focus_window(win_title)

        if countdown > 0:
            countdown_end = time.monotonic() + countdown
            last_remaining = None
            while True:
                if self._video_cancel_requested:
                    return
                remaining = int(math.ceil(countdown_end - time.monotonic()))
                if remaining <= 0:
                    break
                if remaining != last_remaining:
                    elapsed_countdown = countdown - remaining
                    percent = int(elapsed_countdown / countdown * 100)
                    self._set_recording_progress(
                        f"倒數開始錄影 {remaining} 秒",
                        percent,
                    )
                    last_remaining = remaining
                QCoreApplication.processEvents()
                if self._video_cancel_requested:
                    return
                time.sleep(min(0.05, max(0.0, countdown_end - time.monotonic())))

        focus_window(win_title)

        if from_hotkey:
            self._hotkey_recording_active = True
        self._set_recording_progress(f"錄影中 0 / {duration} 秒", 0)
        last_elapsed = -1

        def update_progress(val):
            nonlocal last_elapsed
            fraction = max(0.0, min(1.0, float(val)))
            elapsed = min(duration, int(math.ceil(fraction * duration)))
            percent = int(fraction * 100)
            if elapsed != last_elapsed:
                self._set_recording_progress(
                    f"錄影中 {elapsed} / {duration} 秒",
                    percent,
                )
                last_elapsed = elapsed
            else:
                progress_bar = getattr(self, "progress_recording", None)
                if progress_bar is not None:
                    progress_bar.setValue(percent)
            QCoreApplication.processEvents()

        try:
            file_path, keyframes = self.capture_controller.record_video(
                win_title,
                duration_sec=duration,
                fps=fps,
                progress_callback=update_progress,
                cancel_checker=lambda: self._video_cancel_requested,
                record_audio=self.chk_record_audio.isChecked(),
                audio_device_id=self.combo_audio_output.currentData() or None,
                audio_capture_mode=str(self.cfg.get("audio_capture_mode", "system" if self.chk_record_audio.isChecked() else "off")),
            )
            user_canceled = self._video_cancel_requested
        finally:
            if from_hotkey:
                self._hotkey_recording_active = False

        if user_canceled or not file_path:
            self._set_recording_progress("錄影已取消", self._video_progress_value)
            if from_hotkey:
                self.statusBar().showMessage("快捷鍵錄影已取消。", 5000)
            else:
                self.statusBar().showMessage("錄影已取消。", 5000)
            return

        self._set_recording_progress(f"錄影完成，共 {duration} 秒", 100)
        if from_hotkey:
            self.statusBar().showMessage("快捷鍵錄影完成，正在開啟辨識預覽。", 5000)
        self.open_generated_video_preview(file_path, keyframes)

    def trigger_local_file_report(self):
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇本地影片或圖片檔案進行辨識與檢舉",
            str(get_recordings_dir()),
            "媒體檔案 (*.mp4 *.mkv *.avi *.mov *.png *.jpg *.jpeg);;所有檔案 (*.*)"
        )
        if not file_path or not os.path.exists(file_path):
            return

        keyframes = self.capture_controller.load_keyframes(file_path)
        if not keyframes:
            QMessageBox.warning(self, "讀取失敗", "無法從本機檢舉證據讀取可辨識的畫面。")
            return

        from maple_reporter.ocr.ocr_worker import OcrWorkerThread
        wl_list = [w.strip() for w in self.txt_whitelist.text().split(",") if w.strip()]

        ocr_thread = OcrWorkerThread(
            keyframes,
            whitelist=wl_list,
            parent=self,
            recognize_id=self.chk_ocr_id.isChecked(),
            recognize_map=self.chk_ocr_map.isChecked(),
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
            "file_origin": "imported",
        }

        modal = ReportPreviewModal(data, drive_mgr=self.drive_mgr, folder_name=folder_name, discord_webhook_url=self.txt_discord_webhook.text(), upload_destination=self.combo_upload_destination.currentData(), ocr_thread=ocr_thread, parent=self)
        modal.report_confirmed.connect(self.execute_submission)
        modal.exec()
        modal.dispose_when_idle()

    def _persist_settings(self, *, show_hotkey_error: bool) -> bool:
        """Persist settings after applying global shortcuts transactionally."""

        hotkey_keys = (
            "global_hotkeys_enabled",
            "save_replay_hotkey",
            "record_video_hotkey",
        )
        previous_hotkeys = {
            key: self.cfg.get(key)
            for key in hotkey_keys
        }
        self.settings_controller.collect_from_window(self)

        if not self.configure_global_hotkeys():
            for key, value in previous_hotkeys.items():
                if value is None:
                    self.cfg.pop(key, None)
                else:
                    self.cfg[key] = value
            self.chk_global_hotkeys.setChecked(
                bool(previous_hotkeys.get("global_hotkeys_enabled", True))
            )
            save_key = hotkey_key_from_shortcut(
                str(
                    previous_hotkeys.get(
                        "save_replay_hotkey", DEFAULT_SAVE_REPLAY_HOTKEY
                    )
                ),
                DEFAULT_SAVE_REPLAY_KEY,
            )
            record_key = hotkey_key_from_shortcut(
                str(
                    previous_hotkeys.get(
                        "record_video_hotkey", DEFAULT_RECORD_VIDEO_HOTKEY
                    )
                ),
                DEFAULT_RECORD_VIDEO_KEY,
            )
            self.combo_save_replay_hotkey_key.setCurrentIndex(
                self.combo_save_replay_hotkey_key.findData(save_key)
            )
            self.combo_record_video_hotkey_key.setCurrentIndex(
                self.combo_record_video_hotkey_key.findData(record_key)
            )
            self.on_global_hotkeys_enabled_toggled(
                self.chk_global_hotkeys.isChecked()
            )
            self.on_hotkey_registration_changed("", False, "", "")
            if show_hotkey_error:
                QMessageBox.warning(
                    self,
                    "快捷鍵未套用",
                    f"{self.hotkey_manager.last_error}\n原本的快捷鍵設定仍在使用。",
                )
            return False

        if not self.settings_controller.save_model():
            self.load_settings_to_ui()
            self.configure_global_hotkeys()
            QMessageBox.warning(
                self,
                "設定儲存失敗",
                "設定未能寫入，已重新載入後端目前值。請檢查權限或磁碟空間。",
            )
            return False
        return True

    def save_settings(self):
        """Persist all current UI field values to config.json."""
        if not self._persist_settings(show_hotkey_error=True):
            return
        self.btn_save_settings.setText("已儲存")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.btn_save_settings.setText("儲存設定"))

    def execute_submission(self, confirmed_data: dict):
        confirmed_data = dict(confirmed_data)
        self.txt_map.setText(confirmed_data.get("map_name", ""))
        confirmed_data.setdefault(
            "form_submit_headless",
            bool(self.cfg.get("form_submit_headless", True)),
        )
        confirmed_data.setdefault("dev_mode", bool(self.cfg.get("dev_mode", False)))
        self._persist_settings(show_hotkey_error=False)
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
        """Persist local settings on exit."""
        self._closing = True
        self.replay_controller.stop()
        self._persist_settings(show_hotkey_error=False)
        self.hotkey_manager.shutdown()
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
