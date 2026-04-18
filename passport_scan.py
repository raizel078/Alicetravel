import sys
import fitz
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QFrame, QFileDialog, QPushButton
from PySide6.QtCore import Qt , QTimer
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
import easyocr
import torch, os


class PassportScanner(QWidget):
    def __init__(self):
        super().__init__()

        self.reader  = easyocr.Reader(['en'], gpu=torch.cuda.is_available())
        #window and titled and background
        self.setFixedSize(800,700)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle('Passport Scanner V.1 -Nowa- Alice Travel')

        self.bg_label = QLabel(self)
        pixmap = QPixmap('/home/nowa/Desktop/new ML/Projects/Alicetravel/datasets/alice.jpeg')
        if not pixmap.isNull():
            self.bg_label.setPixmap(pixmap.scaled(800,700, Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.bg_label.setGeometry(0,0,800,700)

        #now the box for the file drops.
        self.drop_zone =  QFrame(self)
        self.drop_zone.setGeometry(150,350, 500,200)
        self.drop_zone.setStyleSheet('''
            QFrame {background-color:rgba(109, 205, 220, 0.8);
                                     border:2px solid;
                                     border-radius: 25px;}
            QFrame:hover {background-color:rgba(109, 205, 220, 1);
                                     border: 2px dashed;
                                     border-radius:30px;}''')

        self.label = QLabel('Drop your files here \nOr choose to click', self.drop_zone)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet('color:black; font-size:20px; font-weight:bold; background:transparent;')
        self.label.setGeometry(0,0,500,200)

        self.setAcceptDrops(True)
        self.drop_zone.mousePressEvent = self.open_explorer
        # *SCAN BUTTON*
        self.scan_btn = QPushButton('Start Scan', self)
        self.scan_btn.setGeometry(180,550,200,50)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.setEnabled(False)
        self.scan_btn.setStyleSheet('background-color: #555555; color:#888888; border-radius: 10px; font-weight:bold;')
        self.scan_btn.clicked.connect(self.Run_extraction)

        #clear Button.
        self.clear_btn = QPushButton('Clear', self)
        self.clear_btn.setGeometry(420, 550, 200, 50)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
                    QPushButton { background-color: #721c24; color: white; border-radius: 10px; font-weight: bold; }
                    QPushButton:hover { background-color: #a71d2a; }
                """)
        self.clear_btn.clicked.connect(self.reset_interface)

        # --- 5. STATUS LABEL ---
        self.status_label = QLabel(self)
        self.status_label.setGeometry(150, 300, 500, 200)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()

        self.current_file = None


    '''all the function will go down here., and styling up above.'''

    def reset_interface(self):
        self.current_file = None
        self.status_label.hide()
        self.drop_zone.show()
        self.label.setText('Drop Passport Here\nor click to Browse')
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText('Start Scan')
        self.scan_btn.setStyleSheet('background-color: #555555; color:#888888; border-radius: 10px;')
        if os.path.exists("temp_scan.jpg"):
            os.remove("temp_scan.jpg")

    def open_explorer(self, event):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Passport File')
        if file_path:
            self.process_file(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.process_file(files[0])

    def process_file(self, path):
        self.current_file = path
        self.scan_btn.setEnabled(True)
        self.scan_btn.setStyleSheet("""
                QPushButton { background-color: #0025AB; color: white; border-radius: 10px; font-weight: bold; }
                QPushButton:hover { background-color: #001A7A; }
            """)
        self.label.setText(f'File Ready:\n{os.path.basename(path)}')

    @staticmethod
    def convert_pdf_to_img(self, path):
        try:
            doc = fitz.open(path)
            page = doc.load_page(0)
            zoom = 2.5  # Extra zoom for sharper MRZ reading
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            temp_image = "temp_scan.jpg"
            pix.save(temp_image)
            doc.close()
            return temp_image
        except Exception as e:
            print(f"PDF Error: {e}")
            return None
    @staticmethod
    def parse_passport_data(self, results):
        mrz_lines = [line.replace(" ", "").upper() for line in results if
                     "<<" in line or (len(line) > 30 and "<" in line)]

        if len(mrz_lines) < 2:
            return None

        # Line 1: P<IND[SURNAME]<<[GIVEN NAMES]
        # Line 2: [PASS NO][CHECK]IND[DOB][CHECK][SEX][EXPIRY][CHECK]
        line1 = mrz_lines[0]
        line2 = mrz_lines[1]

        try:
            # 1. Passport Number: First 9 characters of the second MRZ line
            passport_no = line2[0:9].replace("<", "")

            # 2. Names from Line 1
            # Skip P<IND (first 5 chars)
            raw_names = line1[5:]
            name_parts = raw_names.split('<<')
            surname = name_parts[0].replace('<', ' ').strip()
            given_name = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ""

            # 3. Dates (YYMMDD) - Handling common OCR errors
            dob_raw = line2[13:19]
            exp_raw = line2[21:27]

            # Simple formatting (Assumes 19xx for DOB and 20xx for Expiry)
            dob = f"{dob_raw[4:6]}/{dob_raw[2:4]}/19{dob_raw[0:2]}"
            expiry = f"{exp_raw[4:6]}/{exp_raw[2:4]}/20{exp_raw[0:2]}"

            return {
                "no": passport_no,
                "surname": surname,
                "name": given_name,
                "dob": dob,
                "exp": expiry
            }
        except Exception as e:
            print(f"Parsing Error: {e}")
            return None

    def Run_extraction(self):
        if not hasattr(self, 'current_file') or not self.current_file:
            return

        self.drop_zone.hide()
        self.status_label.show()
        self.status_label.setText("⌛ ANALYZING PASSPORT...")
        self.status_label.setStyleSheet("""
                QLabel { background-color: rgba(0, 37, 171, 200); color: white; 
                         border-radius: 25px; font-size: 18px; font-weight: bold; border: 2px solid white; }                    
            """)
        self.scan_btn.setEnabled(False)

        # Use a single-shot timer to let UI refresh before the heavy AI work
        QTimer.singleShot(100, self._execute_ocr)

    def _execute_ocr(self):
        filename = self.current_file.lower()
        if filename.endswith('.pdf'):
            image_path = self.convert_pdf_to_img(self.current_file)
        else:
            image_path = self.current_file

        if not image_path:
            self.status_label.setText("❌ File Error")
            self.scan_btn.setEnabled(True)
            return

        try:
            # Run the Brain
            results = self.reader.readtext(image_path, detail=0)
            print(f"DEBUG RAW: {results}")

            data = self.parse_passport_data(results)
            if data:
                # This is your bulletproof output
                success_msg = (
                    f"✅ VERIFIED\n\n"
                    f"PASS NO: {data['no']}\n"
                    f"NAME: {data['name']} {data['surname']}\n"
                    f"EXPIRY: {data['exp']}"
                )
                self.status_label.setText(success_msg)
                print(f"Parsed Successfully: {data}")
            else:
                self.status_label.setText("⚠️ MRZ Reading Failed\nPlease try a clearer photo.")

        except Exception as e:
            self.status_label.setText(f"❌ OCR Error: {str(e)}")

        self.scan_btn.setEnabled(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PassportScanner()
    window.show()
    sys.exit(app.exec())

