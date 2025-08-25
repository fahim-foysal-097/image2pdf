import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QFileDialog, QMessageBox, QListWidgetItem, QLabel,
    QHBoxLayout, QComboBox, QColorDialog, QProgressBar, QScrollArea, QDialog
)
from PyQt6.QtGui import QPixmap, QIcon, QColor, QCursor, QFont
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image

class DragDropList(QListWidget):
    """
    A custom QListWidget that handles drag-and-drop events for image files.
    """
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(80, 80))
        self.reset_style()

    def dragEnterEvent(self, event):
        """Changes the widget's style when a drag event with URLs enters."""
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #4CAF50;
                    padding: 10px;
                    background-color: #e6ffe6;
                }
            """)
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        """Resets the widget's style when the drag event leaves."""
        self.reset_style()

    def dragMoveEvent(self, event):
        """Accepts a drag move event if it contains file URLs."""
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """
        Processes dropped file URLs and adds image files to the list widget.
        """
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                # Check for common image file extensions
                if path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff")):
                    self.add_image_item(path)
            event.accept()
            self.reset_style()
        else:
            super().dropEvent(event)

    def reset_style(self):
        """Resets the default styling for the list widget."""
        self.setStyleSheet("""
            QListWidget {
                border: 2px dashed #aaaaaa;
                padding: 10px;
                background-color: #f9f9f9;
            }
            QListWidget::item {
                margin: 5px;
                padding: 5px;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #87CEFA;
            }
        """)

    def add_image_item(self, path):
        """
        Creates and adds a QListWidgetItem with a thumbnail and file path.
        """
        item = QListWidgetItem()
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(pixmap))
        item.setText(os.path.basename(path))
        # Store the full file path in the UserRole for later retrieval
        item.setData(Qt.ItemDataRole.UserRole, path)
        self.addItem(item)

