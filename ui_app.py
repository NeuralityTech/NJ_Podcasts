import sys
import os
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
import shutil
import json
import re
import fitz # PyMuPDF
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QLineEdit, QTextEdit, QMessageBox, QScrollArea, QListWidget, QGroupBox,
    QComboBox, QSpinBox, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSlot, QThread, pyqtSignal, QFileSystemWatcher, QTimer
from PyQt5.QtGui import QIntValidator

# Import custom utilities
from utils.pdf_handler import parse_page_range, extract_pages
from utils.mineru_runner import MinerURunner
from utils.preprocessing import process_preprocessing
from utils.chunking import process_chunking
from utils.retrieval_extraction import process_retrieval_extraction
from utils.script_generation import process_script_generation
from utils.scene_generation import process_scene_generation
from utils.image_prompt_generation import process_image_prompt_generation
from utils.image_generation import process_image_generation
from utils.video_generation import process_video_generation
from utils.sequencing import rebuild_global_sequence

# Preprocessing Runner (QThread for Step 4)
class PreprocessingRunner(QThread):
    finished = pyqtSignal(bool, str, list)

    def __init__(self, latest_output_folder, selected_pages):
        super().__init__()
        self.latest_output_folder = latest_output_folder
        self.selected_pages = selected_pages

    def run(self):
        try:
            result, message = process_preprocessing(self.latest_output_folder, self.selected_pages)
            if result is not None:
                self.finished.emit(True, message, result)
            else:
                self.finished.emit(False, message, [])
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", [])

# Retrieval Runner (QThread for Step 6)
class RetrievalRunner(QThread):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, latest_output_folder, questions, api_key, service_account_path=None):
        super().__init__()
        self.latest_output_folder = latest_output_folder
        self.questions = questions # This is a list
        self.api_key = api_key
        self.service_account_path = service_account_path

    def run(self):
        try:
            path, message = process_retrieval_extraction(self.latest_output_folder, self.questions, self.api_key, self.service_account_path)
            if path:
                self.finished.emit(True, message, path)
            else:
                self.finished.emit(False, message, "")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", "")

# Script Runner (QThread for Step 7)
class ScriptRunner(QThread):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, latest_output_folder, api_key, service_account_path=None):
        super().__init__()
        self.latest_output_folder = latest_output_folder
        self.api_key = api_key
        self.service_account_path = service_account_path

    def run(self):
        try:
            path, message = process_script_generation(self.latest_output_folder, self.api_key, self.service_account_path)
            if path:
                self.finished.emit(True, message, path)
            else:
                self.finished.emit(False, message, "")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", "")

# Stage 8: Scene Runner
class SceneRunner(QThread):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, latest_output_folder, api_key, scene_count=8, service_account_path=None):
        super().__init__()
        self.latest_output_folder = latest_output_folder
        self.api_key = api_key
        self.scene_count = scene_count
        self.service_account_path = service_account_path

    def run(self):
        try:
            # Force cleanup of old results to ensure fresh count
            old_scene_file = os.path.join(self.latest_output_folder, "scene.json")
            if os.path.exists(old_scene_file):
                os.remove(old_scene_file)

            path, message = process_scene_generation(self.latest_output_folder, self.api_key, self.scene_count, self.service_account_path)
            if path:
                self.finished.emit(True, f"{message} (Requested {self.scene_count} scenes)", path)
            else:
                self.finished.emit(False, f"Generation Failed: {message}", "")
        except Exception as e:
            self.finished.emit(False, f"Runner Error: {str(e)}", "")

# Stage 9: Image Prompt Runner
class ImagePromptRunner(QThread):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, latest_output_folder, api_key, service_account_path=None):
        super().__init__()
        self.latest_output_folder = latest_output_folder
        self.api_key = api_key
        self.service_account_path = service_account_path

    def run(self):
        try:
            path, message = process_image_prompt_generation(self.latest_output_folder, self.api_key, self.service_account_path)
            if path:
                self.finished.emit(True, message, path)
            else:
                self.finished.emit(False, message, "")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", "")

# Stage 10: Image Generation Runner
class ImageGenerationRunner(QThread):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, latest_output_folder, api_key, service_account_path=None):
        super().__init__()
        self.latest_output_folder = latest_output_folder
        self.api_key = api_key
        self.service_account_path = service_account_path

    def run(self):
        try:
            path, message = process_image_generation(self.latest_output_folder, self.api_key, self.service_account_path)
            if path:
                self.finished.emit(True, message, path)
            else:
                self.finished.emit(False, message, "")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", "")

class VideoGenerationRunner(QThread):
    finished = pyqtSignal(bool, str, dict)

    def __init__(self, project_folder, api_key, service_account_path=None):
        super().__init__()
        self.project_folder = project_folder
        self.api_key = api_key
        self.service_account_path = service_account_path

    def run(self):
        try:
            result, message = process_video_generation(self.project_folder, self.api_key, self.service_account_path)
            if result:
                self.finished.emit(True, message, result)
            else:
                self.finished.emit(False, message, {})
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}", {})

class SequencingRunner(QThread):
    """Background thread to handle heavy folder reindexing and sequence rebuilding."""
    finished = pyqtSignal()

    def run(self):
        try:
            from utils.sequencing import rebuild_global_sequence
            rebuild_global_sequence()
        except Exception as e:
            print(f"DEBUG: Sequencing Thread Error: {e}")
        self.finished.emit()

