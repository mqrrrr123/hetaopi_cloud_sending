#!/usr/bin/env python3
import requests
import time
from datetime import datetime
import cv2
import itertools
import uuid
from pathlib import Path
import sys
import os
import subprocess
import threading
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QTimer, QSize
from PyQt5 import QtGui, QtWidgets, QtCore

counter = itertools.count(1)

def get_camera_uuid_map():
    return {
        '9f7f9c0b-bd09-53db-9a2b-20daffdb4028': '/dev/video0',
        '48b5ddac-a396-5275-b6cb-32edddb4b5bf': '/dev/video1'
    }

def open_camera_by_uuid(target_uuid, api_preference=cv2.CAP_V4L2):
    uuid_map = get_camera_uuid_map()
    
    if target_uuid not in uuid_map:
        available_uuids = "\n".join(uuid_map.keys())
        raise ValueError(f"Invalid UUID provided. Available UUIDs:\n{available_uuids}")
    
    device_path = uuid_map[target_uuid]
    
    if not Path(device_path).exists():
        raise FileNotFoundError(f"Camera device not found: {device_path}")
    
    cap = cv2.VideoCapture(device_path, api_preference)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, 400)

    if not cap.isOpened():
        raise RuntimeError(f"Failed to open camera at {device_path}")
    
    return cap