class PDFWorker(QThread):
    """
    A QThread to perform PDF creation in a separate thread.
    This prevents the main UI from freezing.
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(self, images, output_file, use_a4=True, bg_color=QColor("white")):
        super().__init__()
        self.images = images
        self.output_file = output_file
        self.use_a4 = use_a4
        self.bg_color = bg_color

    def run(self):
        """
        The main worker function that creates the PDF.
        """
        failed_images = []
        try:
            # Initialize the PDF canvas
            if self.use_a4:
                c = canvas.Canvas(self.output_file, pagesize=A4)
            else:
                # For custom page sizes, we will set it after loading the first image
                c = canvas.Canvas(self.output_file)

            a4_width, a4_height = A4
            total = len(self.images)

            for idx, img_path in enumerate(self.images, 1):
                try:
                    with Image.open(img_path) as img:
                        width, height = img.size
                        
                        if not self.use_a4:
                            # Set page size to match the image size
                            c.setPageSize((width, height))
                            page_width, page_height = width, height
                            ratio = 1
                        else:
                            page_width, page_height = a4_width, a4_height
                            # Calculate the scaling ratio to fit the image on the page
                            ratio = min(page_width / width, page_height / height)
                        
                        new_width = width * ratio
                        new_height = height * ratio
                        x = (page_width - new_width) / 2
                        y = (page_height - new_height) / 2

                    # Draw the background rectangle
                    c.setFillColorRGB(self.bg_color.redF(), self.bg_color.greenF(), self.bg_color.blueF())
                    c.rect(0, 0, page_width, page_height, fill=True, stroke=False)
                    # Draw the image on the canvas
                    c.drawImage(img_path, x, y, width=new_width, height=new_height)
                    
                    # Create a new page for the next image
                    c.showPage()
                except Exception as e:
                    # Append any failed images to the list for user feedback
                    failed_images.append(f"{os.path.basename(img_path)} (Error: {e})")

                # Emit progress update
                self.progress.emit(int(idx / total * 100))
            
            # Finalize the PDF
            c.save()
        except Exception as e:
            failed_images.append(f"PDF creation failed: {e}")

        # Emit the finished signal with the list of failed images
        self.finished.emit(failed_images)

class PreviewDialog(QDialog):
    """
    A dialog to show a preview of all selected images.
    """
    def __init__(self, images):
        super().__init__()
        self.setWindowTitle("Preview Images")
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        for img_path in images:
            label = QLabel()
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(pixmap)
            label.setToolTip(img_path)
            scroll_layout.addWidget(label)

        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        self.setLayout(layout)

class ImageToPDF(QMainWindow):
    """
    The main application window for the Image to PDF converter.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Image to PDF Converter")
        self.setGeometry(300, 100, 900, 600)
        self.page_bg_color = QColor("white")
        self.worker = None

        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Sets up the main window's user interface elements with new styling."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Apply a font to the entire application for a cleaner look
        font = QFont("Helvetica", 10)
        central_widget.setFont(font)

        layout = QVBoxLayout()
        layout.setSpacing(15) # Add spacing between widgets

        title_label = QLabel("Drag & Drop Images Here")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333333; margin-bottom: 5px;")
        layout.addWidget(title_label)

        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(10)
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["A4 Page", "Use Image Size"])
        self.page_size_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        settings_layout.addWidget(QLabel("Page Size:"))
        settings_layout.addWidget(self.page_size_combo)

        self.bg_color_btn = QPushButton("Select Page Background")
        self.bg_color_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 5px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        settings_layout.addWidget(self.bg_color_btn)
        layout.addLayout(settings_layout)

        self.list_widget = DragDropList()
        layout.addWidget(self.list_widget)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.hide()  # Initially hide the progress bar
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Add styled buttons with new colors
        self.add_btn = QPushButton("Add Images")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setStyleSheet("""
            QPushButton {
                background-color: #B0BEC5;
                color: #333333;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #90A4AE;
            }
            QPushButton:pressed {
                background-color: #78909C;
            }
        """)
        
        self.clear_btn = QPushButton("Clear List")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:pressed {
                background-color: #C62828;
            }
        """)
        
        self.save_btn = QPushButton("Create PDF")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
            QPushButton:pressed {
                background-color: #2E7D32;
            }
        """)
        
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.preview_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)
        central_widget.setLayout(layout)

    def setup_connections(self):
        """Connects all UI signals to their corresponding slots."""
        self.bg_color_btn.clicked.connect(self.select_bg_color)
        self.add_btn.clicked.connect(self.add_images)
        self.preview_btn.clicked.connect(self.preview_images)
        self.clear_btn.clicked.connect(self.list_widget.clear)
        self.save_btn.clicked.connect(self.save_pdf)

    def select_bg_color(self):
        """Opens a color dialog and updates the background color button style."""
        color = QColorDialog.getColor(self.page_bg_color)
        if color.isValid():
            self.page_bg_color = color
            self.bg_color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.page_bg_color.name()};
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                    padding: 5px 10px;
                }}
                QPushButton:hover {{
                    background-color: #f0f0f0;
                }}
            """)

    def add_images(self):
        """Opens a file dialog to select and add images to the list."""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Image Files (*.jpg *.jpeg *.png *.bmp *.tiff)")
        for f in files:
            self.list_widget.add_image_item(f)

    def preview_images(self):
        """Opens a dialog to preview the selected images."""
        images = [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
        if images:
            dlg = PreviewDialog(images)
            dlg.exec()
        else:
            QMessageBox.information(self, "No Images", "No images to preview.")

    def save_pdf(self):
        """Initiates the PDF creation process in a separate thread."""
        images = [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
        if not images:
            QMessageBox.critical(self, "Error", "No images selected!")
            return

        output_file, _ = QFileDialog.getSaveFileName(self, "Save PDF", "output.pdf", "PDF Files (*.pdf)")
        if output_file:
            self.set_ui_busy(True)
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            use_a4 = self.page_size_combo.currentText() == "A4 Page"
            self.worker = PDFWorker(images, output_file, use_a4, self.page_bg_color)
            self.worker.progress.connect(self.progress_bar.setValue)
            self.worker.finished.connect(self.pdf_finished)
            self.worker.start()

    def pdf_finished(self, failed_images):
        """Handles the completion of the PDF creation thread."""
        self.set_ui_busy(False)
        self.progress_bar.hide()
        if failed_images:
            QMessageBox.warning(self, "Partial Success", "PDF created, but some images failed:\n" + "\n".join(failed_images))
        else:
            QMessageBox.information(self, "Success", "PDF created successfully!")
        self.worker.deleteLater() # Clean up the worker thread object

    def set_ui_busy(self, busy):
        """Disables/enables buttons and changes the cursor during processing."""
        self.add_btn.setEnabled(not busy)
        self.preview_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.save_btn.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageToPDF()
    window.show()
    sys.exit(app.exec())