# Custom Modern Styling
GLOBAL_STYLE = """
QMainWindow {
    background-color: #f8f9fa;
}
QTabWidget::pane {
    border: 1px solid #dee2e6;
    background: white;
    border-radius: 8px;
    margin-top: -1px;
}
QTabBar::tab {
    background: #e9ecef;
    border: 1px solid #dee2e6;
    padding: 10px 15px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #495057;
    font-size: 13px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background: white;
    border-bottom-color: white;
    color: #007bff;
}
QGroupBox {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    margin-top: 20px;
    padding-top: 20px;
    font-weight: bold;
    font-size: 14px;
    color: #333;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 20px;
    padding: 0 5px;
}
QPushButton {
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0056b3;
}
QPushButton:disabled {
    background-color: #adb5bd;
}
QLineEdit, QTextEdit {
    border: 1px solid #ced4da;
    border-radius: 6px;
    padding: 8px;
    background-color: white;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MinerU Advanced 11-Stage Pipeline")
        self.resize(1200, 850)
        self.setStyleSheet(GLOBAL_STYLE)
        
        # Service Account Configuration
        self.service_account_file = "gen-lang-client-0270986555-ec92ab1a153a.json"
        if os.path.exists(self.service_account_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(self.service_account_file)

        # Global State Management
        self.uploaded_pdf_path = ""
        self.custom_pdf_path = ""
        self.latest_output_folder = ""
        self.selected_pages = [] 
        self.total_pages = 0
        self.cleaned_pages_data = [] # For preprocessed text (Step 4)

        # Automatic Sequence Watcher
        self.project_watcher = QFileSystemWatcher(self)
        self.project_watcher.directoryChanged.connect(self.on_project_changed)
        self.project_watcher.fileChanged.connect(self.on_project_changed)
        
        # UI Initialization
        self.init_ui()
        
        # Debounced Rebuild Timer (Fixes UI Freeze)
        self.rebuild_timer = QTimer(self)
        self.rebuild_timer.setSingleShot(True)
        self.rebuild_timer.timeout.connect(self.safe_rebuild_sequence)
        
        self.setup_project_watchers()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Upload (Step 1)
        self.tab1 = QWidget()
        self.setup_tab1()
        self.tabs.addTab(self.tab1, "1. PDF Upload")

        # Tab 2: Selection (Step 2)
        self.tab2 = QWidget()
        self.setup_tab2()
        self.tabs.addTab(self.tab2, "2. Select Pages")

        # Tab 3: MinerU Extraction (Step 3)
        self.tab3 = QWidget()
        self.setup_tab3()
        self.tabs.addTab(self.tab3, "3. MinerU Run")

        # Tab 4: Preprocessing (Step 4)
        self.tab4 = QWidget()
        self.setup_tab4()
        self.tabs.addTab(self.tab4, "4. Normalize")

        # Tab 5: Chunking (Step 5)
        self.tab5 = QWidget()
        self.setup_tab5()
        self.tabs.addTab(self.tab5, "5. Chunking")
        
        # Tab 6: Retrieval + Extraction (Step 6)
        self.tab6 = QWidget()
        self.setup_tab6()
        self.tabs.addTab(self.tab6, "6. RAG QA")

        # Tab 7: Script Generation (Step 7)
        self.tab7 = QWidget()
        self.setup_tab7()
        self.tabs.addTab(self.tab7, "7. Script")

        # Tab 8: Scene Generation (Step 8)
        self.tab8 = QWidget()
        self.setup_tab8()
        self.tabs.addTab(self.tab8, "8. Scenes")

        # Tab 9: Image Prompt Generation (Step 9)
        self.tab9 = QWidget()
        self.setup_tab9()
        self.tabs.addTab(self.tab9, "9. Image Prompts")

        # Tab 10: Image Generation (Step 10)
        self.tab10 = QWidget()
        self.setup_tab10()
        self.tabs.addTab(self.tab10, "10. Image Generation")

        # Tab 11: Video Generation (Step 11)
        self.tab11 = QWidget()
        self.setup_tab11()
        self.tabs.addTab(self.tab11, "11. Video Generation")
    # --- TAB 1: PDF UPLOAD ---
    def setup_tab1(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        group_selection = QGroupBox("PDF Selection")
        selection_layout = QVBoxLayout()
        
        self.btn_upload = QPushButton("Upload PDF")
        self.btn_upload.clicked.connect(self.upload_pdf)
        selection_layout.addWidget(self.btn_upload)
        
        self.lbl_file_name = QLabel("No file selected")
        self.lbl_file_name.setStyleSheet("color: #6c757d; font-style: italic;")
        selection_layout.addWidget(self.lbl_file_name)
        
        group_selection.setLayout(selection_layout)
        layout.addWidget(group_selection)

        group_info = QGroupBox("File Information")
        info_layout = QVBoxLayout()
        self.lbl_file_path = QLabel("Path: None")
        self.lbl_total_pages = QLabel("Total Pages: 0")
        info_layout.addWidget(self.lbl_file_path)
        info_layout.addWidget(self.lbl_total_pages)
        group_info.setLayout(info_layout)
        layout.addWidget(group_info)
        layout.addStretch()
        self.tab1.setLayout(layout)

    def upload_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if file_path:
            input_dir = os.path.join(os.getcwd(), "input")
            os.makedirs(input_dir, exist_ok=True)
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(input_dir, file_name)
            shutil.copy2(file_path, dest_path)
            self.uploaded_pdf_path = dest_path
            doc = fitz.open(self.uploaded_pdf_path)
            self.total_pages = doc.page_count
            doc.close()
            self.lbl_file_name.setText(f"Selected: {file_name}")
            self.lbl_file_name.setStyleSheet("color: #28a745; font-weight: bold;")
            self.lbl_file_path.setText(f"Path: {self.uploaded_pdf_path}")
            self.lbl_total_pages.setText(f"Total Pages: {self.total_pages}")
            self.spin_n.setValue(min(10, self.total_pages))
            self.spin_n.setMaximum(self.total_pages)
            self.range_input.setText(f"1-{self.total_pages}")
            QMessageBox.information(self, "Success", f"PDF uploaded: {dest_path}")

    # --- TAB 2: PAGE SELECTION ---
    def setup_tab2(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        group_range = QGroupBox("Define Page Range")
        range_layout = QVBoxLayout()
        range_layout.addWidget(QLabel("Selection Method:"))
        self.combo_method = QComboBox()
        self.combo_method.addItems(["All Pages", "First N Pages", "Custom Range"])
        self.combo_method.currentIndexChanged.connect(self.on_selection_method_changed)
        range_layout.addWidget(self.combo_method)
        self.stack_inputs = QStackedWidget()
        widget_all = QWidget()
        self.stack_inputs.addWidget(widget_all)
        widget_n = QWidget()
        n_layout = QHBoxLayout(widget_n)
        n_layout.addWidget(QLabel("Process first:"))
        self.spin_n = QSpinBox()
        self.spin_n.setMinimum(1)
        self.spin_n.setMaximum(9999)
        n_layout.addWidget(self.spin_n)
        n_layout.addWidget(QLabel("pages"))
        n_layout.addStretch()
        self.stack_inputs.addWidget(widget_n)
        widget_custom = QWidget()
        custom_layout = QVBoxLayout(widget_custom)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("Enter Range (e.g. 1-10, 15, 20-25):"))
        self.range_input = QLineEdit()
        self.range_input.setPlaceholderText("Example: 30-60, 80-90, 78-90, 5, 10-15")
        custom_layout.addWidget(self.range_input)
        self.stack_inputs.addWidget(widget_custom)
        range_layout.addWidget(self.stack_inputs)
        btn_generate = QPushButton("Generate & Export Custom PDF")
        btn_generate.clicked.connect(self.generate_custom_pdf)
        range_layout.addWidget(btn_generate)
        group_range.setLayout(range_layout)
        layout.addWidget(group_range)
        self.lbl_custom_status = QLabel("Status: Waiting...")
        self.lbl_custom_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_custom_status)
        layout.addStretch()
        self.tab2.setLayout(layout)

    def on_selection_method_changed(self, index):
        self.stack_inputs.setCurrentIndex(index)

    def generate_custom_pdf(self):
        if not self.uploaded_pdf_path:
            QMessageBox.warning(self, "Warning", "Please upload a PDF first.")
            return
        method = self.combo_method.currentText()
        if method == "All Pages":
            self.selected_pages = list(range(1, self.total_pages + 1))
        elif method == "First N Pages":
            n = self.spin_n.value()
            self.selected_pages = list(range(1, min(n, self.total_pages) + 1))
        else:
            self.selected_pages = parse_page_range(self.range_input.text(), self.total_pages)
        if not self.selected_pages:
            QMessageBox.warning(self, "Warning", "Invalid selection.")
            return
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        self.custom_pdf_path = os.path.join(output_dir, "custom_pages.pdf")
        
        try:
            # We pass raw strings now for Label Lookup
            raw_input = self.range_input.text()
            requested_labels = [p.strip() for p in raw_input.split(',')]
            
            # extract_pages flattens ranges and saves them to custom_pages_labels.json
            extract_pages(self.uploaded_pdf_path, self.custom_pdf_path, requested_labels)
            
            # Fix: The PDF is in the root/output/ directory. HTML is in root/project/section_XX/
            relative_pdf_url = "../../output/custom_pages.pdf"
            sidecar_path = self.custom_pdf_path.replace(".pdf", "_labels.json")
            if os.path.exists(sidecar_path):
                with open(sidecar_path, 'r', encoding='utf-8') as f:
                    self.selected_pages = json.load(f)
            else:
                self.selected_pages = requested_labels # Fallback
            
            self.lbl_custom_status.setText(f"Status: Generated (Labels: {raw_input})")
            self.lbl_custom_status.setStyleSheet("color: #28a745; font-weight: bold;")
            QMessageBox.information(self, "Success", f"Custom PDF generated: {self.custom_pdf_path}\nTarget Labels: {raw_input}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not generate PDF: {str(e)}")

    # --- TAB 3: MINERU PROCESSING ---
    def setup_tab3(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        group_run = QGroupBox("MinerU AI Extraction")
        run_layout = QVBoxLayout()
        run_layout.addWidget(QLabel("Select PDF Source:"))
        self.combo_pdf_source = QComboBox()
        self.combo_pdf_source.addItems(["Custom PDF (from Step 2)", "Original PDF (from Step 1)", "Upload New PDF..."])
        self.combo_pdf_source.currentIndexChanged.connect(self.on_pdf_source_changed)
        run_layout.addWidget(self.combo_pdf_source)
        self.lbl_selected_mineru_pdf = QLabel("No PDF selected")
        self.lbl_selected_mineru_pdf.setStyleSheet("color: #6c757d; font-style: italic;")
        run_layout.addWidget(self.lbl_selected_mineru_pdf)
        self.btn_run_mineru = QPushButton("Run MinerU")
        self.btn_run_mineru.clicked.connect(self.run_mineru)
        self.btn_run_mineru.setStyleSheet("background-color: #6c757d;")
        run_layout.addWidget(self.btn_run_mineru)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        run_layout.addWidget(self.log_area)
        group_run.setLayout(run_layout)
        layout.addWidget(group_run)
        self.lbl_mineru_status = QLabel("Status: Idle")
        self.lbl_mineru_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_mineru_status)
        layout.setStretch(0, 1)
        self.tab3.setLayout(layout)

    def on_pdf_source_changed(self, index):
        if index == 0: self.current_mineru_pdf = self.custom_pdf_path
        elif index == 1: self.current_mineru_pdf = self.uploaded_pdf_path
        elif index == 2:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
            if file_path: self.current_mineru_pdf = file_path
            else: self.combo_pdf_source.setCurrentIndex(0); return
        if self.current_mineru_pdf:
             self.lbl_selected_mineru_pdf.setText(f"Target: {os.path.basename(self.current_mineru_pdf)}")
             self.lbl_selected_mineru_pdf.setStyleSheet("color: #007bff; font-weight: bold;")
        else: self.lbl_selected_mineru_pdf.setText("No PDF selected")

    def run_mineru(self):
        # Fix: The PDF is in the root/output/ directory. HTML is in root/project/section_XX/
        relative_pdf_url = "../../output/custom_pages.pdf"
        target_pdf = self.custom_pdf_path if self.combo_pdf_source.currentIndex() == 0 else \
                     self.uploaded_pdf_path if self.combo_pdf_source.currentIndex() == 1 else \
                     getattr(self, 'current_mineru_pdf', None)
        if not target_pdf or not os.path.exists(target_pdf):
            QMessageBox.warning(self, "Warning", "Target missing.")
            return
        output_base_dir = os.path.join(os.getcwd(), "output")
        self.mineru_runner = MinerURunner(target_pdf, output_base_dir)
        self.mineru_runner.progress.connect(self.log_area.append)
        self.mineru_runner.finished.connect(self.on_mineru_finished)
        self.btn_run_mineru.setEnabled(False)
        self.btn_run_mineru.setText("Running...")
        self.lbl_mineru_status.setText("Status: Running...")
        self.log_area.clear()
        self.mineru_runner.start()

    @pyqtSlot(bool, str, str)
    def on_mineru_finished(self, success, message, output_folder):
        self.btn_run_mineru.setEnabled(True)
        self.btn_run_mineru.setText("Run MinerU")
        if success:
            self.latest_output_folder = output_folder
            self.lbl_mineru_status.setText("Status: Completed")
            self.lbl_mineru_status.setStyleSheet("color: #28a745; font-weight: bold;")
            QMessageBox.information(self, "Success", f"Output folder: {output_folder}")
        else:
            self.lbl_mineru_status.setText("Status: Failed")
            QMessageBox.critical(self, "Error", message)

    # --- TAB 4: PREPROCESSING ---
    def setup_tab4(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        group_pre = QGroupBox("Number of Tokens")
        pre_layout = QVBoxLayout()
        self.btn_process_pages = QPushButton("Process Pages")
        self.btn_process_pages.clicked.connect(self.run_preprocessing)
        pre_layout.addWidget(self.btn_process_pages)
        self.pre_info = QTextEdit()
        self.pre_info.setReadOnly(True)
        self.pre_info.setPlaceholderText("Page normalization summary...")
        pre_layout.addWidget(self.pre_info)
        group_pre.setLayout(pre_layout)
        layout.addWidget(group_pre)
        self.lbl_pre_status = QLabel("Status: Idle")
        self.lbl_pre_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_pre_status)
        layout.setStretch(0, 1)
        self.tab4.setLayout(layout)

    def run_preprocessing(self):
        if not self.latest_output_folder:
            QMessageBox.warning(self, "Warning", "Run Step 3 first.")
            return
        self.pre_runner = PreprocessingRunner(self.latest_output_folder, self.selected_pages)
        self.pre_runner.finished.connect(self.on_pre_finished)
        self.btn_process_pages.setEnabled(False)
        self.lbl_pre_status.setText("Status: Processing...")
        self.pre_info.clear()
        self.pre_runner.start()

    @pyqtSlot(bool, str, list)
    def on_pre_finished(self, success, message, result):
        self.btn_process_pages.setEnabled(True)
        if success:
            self.cleaned_pages_data = result
            self.lbl_pre_status.setText("Status: Completed")
            total_tokens = sum(page["tokens"] for page in result)
            self.pre_info.append("=== PER-PAGE TOKENS ===")
            for pg in result:
                self.pre_info.append(f"Page {pg['page']} → {pg['tokens']} tokens")
            self.pre_info.append("\n-------------------------")
            self.pre_info.append(f"TOTAL TOKENS → {total_tokens}")
        else:
            QMessageBox.critical(self, "Error", message)

    # --- TAB 5: CHUNKING ---
    def setup_tab5(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        group_chunk = QGroupBox("Chunking")
        chunk_layout = QVBoxLayout()
        btn_chunk = QPushButton("Generate Chunks")
        btn_chunk.clicked.connect(self.generate_chunks)
        chunk_layout.addWidget(btn_chunk)
        self.chunk_info = QTextEdit()
        self.chunk_info.setReadOnly(True)
        chunk_layout.addWidget(self.chunk_info)
        group_chunk.setLayout(chunk_layout)
        layout.addWidget(group_chunk)
        layout.setStretch(0, 1)
        self.tab5.setLayout(layout)

    def generate_chunks(self):
        if not self.cleaned_pages_data:
            QMessageBox.warning(self, "Warning", "Process Step 4 first.")
            return
        output_path, message = process_chunking(self.latest_output_folder, self.cleaned_pages_data)
        if output_path:
            self.chunk_info.append(f"SUCCESS: {message}\nSaved at: {output_path}")
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data: self.chunk_info.append(f"Total chunks: {len(data)}\nSnippet:\n{json.dumps(data[0], indent=2)}")
            QMessageBox.information(self, "Success", "Chunks generated.")
        else: QMessageBox.critical(self, "Error", message)

    # --- TAB 6: CONTEXT-BASED Q&A (GEMINI) ---
    def setup_tab6(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        group_qa = QGroupBox("Context-Based Q&A (Gemini AI)")
        qa_layout = QVBoxLayout()
        
        # --- NEW SERVICE ACCOUNT OVERRIDE ---
        auth_layout = QHBoxLayout()
        auth_layout.addWidget(QLabel("Vertex AI JSON (Optional):"))
        self.btn_upload_vertex = QPushButton("Upload Vertex JSON")
        self.btn_upload_vertex.clicked.connect(self.upload_vertex_json)
        self.btn_upload_vertex.setStyleSheet("background-color: #6c757d; padding: 5px 10px; font-size: 12px;")
        auth_layout.addWidget(self.btn_upload_vertex)
        self.lbl_vertex_status = QLabel("Default Used")
        self.lbl_vertex_status.setStyleSheet("color: #666; font-size: 11px;")
        if os.path.exists(self.service_account_file):
            self.lbl_vertex_status.setText(f"Active: {os.path.basename(self.service_account_file)}")
        auth_layout.addWidget(self.lbl_vertex_status)
        qa_layout.addLayout(auth_layout)
        
        # Mode Selection Dropdown
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Questioning Mode:"))
        self.qa_mode_combo = QComboBox()
        self.qa_mode_combo.addItems(["Manual Interactive Question", "Batch Question Bank (File Upload)"])
        mode_layout.addWidget(self.qa_mode_combo)
        qa_layout.addLayout(mode_layout)

        # Container for Batch mode widgets
        self.batch_widget = QWidget()
        batch_layout = QVBoxLayout(self.batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_layout = QHBoxLayout()
        lbl_layout.addWidget(QLabel("Batch Question Bank (TXT / PDF / DOCX):"))
        self.btn_upload_qb = QPushButton("Upload File")
        self.btn_upload_qb.clicked.connect(self.upload_qa_bank)
        lbl_layout.addWidget(self.btn_upload_qb)
        batch_layout.addLayout(lbl_layout)

        self.qb_input = QTextEdit()
        self.qb_input.setPlaceholderText("Upload a file or paste questions here...")
        batch_layout.addWidget(self.qb_input)
        
        qa_layout.addWidget(self.batch_widget)

        # Container for Manual mode widget
        self.manual_widget = QWidget()
        manual_layout = QVBoxLayout(self.manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        
        manual_layout.addWidget(QLabel("Manual Question:"))
        self.manual_q_input = QLineEdit()
        self.manual_q_input.setPlaceholderText("Enter a single question to answer manually...")
        manual_layout.addWidget(self.manual_q_input)
        
        qa_layout.addWidget(self.manual_widget)
        
        # Connect visibility toggle
        self.qa_mode_combo.currentIndexChanged.connect(self.toggle_qa_mode)
        # Set default visibility
        self.toggle_qa_mode(0)
        
        # Run Button
        self.btn_run_ext = QPushButton("Run Structured Extraction (Gemini)")
        self.btn_run_ext.clicked.connect(self.run_extraction)
        qa_layout.addWidget(self.btn_run_ext)
        
        # Output Area
        from PyQt5.QtWidgets import QTextBrowser
        self.ext_output = QTextBrowser()
        self.ext_output.setOpenExternalLinks(False)
        self.ext_output.anchorClicked.connect(self.on_rag_link_clicked)
        self.ext_output.setPlaceholderText("JSON results will appear here as clickable links...")
        qa_layout.addWidget(self.ext_output)
        
        group_qa.setLayout(qa_layout)
        layout.addWidget(group_qa)
        
        
        # View Audit Button
        self.btn_view_rag_audit = QPushButton("View Interactive Audit Viewer (HTML)")
        self.btn_view_rag_audit.clicked.connect(self.view_rag_audit)
        self.btn_view_rag_audit.setStyleSheet("background-color: #f0f7ff; border: 1px solid #3498db; color: #004C8F; font-weight: bold; padding: 5px;")
        layout.addWidget(self.btn_view_rag_audit)
        
        # Status Label
        self.lbl_ext_status = QLabel("Status: Idle")
        self.lbl_ext_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_ext_status)
        
        layout.setStretch(0, 1)
        self.tab6.setLayout(layout)

    def upload_vertex_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Vertex AI Service Account JSON", "", "JSON Files (*.json)")
        if file_path:
            self.service_account_file = file_path
            self.lbl_vertex_status.setText(f"Selected: {os.path.basename(file_path)}")
            self.lbl_vertex_status.setStyleSheet("color: #28a745; font-weight: bold;")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(file_path)
            QMessageBox.information(self, "Success", f"Service Account updated to:\n{file_path}")

    def on_rag_link_clicked(self, url):
        link = url.toString()
        if "#page=" in link:
            try:
                p_val = link.split("#page=")[-1]
                
                # RECALIBRATED PDF DISCOVERY:
                # Always look for custom_pages.pdf in the root 'output/' folder.
                root_output = os.path.join(os.getcwd(), "output")
                clean_path = os.path.abspath(os.path.join(root_output, "custom_pages.pdf"))

                if os.path.exists(clean_path):
                    QMessageBox.information(self, "Audit Navigator", f"Launching Source Document...\n\nPlease scroll to PAGE {p_val} to verify the data.")
                    os.startfile(clean_path)
                else:
                    QMessageBox.warning(self, "Error", f"PDF Source file not found: {clean_path}")
            except Exception as e: 
                QMessageBox.warning(self, "Error", f"Failed to follow link: {e}")
        else:
            import webbrowser
            webbrowser.open(link)

    def view_rag_audit(self):
        # SEARCH ALGORITHM: 1. Try Captured Path, 2. Try Global Latest, 3. Try Root Output
        search_dirs = []
        if hasattr(self, 'rag_output_dir') and self.rag_output_dir: search_dirs.append(self.rag_output_dir)
        if self.latest_output_folder: search_dirs.append(self.latest_output_folder)
        
        # Add root output/ folder as a fallback
        root_output = os.path.join(os.getcwd(), "output")
        if os.path.exists(root_output):
            search_dirs.append(root_output)
            # Check for standard subfolders like custom_pages/auto
            search_dirs.append(os.path.join(root_output, "custom_pages", "auto"))

        found_file = None
        for d in search_dirs:
            p = os.path.join(d, "rag_audit.html")
            if os.path.exists(p):
                found_file = p
                break
        
        if found_file:
            import webbrowser, pathlib
            webbrowser.open(pathlib.Path(os.path.abspath(found_file)).as_uri())
        else:
            QMessageBox.warning(self, "Error", f"Audit file 'rag_audit.html' not found.\nChecked in: {', '.join(search_dirs)}")

    def upload_qa_bank(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Question Bank", "", "Documents (*.txt *.pdf *.docx)")
        if not file_path:
            return
        
        try:
            fp_str = str(file_path).lower()
            if fp_str.endswith('.pdf'):
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                self.qb_input.setText(text.strip())
            elif fp_str.endswith('.docx'):
                import docx
                doc = docx.Document(file_path)
                text = "\n".join([p.text for p in doc.paragraphs])
                self.qb_input.setText(text.strip())
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.qb_input.setText(f.read().strip())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read file:\n{str(e)}")

    def toggle_qa_mode(self, index):
        """Toggle visibility based on dropdown index"""
        is_manual = (index == 0)
        self.manual_widget.setVisible(is_manual)
        self.batch_widget.setVisible(not is_manual)

    def run_extraction(self):
        if not self.latest_output_folder:
            QMessageBox.warning(self, "Warning", "Please run Step 5 (Chunking) first.")
            return

        is_manual = (self.qa_mode_combo.currentIndex() == 0)
        api_key = os.getenv("GEMINI_API_KEY", "").strip()

        # Check for service account or API key
        has_service_account = os.path.exists(self.service_account_file)
        if not has_service_account and (not api_key or "YOUR" in api_key):
            QMessageBox.critical(self, "Error", "Gemini API Key not found in .env and service account JSON not found.")
            return

        questions = []
        if is_manual:
            manual_q = self.manual_q_input.text().strip()
            if not manual_q:
                QMessageBox.warning(self, "Warning", "Please enter a question.")
                return
            questions.append(manual_q)
        else:
            qb_text = self.qb_input.toPlainText().strip()
            if not qb_text:
                QMessageBox.warning(self, "Warning", "Please upload a bank file or paste questions.")
                return
            questions.extend([q.strip() for q in qb_text.splitlines() if q.strip()])

        self.btn_run_ext.setEnabled(False)
        self.lbl_ext_status.setText("Status: Processing Questions with Gemini Context Stuffing...")
        self.ext_output.clear()
        
        self.ext_runner = RetrievalRunner(self.latest_output_folder, questions, api_key, self.service_account_file)
        self.ext_runner.finished.connect(self.on_ext_finished)
        self.ext_runner.start()

    @pyqtSlot(bool, str, str)
    def on_ext_finished(self, success, message, output_path):
        self.btn_run_ext.setEnabled(True)
        self.rag_output_dir = output_path # Capture the EXACT directory for the auditor
        if success:
            # CRITICAL FIX: update latest_output_folder so downstream steps (Tab 9) find rag_output.json
            self.latest_output_folder = output_path
            self.lbl_ext_status.setText("Status: Completed")
            self.lbl_ext_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.ext_output.clear()
            self.ext_output.append(f"SUCCESS: {message}<br>Saved at: {output_path}<br>")
            
            try:
                manifest_path = os.path.join(output_path, "rag_output.json")
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Highlight anchor_id as actual clickable links
                raw_json = json.dumps(data, indent=2, ensure_ascii=False)
                safe_json = raw_json.replace("<", "&lt;").replace(">", "&gt;")
                safe_json = re.sub(r'("anchor_id":\s*")([^"]+)(")', r'\1<a href="\2">\2</a>\3', safe_json)
                
                # 1. Insert JSON Data first (No more inline audit link, button below is used)
                self.ext_output.insertHtml(f"<pre style='font-family: Consolas, monospace; font-size: 13px;'>{safe_json}</pre>")
            except Exception as e:
                self.ext_output.append(f"<b>Failed to read output:</b> {str(e)}")
                
            QMessageBox.information(self, "Success", "Structured RAG output generated with interactive audit links.")
        else:
            self.lbl_ext_status.setText("Status: Failed")
            self.lbl_ext_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.ext_output.clear()
            self.ext_output.append(f"<b style='color: red;'>ERROR:</b> {message}")
            QMessageBox.critical(self, "Error", message)


    # --- TAB 7: SCRIPT GENERATION ---
    def setup_tab7(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        group_script = QGroupBox("Script Generation")
        script_layout = QVBoxLayout()
        
        self.btn_run_script = QPushButton("Generate Narration Script")
        self.btn_run_script.clicked.connect(self.run_script)
        script_layout.addWidget(self.btn_run_script)
        
        self.script_output = QTextEdit()
        self.script_output.setReadOnly(True)
        self.script_output.setPlaceholderText("Generated script will appear here...")
        script_layout.addWidget(self.script_output)
        
        group_script.setLayout(script_layout)
        layout.addWidget(group_script)
        
        self.lbl_script_status = QLabel("Status: Idle")
        self.lbl_script_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_script_status)
        
        layout.setStretch(0, 1)
        self.tab7.setLayout(layout)

    def run_script(self):
        if not self.latest_output_folder:
            QMessageBox.warning(self, "Warning", "Please run Step 6 (RAG QA) to generate insights first.")
            return
        
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_sa = os.path.exists(self.service_account_file)
        if not has_sa and (not api_key or "YOUR" in api_key):
            QMessageBox.critical(self, "Error", "Gemini API Key or service account JSON not found.")
            return

        self.btn_run_script.setEnabled(False)
        self.lbl_script_status.setText("Status: Generating Script with Gemini AI...")
        self.script_output.clear()
        
        self.script_runner = ScriptRunner(self.latest_output_folder, api_key, self.service_account_file)
        self.script_runner.finished.connect(self.on_script_finished)
        self.script_runner.start()

    @pyqtSlot(bool, str, str)
    def on_script_finished(self, success, message, output_folder):
        self.btn_run_script.setEnabled(True)
        if success:
            self.latest_output_folder = output_folder
            self.lbl_script_status.setText("Status: Completed")
            self.lbl_script_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.script_output.append(f"SUCCESS: {message}\nFolder: {output_folder}\n")
            
            try:
                script_file = os.path.join(output_folder, "script.txt")
                with open(script_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.script_output.append(content)
            except Exception as e:
                self.script_output.append(f"Failed to read output for display: {str(e)}")
                
            QMessageBox.information(self, "Success", f"Narration script generated and saved in {os.path.basename(output_folder)}.")
        else:
            self.lbl_script_status.setText("Status: Failed")
            self.lbl_script_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.script_output.append(f"ERROR: {message}")
            QMessageBox.critical(self, "Error", message)

    # --- TAB 8: SCENE GENERATION ---
    def setup_tab8(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        group_scene = QGroupBox("Video Scene Generation")
        scene_layout = QVBoxLayout()
        
        # Scene Count Selection (Dynamic from UI per prompt4.txt)
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of Scenes to Generate:"))
        self.scene_count_input = QLineEdit()
        self.scene_count_input.setValidator(QIntValidator(1, 200))
        self.scene_count_input.setPlaceholderText("Enter count (1-200)")
        count_layout.addWidget(self.scene_count_input)
        scene_layout.addLayout(count_layout)

        self.btn_run_scene = QPushButton("Generate Video Scenes")
        self.btn_run_scene.clicked.connect(self.run_scene)
        scene_layout.addWidget(self.btn_run_scene)
        
        self.scene_output = QTextEdit()
        self.scene_output.setReadOnly(True)
        self.scene_output.setPlaceholderText("Generated visually descriptive scenes will appear here...")
        scene_layout.addWidget(self.scene_output)
        
        group_scene.setLayout(scene_layout)
        layout.addWidget(group_scene)
        
        self.lbl_scene_status = QLabel("Status: Idle")
        self.lbl_scene_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_scene_status)
        
        layout.setStretch(0, 1)
        self.tab8.setLayout(layout)

    def run_scene(self):
        if not self.latest_output_folder:
            QMessageBox.warning(self, "Warning", "Please run Step 7 (Script Generation) first.")
            return

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_sa = os.path.exists(self.service_account_file)
        if not has_sa and (not api_key or "YOUR" in api_key):
            QMessageBox.critical(self, "Error", "Gemini API Key or service account JSON not found.")
            return

        try:
            val = self.scene_count_input.text().strip()
            scene_count = int(val) if val else 8
        except ValueError:
            scene_count = 8
        
        self.btn_run_scene.setEnabled(False)
        self.lbl_scene_status.setText(f"Status: Generating {scene_count} Scenes with Gemini AI...")
        self.scene_output.clear()
        
        self.scene_runner = SceneRunner(self.latest_output_folder, api_key, scene_count, self.service_account_file)
        self.scene_runner.finished.connect(self.on_scene_finished)
        self.scene_runner.start()

    @pyqtSlot(bool, str, str)
    def on_scene_finished(self, success, message, output_folder):
        self.btn_run_scene.setEnabled(True)
        if success:
            self.latest_output_folder = output_folder # CRITICAL SYNC FIX
            self.lbl_scene_status.setText("Status: Completed")
            self.lbl_scene_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.scene_output.append(f"SUCCESS: {message}\nFolder: {output_folder}\n")
            
            try:
                scene_file = os.path.join(output_folder, "scene.json")
                with open(scene_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.scene_output.append(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception as e:
                self.scene_output.append(f"Failed to read output for display: {str(e)}")
                
            QMessageBox.information(self, "Success", "Video scenes generated.")
        else:
            self.lbl_scene_status.setText("Status: Failed")
            self.lbl_scene_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.scene_output.append(f"ERROR: {message}")
            QMessageBox.critical(self, "Error", message)


    # --- TAB 9: IMAGE PROMPT GENERATION ---
    def setup_tab9(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        group_prompt = QGroupBox("AI Image Prompt Engineering")
        prompt_layout = QVBoxLayout()
        
        self.btn_run_prompt = QPushButton("Generate AI Image Prompts")
        self.btn_run_prompt.clicked.connect(self.run_prompt_generation)
        prompt_layout.addWidget(self.btn_run_prompt)
        
        from PyQt5.QtWidgets import QTextBrowser
        self.prompt_output = QTextBrowser()
        self.prompt_output.setOpenExternalLinks(False)
        self.prompt_output.anchorClicked.connect(self.on_rag_link_clicked)
        self.prompt_output.setPlaceholderText("Optimized high-fidelity prompts will appear here...")
        prompt_layout.addWidget(self.prompt_output)
        
        group_prompt.setLayout(prompt_layout)
        layout.addWidget(group_prompt)
        
        # View Prompt Audit Button (RE-INSTATED)
        self.btn_view_prompt_audit = QPushButton("View Interactive Prompt Audit (HTML)")
        self.btn_view_prompt_audit.clicked.connect(self.view_prompt_audit)
        self.btn_view_prompt_audit.setStyleSheet("background-color: #f0f7ff; border: 1px solid #3498db; color: #004C8F; font-weight: bold; padding: 5px;")
        layout.addWidget(self.btn_view_prompt_audit)
        
        self.lbl_prompt_status = QLabel("Status: Idle")
        self.lbl_prompt_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_prompt_status)
        
        layout.setStretch(0, 1)
        self.tab9.setLayout(layout)

    def run_prompt_generation(self):
        if not self.latest_output_folder:
            QMessageBox.warning(self, "Warning", "Please run Step 8 (Scene Generation) first.")
            return

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_sa = os.path.exists(self.service_account_file)
        if not has_sa and (not api_key or "YOUR" in api_key):
            QMessageBox.critical(self, "Error", "Gemini API Key or service account JSON not found.")
            return

        self.btn_run_prompt.setEnabled(False)
        self.lbl_prompt_status.setText("Status: Engineering Visual Prompts with Gemini AI...")
        self.prompt_output.clear()
        
        self.prompt_runner = ImagePromptRunner(self.latest_output_folder, api_key, self.service_account_file)
        self.prompt_runner.finished.connect(self.on_prompt_finished)
        self.prompt_runner.start()

    @pyqtSlot(bool, str, str)
    def on_prompt_finished(self, success, message, output_folder):
        self.btn_run_prompt.setEnabled(True)
        self.prompt_output_dir = output_folder # Capture the EXACT directory for the auditor
        if success:
            self.latest_output_folder = output_folder # CRITICAL SYNC FIX
            self.lbl_prompt_status.setText("Status: Completed")
            self.lbl_prompt_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.prompt_output.append(f"SUCCESS: {message}\nFolder: {output_folder}\n")
            
            try:
                prompt_file = os.path.join(output_folder, "image_prompts.json")
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    raw_json = json.dumps(data, indent=2, ensure_ascii=False)
                    safe_json = raw_json.replace("<", "&lt;").replace(">", "&gt;")
                    safe_json = re.sub(r'("anchor_id":\s*")([^"]+)(")', r'\1<a href="\2">\2</a>\3', safe_json)
                    # 1. Insert JSON Data first (No more inline audit link, button below is used)
                    self.prompt_output.insertHtml(f"<pre style='font-family: Consolas, monospace; font-size: 13px;'>{safe_json}</pre>")
            except Exception as e:
                self.prompt_output.append(f"Failed to read output: {str(e)}")
            QMessageBox.information(self, "Success", "Image prompts successfully engineered.")
        else:
            self.lbl_prompt_status.setText("Status: Failed")
            self.lbl_prompt_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.prompt_output.append(f"ERROR: {message}")
            QMessageBox.critical(self, "Error", message)

    # --- TAB 10: IMAGE GENERATION ---
    def setup_tab10(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        group_img = QGroupBox("Direct AI Image Generation (Nano Banana)")
        img_layout = QVBoxLayout()
        
        self.btn_run_image = QPushButton("Generate Scene Images")
        self.btn_run_image.clicked.connect(self.run_image_gen)
        img_layout.addWidget(self.btn_run_image)
        
        self.image_output = QTextEdit()
        self.image_output.setReadOnly(True)
        self.image_output.setPlaceholderText("Generation log and image paths will appear here...")
        img_layout.addWidget(self.image_output)
        
        group_img.setLayout(img_layout)
        layout.addWidget(group_img)
        
        self.lbl_img_status = QLabel("Status: Idle")
        self.lbl_img_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_img_status)
        
        layout.setStretch(0, 1)
        self.tab10.setLayout(layout)

    def run_image_gen(self):
        if not self.latest_output_folder:
            QMessageBox.warning(self, "Warning", "Please run Step 9 (Prompt Generation) first.")
            return

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_sa = os.path.exists(self.service_account_file)
        if not has_sa and (not api_key or "YOUR" in api_key):
            QMessageBox.critical(self, "Error", "Gemini API Key or service account JSON not found.")
            return

        self.btn_run_image.setEnabled(False)
        self.lbl_img_status.setText("Status: Generating High-Fidelity Images...")
        self.image_output.clear()
        
        self.img_runner = ImageGenerationRunner(self.latest_output_folder, api_key, self.service_account_file)
        self.img_runner.finished.connect(self.on_image_gen_finished)
        self.img_runner.start()

    @pyqtSlot(bool, str, str)
    def on_image_gen_finished(self, success, message, output_folder):
        self.btn_run_image.setEnabled(True)
        if success:
            self.lbl_img_status.setText("Status: Completed")
            self.lbl_img_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.image_output.append(f"SUCCESS: {message}\nFolder: {output_folder}\n")
            
            try:
                # In Stage 10, the "manifest" resides in images_manifest.json (or results can show the images)
                manifest_file = os.path.join(output_folder, "images_manifest.json")
                if os.path.exists(manifest_file):
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.image_output.append(json.dumps(data, indent=2, ensure_ascii=False))
                else:
                    self.image_output.append("Images generated successfully. (Manifest file not found for display)")
            except Exception as e:
                self.image_output.append(f"Failed to read manifest: {str(e)}")
            QMessageBox.information(self, "Success", "All scene images have been generated.")
        else:
            self.lbl_img_status.setText("Status: Failed")
            self.lbl_img_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.image_output.append(f"ERROR: {message}")
            QMessageBox.critical(self, "Error", message)

    def view_rag_audit(self):
        # SEARCH ALGORITHM: 1. Try Captured Path, 2. Try Global Latest, 3. Try Root Output
        search_dirs = []
        if hasattr(self, 'rag_output_dir') and self.rag_output_dir: search_dirs.append(self.rag_output_dir)
        if self.latest_output_folder: search_dirs.append(self.latest_output_folder)
        
        # Add root output/ folder as a fallback
        root_output = os.path.join(os.getcwd(), "output")
        if os.path.exists(root_output):
            search_dirs.append(root_output)
            # Check for standard subfolders like custom_pages/auto
            search_dirs.append(os.path.join(root_output, "custom_pages", "auto"))

        found_file = None
        for d in search_dirs:
            p = os.path.join(d, "rag_audit.html")
            if os.path.exists(p):
                found_file = p
                break
        
        if found_file:
            import webbrowser, pathlib
            webbrowser.open(pathlib.Path(os.path.abspath(found_file)).as_uri())
        else:
            QMessageBox.warning(self, "Error", f"Audit file 'rag_audit.html' not found.\nChecked in: {', '.join(search_dirs)}")

    def setup_tab11(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        group_config = QGroupBox("Project Selection")
        config_layout = QHBoxLayout()
        self.edit_video_project = QLineEdit()
        self.edit_video_project.setPlaceholderText("Select project root folder (e.g. results/project_name)...")
        self.btn_browse_video = QPushButton("Browse Project")
        self.btn_browse_video.clicked.connect(self.browse_video_project)
        config_layout.addWidget(self.edit_video_project)
        config_layout.addWidget(self.btn_browse_video)
        group_config.setLayout(config_layout)
        layout.addWidget(group_config)

        group_video = QGroupBox("Video Orchestration & Veo 3.1 Render")
        video_layout = QVBoxLayout()
        
        self.btn_run_video = QPushButton("Generate Final Video (180s)")
        self.btn_run_video.clicked.connect(self.run_video_gen)
        video_layout.addWidget(self.btn_run_video)
        
        self.video_output = QTextEdit()
        self.video_output.setReadOnly(True)
        self.video_output.setPlaceholderText("Video timeline and Veo status will appear here...")
        video_layout.addWidget(self.video_output)
        
        group_video.setLayout(video_layout)
        layout.addWidget(group_video)
        
        self.lbl_video_status = QLabel("Status: Idle")
        self.lbl_video_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_video_status)
        
        layout.setStretch(1, 1)
        self.tab11.setLayout(layout)

    def browse_video_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Root Folder")
        if folder:
            self.edit_video_project.setText(folder)

    def run_video_gen(self):
        manual_path = self.edit_video_project.text().strip()
        
        if manual_path:
            project_root = manual_path
        elif self.latest_output_folder:
            # If we just ran Step 10, latest_output_folder is project/section_XX
            # We need the parent project/ folder
            project_root = os.path.dirname(self.latest_output_folder)
        else:
            QMessageBox.warning(self, "Warning", "Please select a Project Folder or run Step 10 first.")
            return

        if not os.path.exists(os.path.join(project_root, "global_sequence.json")):
             QMessageBox.critical(self, "Error", f"Selected folder is not a valid project (missing global_sequence.json):\n{project_root}")
             return
        
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_sa = os.path.exists(self.service_account_file)
        if not has_sa and (not api_key or "YOUR" in api_key):
            QMessageBox.critical(self, "Error", "Gemini API Key or service account JSON not found.")
            return

        self.btn_run_video.setEnabled(False)
        self.lbl_video_status.setText("Status: Orchestrating Video Timeline...")
        self.video_output.clear()
        
        self.video_runner = VideoGenerationRunner(project_root, api_key, self.service_account_file)
        self.video_runner.finished.connect(self.on_video_finished)
        self.video_runner.start()

    @pyqtSlot(bool, str, dict)
    def on_video_finished(self, success, message, result):
        self.btn_run_video.setEnabled(True)
        if success:
            self.lbl_video_status.setText("Status: Completed")
            self.lbl_video_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.video_output.append(f"SUCCESS: {message}\n")
            self.video_output.append(json.dumps(result, indent=2, ensure_ascii=False))
            QMessageBox.information(self, "Success", "Video timeline generated. Veo 3.1 render has been queued.")
        else:
            self.lbl_video_status.setText("Status: Failed")
            self.lbl_video_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.video_output.append(f"ERROR: {message}")
            QMessageBox.critical(self, "Error", message)

    def setup_project_watchers(self):
        """Monitors the project folder tree for ANY changes."""
        root = os.path.join(os.getcwd(), "project")
        if not os.path.exists(root): os.makedirs(root, exist_ok=True)
        
        # Remove old paths to avoid dupes/errors
        current_paths = self.project_watcher.directories()
        if current_paths: self.project_watcher.removePaths(current_paths)
        
        # Monitor Root (for additions/deletions of sections)
        self.project_watcher.addPath(root)
        
        # Monitor each section's images folder (for scene changes)
        sections = [f for f in os.listdir(root) if f.startswith("section_") and os.path.isdir(os.path.join(root, f))]
        for s in sections:
            img_dir = os.path.join(root, s, "images")
            if os.path.exists(img_dir): self.project_watcher.addPath(img_dir)
            sec_dir = os.path.join(root, s)
            self.project_watcher.addPath(sec_dir)

    def on_project_changed(self, path):
        """Triggered automatically on any file system change. Starts a 2s debounce timer."""
        self.rebuild_timer.start(2000) 

    def safe_rebuild_sequence(self):
        """Performs heavy rebuilding in a background thread to keep UI alive."""
        if hasattr(self, 'seq_runner') and self.seq_runner.isRunning():
            # If already running, wait for next debounce
            self.rebuild_timer.start(2000)
            return
            
        self.seq_runner = SequencingRunner()
        self.seq_runner.finished.connect(lambda: QTimer.singleShot(1000, self.setup_project_watchers))
        self.seq_runner.start()
        # print("DEBUG: Sequence Rebuild started in background...")

    def view_prompt_audit(self):
        search_dirs = []
        if hasattr(self, 'prompt_output_dir') and self.prompt_output_dir: search_dirs.append(self.prompt_output_dir)
        if self.latest_output_folder: search_dirs.append(self.latest_output_folder)
        
        root_output = os.path.join(os.getcwd(), "output")
        if os.path.exists(root_output):
            search_dirs.append(os.path.join(root_output, "custom_pages", "auto"))

        found_file = None
        for d in search_dirs:
            p = os.path.join(d, "prompt_audit.html")
            if os.path.exists(p):
                found_file = p
                break
        
        if found_file:
            import webbrowser, pathlib
            webbrowser.open(pathlib.Path(os.path.abspath(found_file)).as_uri())
        else:
            QMessageBox.warning(self, "Error", f"Audit file 'prompt_audit.html' not found.\nChecked in: {', '.join(search_dirs)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


