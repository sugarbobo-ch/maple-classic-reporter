import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QRadioButton, QButtonGroup, QPushButton, QTextEdit, QMessageBox
)
from maple_reporter.discord.webhook_service import upload_evidence_to_discord
from maple_reporter.gui.widgets import WheelSafeComboBox


class EvidenceUploadThread(QThread):
    finished_signal = Signal(bool, str)

    def __init__(self, destination, file_path, drive_mgr, folder_name, webhook_url, description, parent=None):
        super().__init__(parent)
        self.destination = destination
        self.file_path = file_path
        self.drive_mgr = drive_mgr
        self.folder_name = folder_name
        self.webhook_url = webhook_url
        self.description = description

    def run(self):
        if self.destination == "gdrive":
            ok, result = self.drive_mgr.upload_file_and_make_public(self.file_path, self.folder_name)
        else:
            ok, result = upload_evidence_to_discord(self.webhook_url, self.file_path, self.description)
        self.finished_signal.emit(ok, result)

class ReportPreviewModal(QDialog):
    report_confirmed = Signal(dict)

    def __init__(self, data: dict, drive_mgr=None, folder_name: str = "MapleClassic_Reports", discord_webhook_url: str = "", upload_destination: str = "gdrive", ocr_thread=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("確認並送出外掛檢舉內容")
        self.resize(500, 500)

        self.drive_mgr = drive_mgr
        self.folder_name = folder_name
        self.file_path = data.get("file_path", "")
        self.ocr_thread = ocr_thread
        self.discord_webhook_url = discord_webhook_url.strip()
        self.upload_destination = upload_destination
        self.default_map_name = str(data.get("default_map_name") or "").strip()
        self._map_name_user_edited = False
        self.upload_thread = None
        self.pending_data = None
        self._dispose_requested = False

        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("確認外掛檢舉內容")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e88e5; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Media Preview Section
        if self.file_path and os.path.exists(self.file_path):
            media_box = QHBoxLayout()
            ext = os.path.splitext(self.file_path)[1].lower()
            is_video = ext in [".mp4", ".mkv", ".avi", ".mov"]
            media_label_text = f"事證檔案：{os.path.basename(self.file_path)}"

            lbl_media = QLabel(media_label_text)
            lbl_media.setStyleSheet("font-weight: bold; color: #333;")

            btn_preview = QPushButton("播放預覽影片" if is_video else "檢視截圖圖片")
            btn_preview.setStyleSheet("""
                QPushButton {
                    background-color: #0288d1;
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #0277bd; }
            """)
            btn_preview.clicked.connect(self.preview_file)

            media_box.addWidget(lbl_media)
            media_box.addStretch()
            media_box.addWidget(btn_preview)
            layout.addLayout(media_box)

        # 1. Suspect ID (Editable QComboBox with Candidate List & Whitelist Button)
        layout.addWidget(QLabel("1. 外掛玩家角色 ID (可隨時手動輸入或選取):"))
        id_box = QHBoxLayout()
        self.id_combo = WheelSafeComboBox()
        self.id_combo.setEditable(True)

        candidates = data.get("candidate_ids", [])
        suspect_id = data.get("suspect_id", "")
        if suspect_id and suspect_id not in candidates:
            candidates.insert(0, suspect_id)

        if candidates:
            self.id_combo.addItems(candidates)
            self.id_combo.setCurrentIndex(0)
        else:
            self.id_combo.setEditText(suspect_id)

        btn_add_whitelist = QPushButton("加入白名單")
        btn_add_whitelist.setToolTip("將目前選擇的 ID 加入白名單（例如自己或隊友名稱），未來將自動過濾")
        btn_add_whitelist.setStyleSheet("""
            QPushButton {
                background-color: #78909c;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #607d8b; }
        """)
        btn_add_whitelist.clicked.connect(self.add_current_id_to_whitelist)

        id_box.addWidget(self.id_combo, 1)
        id_box.addWidget(btn_add_whitelist)
        layout.addLayout(id_box)

        # Live OCR Status Label
        self.lbl_ocr_status = QLabel("")
        self.lbl_ocr_status.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 5px;")
        layout.addWidget(self.lbl_ocr_status)

        # Connect background OCR thread signals if provided
        if self.ocr_thread:
            self.ocr_thread.candidates_found.connect(self.on_live_candidates_found)
            self.ocr_thread.map_name_found.connect(self.on_live_map_name_found)
            self.ocr_thread.status_changed.connect(self.on_ocr_status_changed)
            self.ocr_thread.finished.connect(self.on_ocr_finished)

        # 2. Server Selection
        layout.addWidget(QLabel("2. 伺服器:"))
        server_layout = QHBoxLayout()
        self.radio_server1 = QRadioButton("雪吉拉")
        self.radio_server2 = QRadioButton("菇菇寶貝")
        self.server_group = QButtonGroup(self)
        self.server_group.addButton(self.radio_server1, 1)
        self.server_group.addButton(self.radio_server2, 2)

        if data.get("server_name") == "菇菇寶貝":
            self.radio_server2.setChecked(True)
        else:
            self.radio_server1.setChecked(True)

        server_layout.addWidget(self.radio_server1)
        server_layout.addWidget(self.radio_server2)
        server_layout.addStretch()
        layout.addLayout(server_layout)

        # 3. Map Name
        map_label = QLabel("3. 所在地圖名稱:")
        map_box = QHBoxLayout()
        self.map_input = QLineEdit(str(data.get("map_name") or ""))
        map_label.setBuddy(self.map_input)
        self.map_input.setAccessibleName("所在地圖名稱")
        self.map_input.setAccessibleDescription(
            "可填入 OCR 辨識的地圖名稱，也可以使用預設地圖名稱"
        )
        self.map_input.setPlaceholderText("等待 OCR 辨識結果，或手動輸入")
        self.map_input.textEdited.connect(self._on_map_name_edited)

        self.btn_use_default_map = QPushButton("使用預設地圖名稱")
        self.btn_use_default_map.setToolTip("將預設地圖名稱帶入所在地圖名稱")
        self.btn_use_default_map.clicked.connect(self.use_default_map_name)

        self.lbl_default_map_name = QLabel(
            f"預設地圖名稱：{self.default_map_name}"
        )
        self.lbl_default_map_name.setObjectName("hint")

        map_box.addWidget(self.map_input, 1)
        map_box.addWidget(self.btn_use_default_map)
        map_box.addWidget(self.lbl_default_map_name)
        layout.addWidget(map_label)
        layout.addLayout(map_box)

        # 4. Note
        layout.addWidget(QLabel("4. 備註 / 外掛違規說明:"))
        self.note_input = QLineEdit(data.get("note", "自動打怪/外掛行為"))
        layout.addWidget(self.note_input)

        destination_name = "Google Drive" if self.upload_destination == "gdrive" else "Discord"
        layout.addWidget(QLabel(f"5. 上傳後自動產生的事證連結（{destination_name}）："))
        url_box = QHBoxLayout()
        self.url_input = QLineEdit(data.get("evidence_url", ""))
        self.url_input.setReadOnly(True)
        self.url_input.setPlaceholderText(f"完成上傳後會自動產生，並填入外部檢舉表單")
        self.url_input.setToolTip("此連結由上傳流程自動產生，不能手動修改。")
        url_box.addWidget(self.url_input)
        layout.addLayout(url_box)

        self.lbl_upload_status = QLabel("")
        self.lbl_upload_status.setObjectName("hint")
        layout.addWidget(self.lbl_upload_status)

        layout.addSpacing(15)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_submit = QPushButton("確認內容並上傳事證")
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_cancel = QPushButton("取消 (Cancel)")
        self.btn_cancel.setStyleSheet("padding: 8px 16px;")

        self.btn_submit.clicked.connect(self.on_submit)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_submit)
        layout.addLayout(btn_layout)

        # Start OCR only after every field, including map_input, exists. A
        # fast OCR result can otherwise arrive while __init__ is still
        # constructing the dialog and be lost before it can be displayed.
        if self.ocr_thread and not self.ocr_thread.isRunning():
            self.ocr_thread.start()

    def on_ocr_status_changed(self, status_text: str):
        self.lbl_ocr_status.setText(status_text)
        if "完成" in status_text:
            self.lbl_ocr_status.setStyleSheet("font-size: 11px; color: #2e7d32; font-weight: bold; margin-bottom: 5px;")
        elif "本地補充" in status_text:
            self.lbl_ocr_status.setStyleSheet("font-size: 11px; color: #0288d1; font-weight: bold; margin-bottom: 5px;")
        else:
            self.lbl_ocr_status.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 5px;")

    def on_live_candidates_found(self, candidates: list):
        current_text = self.id_combo.currentText().strip()
        existing = [self.id_combo.itemText(i) for i in range(self.id_combo.count())]

        added_any = False
        for c in candidates:
            if c and c not in existing:
                self.id_combo.addItem(c)
                existing.append(c)
                added_any = True

        # If user hasn't typed anything yet and candidates arrived, auto-select first!
        if not current_text and self.id_combo.count() > 0:
            self.id_combo.setCurrentIndex(0)
        else:
            # Preserve user's current typed text
            self.id_combo.setEditText(current_text)

    def on_live_map_name_found(self, map_name: str):
        detected_map = map_name.strip()
        if not detected_map:
            return

        # Fill the empty field with OCR results, but preserve any explicit user
        # edit or selection made through the default-name button.
        if not self._map_name_user_edited:
            self.map_input.setText(detected_map)

    def on_ocr_finished(self):
        """Apply a stored map result if its queued signal arrived too early."""

        if not self.ocr_thread or self._map_name_user_edited:
            return
        detected_map = str(getattr(self.ocr_thread, "detected_map_name", "") or "")
        if detected_map:
            self.on_live_map_name_found(detected_map)

    def _on_map_name_edited(self, _text: str):
        self._map_name_user_edited = True

    def use_default_map_name(self):
        self._map_name_user_edited = True
        self.map_input.setText(self.default_map_name)
        self.map_input.setFocus()
        self.map_input.selectAll()

    def dispose_when_idle(self):
        """Delete the closed modal after its child worker threads have exited."""
        self._dispose_requested = True
        self._dispose_if_idle()

    def _dispose_if_idle(self):
        if not self._dispose_requested:
            return
        active_threads = [self.upload_thread]
        if any(thread and thread.isRunning() for thread in active_threads):
            return
        self.ocr_thread = None
        self.deleteLater()

    def add_current_id_to_whitelist(self):
        target_id = self.id_combo.currentText().strip()
        if not target_id:
            return

        from maple_reporter.utils.config import load_config, save_config
        cfg = load_config()
        wl = cfg.get("whitelist", [])
        if target_id not in wl:
            wl.append(target_id)
            cfg["whitelist"] = wl
            save_config(cfg)

        curr_idx = self.id_combo.currentIndex()
        if curr_idx != -1:
            self.id_combo.removeItem(curr_idx)

        self.lbl_ocr_status.setText(f"已將「{target_id}」加入白名單，未來會自動過濾。")
        self.lbl_ocr_status.setStyleSheet("font-size: 11px; color: #d32f2f; font-weight: bold; margin-bottom: 5px;")

    def preview_file(self):
        if self.file_path and os.path.exists(self.file_path):
            try:
                os.startfile(self.file_path)
            except Exception as e:
                QMessageBox.warning(self, "開啟失敗", f"無法開啟媒體檔案: {str(e)}")

    def on_submit(self):
        suspect_id = self.id_combo.currentText().strip()
        if not suspect_id:
            QMessageBox.warning(self, "警告", "外掛玩家角色 ID 不能為空！")
            return

        server_name = "雪吉拉" if self.radio_server1.isChecked() else "菇菇寶貝"
        map_name = self.map_input.text().strip()
        if not map_name:
            QMessageBox.warning(
                self,
                "無法送出",
                "請確認所在地圖名稱，或按「使用預設地圖名稱」。",
            )
            self.map_input.setFocus()
            return
        note = self.note_input.text().strip() or "自動打怪/外掛行為"
        if not self.file_path or not os.path.isfile(self.file_path):
            QMessageBox.warning(self, "無法送出", "找不到本次事證檔案；必須先成功上傳事證。")
            return
        destination_name = "Google Drive" if self.upload_destination == "gdrive" else "Discord"
        if self.upload_destination == "gdrive":
            if not self.drive_mgr or not self.drive_mgr.is_authenticated():
                QMessageBox.warning(self, "無法送出", "Google Drive 尚未授權；必須先成功上傳事證。")
                return
        else:
            if not self.discord_webhook_url:
                QMessageBox.warning(self, "無法送出", "尚未設定 Discord Webhook URL。")
                return
        self.pending_data = {
            "suspect_id": suspect_id,
            "server_name": server_name,
            "map_name": map_name,
            "note": note,
            "evidence_url": "",
            "file_path": self.file_path,
            "upload_confirmed": False,
            "form_confirmed": False,
        }
        self.btn_submit.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_submit.setText("上傳中…")
        self.lbl_upload_status.setText(f"正在上傳至 {destination_name}。影片較大時可能需要一段時間，請勿關閉視窗。")
        description = f"檢舉事證｜ID: {suspect_id}｜伺服器: {server_name}｜地圖: {map_name}"
        self.upload_thread = EvidenceUploadThread(
            self.upload_destination, self.file_path, self.drive_mgr, self.folder_name,
            self.discord_webhook_url, description, parent=self,
        )
        self.upload_thread.finished_signal.connect(self.on_upload_finished)
        self.upload_thread.finished.connect(self.upload_thread.deleteLater)
        self.upload_thread.finished.connect(self.on_upload_thread_finished)
        self.upload_thread.start()

    def on_upload_thread_finished(self):
        self.upload_thread = None
        self._dispose_if_idle()

    def on_upload_finished(self, ok: bool, evidence_url: str):
        destination_name = "Google Drive" if self.upload_destination == "gdrive" else "Discord"
        self.btn_submit.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_submit.setText("確認內容並上傳事證")
        if not ok:
            self.lbl_upload_status.setText(f"{destination_name} 上傳失敗，表單尚未送出。")
            QMessageBox.warning(self, "上傳失敗", f"{evidence_url}\n表單尚未送出。")
            return
        self.url_input.setText(evidence_url)
        self.btn_submit.setText("已完成上傳，正在送出表單…")
        self.lbl_upload_status.setText(f"已完成上傳至 {destination_name}，正在帶入連結並送出表單。")
        self.pending_data["evidence_url"] = evidence_url
        self.pending_data["upload_confirmed"] = True
        self.report_confirmed.emit(self.pending_data)
        self.accept()
