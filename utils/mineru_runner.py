import os
import subprocess
import glob
from PyQt5.QtCore import QThread, pyqtSignal

class MinerURunner(QThread):
    finished = pyqtSignal(bool, str, str)  # (success, status_msg, latest_output_folder)
    progress = pyqtSignal(str)

    def __init__(self, input_pdf_path, output_base_dir):
        super().__init__()
        self.input_pdf_path = input_pdf_path
        self.output_base_dir = output_base_dir

    def run(self):
        try:
            # Set environment variable to fix OpenMP duplicate library error
            os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

            # Command based on prompt3 requirements:
            # mineru -p E:\mineru_new\output\custom_pages.pdf -o E:\mineru_new\output -b pipeline -d cpu -l en
            
            command = [
                "mineru",
                "-p", self.input_pdf_path,
                "-o", self.output_base_dir,
                "-b", "pipeline",
                "-d", "cpu",
                "-l", "en"
            ]
            
            # Start process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True # Required for 'mineru' to be recognized as a command
            )
            
            # Read output and emit progress signals
            stdout = process.stdout
            if stdout is not None:
                while True:
                    line = stdout.readline()
                    if not line:
                        break
                    self.progress.emit(line.strip())
            
            # Wait for process to complete
            process.wait()
            
            if process.returncode == 0:
                # Execution successful, detect latest output folder
                latest_output_folder = self.get_latest_output_folder()
                if latest_output_folder:
                    # CONSOLIDATION: Copy MinerU extracted images to a clean folder
                    self.consolidate_extracted_images(latest_output_folder)
                    self.finished.emit(True, "Process completed successfully. Images consolidated.", latest_output_folder)
                else:
                    self.finished.emit(False, "MinerU finished but couldn't detect output folder.", "")
            else:
                self.finished.emit(False, f"MinerU failed with exit code {process.returncode}.", "")
                
        except Exception as e:
            self.finished.emit(False, f"An error occurred: {str(e)}", "")

    def consolidate_extracted_images(self, latest_folder):
        """Copies images from MinerU's nested folder to a standard extracted_pdf_images path."""
        import shutil
        src_images = os.path.join(latest_folder, "images")
        if os.path.exists(src_images) and os.path.isdir(src_images):
            # Target is sibling to the PDF name folder in output
            # Path: .../output/extracted_pdf_images
            dest_images = os.path.join(os.path.dirname(os.path.dirname(latest_folder)), "extracted_pdf_images")
            os.makedirs(dest_images, exist_ok=True)
            
            for item in os.listdir(src_images):
                s = os.path.join(src_images, item)
                d = os.path.join(dest_images, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)

    def get_latest_output_folder(self):
        """
        Detects the most recently created folder in the output directory.
        MinerU creates a folder named after the PDF name (without extension).
        """
        # Look for subdirectories in the output_base_dir
        # MinerU folders usually have a timestamp or at least the PDF name
        pdf_name = os.path.splitext(os.path.basename(self.input_pdf_path))[0]
        search_pattern = os.path.join(self.output_base_dir, pdf_name, "*")
        
        # We need to find the parent folder which is usually the pdf name, 
        # and then MinerU might create a timestamped folder inside it? 
        # Actually, let's just find the latest directory created in the base output path.
        
        # MinerU's behavior: -o folder_path results in folder_path/pdf_name/timestamp/
        parent_path = os.path.join(self.output_base_dir, pdf_name)
        if not os.path.exists(parent_path):
             return None
        
        subfolders = [os.path.join(parent_path, f) for f in os.listdir(parent_path) if os.path.isdir(os.path.join(parent_path, f))]
        
        if not subfolders:
             return None
             
        # Find latest based on creation time
        latest_folder = max(subfolders, key=os.path.getctime)
        return latest_folder