def generate_filename(prefix="image"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  
    return f"{prefix}_{timestamp}.png"

def send_image(png_binary, server_url):
    try:
        filename = generate_filename()  
        files = {'images': (filename, png_binary)}
        response = requests.post(server_url, files=files, timeout=5)
        return filename, response.json()
    except Exception as e:
        print(f"Error sending image: {str(e)}")
        return None, str(e)

class CameraThread(QThread):
    image_updated = pyqtSignal(QtGui.QImage)
    capture_image_ready = pyqtSignal(bytes) 
    initial_size_determined = pyqtSignal(QSize) # Signal for initial image size
    
    def __init__(self, uuid, parent=None):
        super().__init__(parent)
        self.target_uuid = uuid
        self.running = True
        self.capture_enabled = False
        self.current_frame = None
        self.lock = threading.Lock()
        self.initial_size_set = False
        self.PREVIEW_WIDTH = 420
        self.PREVIEW_HEIGHT = 180
    
    def run(self):
        try:
            self.cap = open_camera_by_uuid(self.target_uuid)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.current_frame = frame.copy()
                    
                    # Convert to RGB for display
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    
                    # Resize for small screen preview ()
                    resized = cv2.resize(rgb_image, (int(self.PREVIEW_WIDTH), int(self.PREVIEW_HEIGHT)))
                    resized_h, resized_w, _ = resized.shape
                    
                    bytes_per_line = 3 * resized_w
                    qimage = QtGui.QImage(resized.data, resized_w, resized_h, bytes_per_line, QtGui.QImage.Format_RGB888)
                    
                    # Emit initial size once
                    if not self.initial_size_set:
                        self.initial_size_determined.emit(QSize(w, h))
                        self.initial_size_set = True
                    
                    # Send preview image
                    self.image_updated.emit(qimage)
                
                if self.capture_enabled:
                    self.process_capture_request()
                    self.capture_enabled = False
                
                self.msleep(30)
                
        except Exception as e:
            print(f"Camera error: {str(e)}")
        finally:
            if hasattr(self, 'cap') and self.cap.isOpened():
                self.cap.release()
    
    def process_capture_request(self):
        with self.lock:
            if self.current_frame is not None:
                _, buffer = cv2.imencode('.png', self.current_frame)
                png_binary = buffer.tobytes()
                self.capture_image_ready.emit(png_binary)
    
    def stop(self):
        self.running = False
        self.wait()
    
    def request_capture(self):
        self.capture_enabled = True

class Ui_MainWindow(QObject):
    update_send_status = pyqtSignal(str, str)
    script_completed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.camera_thread = None  # 
        self.SERVER_IP = '192.168.83.135'
        self.PORT = 5000
        self.server_url = f'http://{self.SERVER_IP}:{self.PORT}/upload'
        
        self.external_script = "/home/pi/test/app_io.py"
        
        # Capture settings
        self.MAX_IMAGES = 60
        self.captured_count = 0
        
        # Timers
        self.statusbar_timer = QTimer()
        self.statusbar_timer.timeout.connect(self.update_status_time)
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_image)
        
        self.operation_time = 0
        self.operation_start_time = time.time()
        
        # UI state
        self.fixed_image_size = QSize(420, 180)
    
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("尿蛋白云存储")
        
        MainWindow.resize(480, 280)
        MainWindow.setMinimumSize(480, 280)
        MainWindow.setMaximumSize(480, 280)
        
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        # Main layout with tight spacing for small screen
        main_layout = QtWidgets.QVBoxLayout(self.centralwidget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(5)
        
        # Image display area - fixed size for small screen
        self.image_frame = QtWidgets.QFrame(self.centralwidget)
        self.image_frame_layout = QtWidgets.QVBoxLayout(self.image_frame)
        
        self.image_label = QtWidgets.QLabel(self.image_frame)
        self.image_label.setText("等待启动...")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: black;
                color: white;
                border: 1px solid #555;
                border-radius: 8px;
                font-size: 16px;
            }
        """)
        
        preview_width = 420
        preview_height = 180
        self.image_label.setFixedSize(preview_width, preview_height)
        self.image_frame.setFixedSize(preview_width, preview_height)
        
        self.image_frame_layout.addWidget(self.image_label)
        main_layout.addWidget(self.image_frame, 1, Qt.AlignCenter)
        
        # Status and control area - compact for small screen
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.setSpacing(6)
        
        # Status panel with smaller height
        status_frame = QtWidgets.QFrame(self.centralwidget)
        status_frame.setFixedHeight(60)
        status_layout = QtWidgets.QVBoxLayout(status_frame)
        status_layout.setContentsMargins(2, 2, 2, 2)
        
        self.status_label = QtWidgets.QLabel(status_frame)
        self.status_label.setText("准备就绪")
        self.status_label.setStyleSheet("font-size: 14px; color: #333; padding: 0px;")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        self.progress_label = QtWidgets.QLabel(status_frame)
        self.progress_label.setText("已发送照片: 0/60")
        self.progress_label.setStyleSheet("font-size: 12px; color: #555; padding: 0px;")
        self.progress_label.setAlignment(QtCore.Qt.AlignCenter)
        status_layout.addWidget(self.progress_label)
        
        self.timer_label = QtWidgets.QLabel(status_frame)
        self.timer_label.setText("记时: 00:00")
        self.timer_label.setStyleSheet("font-size: 12px; color: #555; padding: 0px;")
        self.timer_label.setAlignment(QtCore.Qt.AlignCenter)
        status_layout.addWidget(self.timer_label)
        
        control_layout.addWidget(status_frame)
        
        # Button panel - compact with smaller buttons
        button_frame = QtWidgets.QFrame(self.centralwidget)
        button_layout = QtWidgets.QVBoxLayout(button_frame)
        button_layout.setSpacing(4)
        
        # Start button
        self.start_button = QtWidgets.QPushButton(button_frame)
        self.start_button.setText("启动")
        self.start_button.setFixedHeight(42)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.start_button)
        
        # # Stop button
        # self.stop_button = QtWidgets.QPushButton(button_frame)
        # self.stop_button.setText("Stop")
        # self.stop_button.setFixedHeight(42)  #
        # self.stop_button.setStyleSheet("""
        #     QPushButton {
        #         background-color: #f44336;
        #         color: white;
        #         border-radius: 6px;
        #         font-size: 16px;
        #         font-weight: bold;
        #     }
        #     QPushButton:hover {
        #         background-color: #d32f2f;
        #     }
        #     QPushButton:disabled {
        #         background-color: #cccccc;
        #     }
        # """)
        # self.stop_button.setEnabled(False)
        # button_layout.addWidget(self.stop_button)
        
        self.close_button = QtWidgets.QPushButton(button_frame)
        self.close_button.setText("关闭")
        self.close_button.setFixedHeight(36)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        button_layout.addWidget(self.close_button)
        
        control_layout.addWidget(button_frame)
        main_layout.addLayout(control_layout)
        
        MainWindow.setCentralWidget(self.centralwidget)
        
        # Connect UI signals
        self.start_button.clicked.connect(self.start_capture)
        # self.stop_button.clicked.connect(self.stop_capture)
        self.close_button.clicked.connect(MainWindow.close)
        
        # Connect custom signals
        self.update_send_status.connect(self.handle_update_send_status)
        self.script_completed.connect(self.on_script_completed)
        
        # Program state
        self.external_script_running = False
        self.external_script_completed = False
    
    def start_capture(self):
        """Start the capture process"""
        try:
            if self.camera_thread and self.camera_thread.isRunning():
                return
            
            # Update UI state
            self.start_button.setEnabled(False)
            # self.stop_button.setEnabled(True)
            if self.close_button:
                self.close_button.setEnabled(False)
            
            # Start camera preview
            if self.status_label:
                self.status_label.setText("开始启动相机...")
            
            self.camera_thread = CameraThread('9f7f9c0b-bd09-53db-9a2b-20daffdb4028')
            
            # Connect signals
            if self.image_label:
                self.camera_thread.image_updated.connect(self.update_image)
            self.camera_thread.capture_image_ready.connect(self.handle_capture_complete)
            self.camera_thread.start()
            
            # Reset counters and timers
            self.captured_count = 0
            self.external_script_completed = False
            self.operation_start_time = time.time()
            self.operation_time = 0
            self.statusbar_timer.start(1000)
            self.update_status_time()
            
            # Start external script
            self.run_external_script()
            
        except Exception as e:
            print(f"Error starting capture: {str(e)}")
            if self.status_label:
                self.status_label.setText(f"Start failed: {str(e)}")
            self.start_button.setEnabled(True)
            # self.stop_button.setEnabled(False)
            if self.close_button:
                self.close_button.setEnabled(True)
    
    def run_external_script(self):
        """Execute the external Python script"""
        try:
            if self.status_label:
                self.status_label.setText("气泵运行中...")
            if self.progress_label:
                self.progress_label.setText("正在运行气泵")
            
            if not os.path.exists(self.external_script):
                if self.status_label:
                    self.status_label.setText(f"Script not found: {self.external_script}")
                self.script_completed.emit()
                return
                
            # Mark script as running
            self.external_script_running = True
            
            # Start script execution in separate thread
            threading.Thread(
                target=self.run_script_thread,
                daemon=True
            ).start()
            
        except Exception as e:
            if self.status_label:
                self.status_label.setText(f"Script error: {str(e)}")
            self.script_completed.emit()
    
    def run_script_thread(self):
        """Thread for running external script"""
        try:
            command = f"sudo python3 {self.external_script}"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            # Emit completion signal regardless of success
            self.script_completed.emit()
        except Exception as e:
            print(f"Error running script: {str(e)}")
            self.script_completed.emit()
    
    def on_script_completed(self):
        """Handle completion of external script"""
        self.external_script_running = False
        self.external_script_completed = True
        
        # Start capturing images
        if self.status_label:
            self.status_label.setText("开始捕获图像")
        self.capture_timer.start(1000)
    
    def capture_image(self):
        """Capture and send an image"""
        if (not self.camera_thread or 
            not self.camera_thread.isRunning() or 
            not self.external_script_completed):
            return
            
        if self.captured_count >= self.MAX_IMAGES:
            self.stop_capture()
            return
            
        # Request image capture
        self.camera_thread.request_capture()
        if self.status_label:
            self.status_label.setText("捕获图像...")
    
    def handle_capture_complete(self, image_data):
        """Process captured image"""
        if self.external_script_completed and self.captured_count < self.MAX_IMAGES:
            if self.status_label:
                self.status_label.setText(f"发送图片 {self.captured_count+1}/{self.MAX_IMAGES}...")
            threading.Thread(
                target=self.send_image_thread,
                args=(image_data,),
                daemon=True
            ).start()
            
            # Update image counter
            self.captured_count += 1
            if self.progress_label:
                self.progress_label.setText(f"图片: {self.captured_count}/{self.MAX_IMAGES}")
            
            # Stop after reaching max images
            if self.captured_count >= self.MAX_IMAGES:
                self.stop_capture()
    
    def send_image_thread(self, image_data):
        """Thread for sending images to server"""
        try:
            filename, response = send_image(image_data, self.server_url)
            self.update_send_status.emit(filename, str(response))
        except Exception as e:
            self.update_send_status.emit("", f"Send error: {str(e)}")
    
    def handle_update_send_status(self, filename, response):
        """Update UI with send status"""
        if filename and self.status_label:
            self.status_label.setText(f"发送 {filename}")
        elif self.status_label:
            self.status_label.setText(response)
    
    def update_status_time(self):
        """Update operation timer"""
        self.operation_time = int(time.time() - self.operation_start_time)
        minutes = self.operation_time // 60
        seconds = self.operation_time % 60
        if self.timer_label:
            self.timer_label.setText(f"Time: {minutes:02d}:{seconds:02d}")
    
    def stop_capture(self):
        """Stop all capture processes"""
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
        
        if self.capture_timer.isActive():
            self.capture_timer.stop()
            
        if self.statusbar_timer.isActive():
            self.statusbar_timer.stop()
        
        self.external_script_running = False
        self.external_script_completed = False
        
        # Update UI state
        if self.start_button:
            self.start_button.setEnabled(True)
        # if self.stop_button:
        #     self.stop_button.setEnabled(False)
        if self.close_button:
            self.close_button.setEnabled(True)
        
        if self.captured_count >= self.MAX_IMAGES and self.status_label:
            self.status_label.setText(f"完成! 捕获 {self.MAX_IMAGES} 图片")
    
    def update_image(self, qimage):
        """Display the image using fixed size (without scaling)"""
        if self.image_label:
            # Create pixmap directly from QImage
            pixmap = QtGui.QPixmap.fromImage(qimage)
            
            # Set pixmap without scaling
            self.image_label.setPixmap(pixmap)

    def closeEvent(self, event):
        """Clean up on application close"""
        self.stop_capture()
        event.accept()

class CameraApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.setWindowTitle("尿蛋白云存储")
        self.setMinimumSize(480, 280)
        self.setMaximumSize(480, 280)
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.ui.closeEvent(event)
        event.accept()
        
    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
    
    def resizeEvent(self, event):
        """Clear pixmap on resize to prevent artifacts"""
        super().resizeEvent(event)
        if hasattr(self.ui, 'image_label'):
            self.ui.image_label.setPixmap(QtGui.QPixmap())

if __name__ == "__main__":
    os.environ["DISPLAY"] = ":0.0"
    
    app = QtWidgets.QApplication(sys.argv)
    
    
    app.setStyle("Fusion")
    font = QtGui.QFont()
    font.setPointSize(10)
    app.setFont(font)
    
    main_window = CameraApp()
    main_window.show()
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec_())