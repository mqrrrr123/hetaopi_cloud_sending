# -*- coding: utf-8 -*-
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
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QTimer
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
        raise ValueError(f"no UUID please\n{available_uuids}")
    
    device_path = uuid_map[target_uuid]
    
    if not Path(device_path).exists():
        raise FileNotFoundError(f" {device_path} no cameras")
    
    cap = cv2.VideoCapture(device_path, api_preference)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, 400)

    if not cap.isOpened():
        raise RuntimeError(f" {device_path} no get")
    
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
    
    def __init__(self, uuid, parent=None):
        super().__init__(parent)
        self.target_uuid = uuid
        self.running = True
        self.capture_enabled = False
        self.current_frame = None
        self.lock = threading.Lock()
    
    def run(self):
        try:
            self.cap = open_camera_by_uuid(self.target_uuid)
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.current_frame = frame.copy()
                    
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qimage = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
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
        super().__init__()  #
        self.SERVER_IP = '192.168.148.135'
        self.PORT = 5000
        self.server_url = f'http://{self.SERVER_IP}:{self.PORT}/upload'
        
        self.external_script = "/home/pi/test/app_io.py"
        
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(self.capture_and_send)
        
        self.update_send_status.connect(self.handle_update_send_status)
        self.script_completed.connect(self.on_script_completed)  
        
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(640, 480)  
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        self.status_label = QtWidgets.QLabel(self.centralwidget)
        self.status_label.setGeometry(QtCore.QRect(20, 350, 600, 20))
        self.status_label.setObjectName("status_label")

        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton.setGeometry(QtCore.QRect(270, 380, 100, 30))
        self.pushButton.setObjectName("pushButton")
        
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(20, 20, 600, 340))
        self.label.setText("no camera")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                background-color: black;
                color: white;
                border: 1px solid gray;
            }
        """)
        self.label.setObjectName("label")
        
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 640, 22))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        self.camera_thread = None
        self.pushButton.clicked.connect(self.toggle_camera)
        self.external_script_running = False  
        self.external_script_completed = False  

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Camera Monitor"))
        self.pushButton.setText(_translate("MainWindow", "Start Camera"))
        self.status_label.setText("Ready")
        
    def handle_update_send_status(self, filename, response):
        if filename:
            self.status_label.setText(f"Image sent: {filename}, response: {response}")
        else:
            self.status_label.setText(response)
    
    def toggle_camera(self):
        if self.camera_thread and self.camera_thread.isRunning():
            self.stop_camera()
            self.pushButton.setText("Start Camera")
            self.status_label.setText("Camera stopped")
        else:
            self.start_camera()
            self.pushButton.setText("Stop Camera")
            self.status_label.setText("Starting camera...")
    
    def start_camera(self):
        try:
            self.camera_thread = CameraThread('9f7f9c0b-bd09-53db-9a2b-20daffdb4028')
            self.camera_thread.image_updated.connect(self.update_image)
            self.camera_thread.capture_image_ready.connect(self.handle_capture_complete)
            self.camera_thread.start()
            
            self.run_external_script()
            
            self.status_label.setText("Running external script...")
            
        except Exception as e:
            self.label.setText(f"Error: {str(e)}")
            self.status_label.setText(f"Camera start failed: {str(e)}")
    
    def run_external_script(self):
        try:
            if not os.path.exists(self.external_script):
                self.status_label.setText(f"Script not found: {self.external_script}")
                self.script_completed.emit()  
                return
                
            self.external_script_running = True
            self.external_script_completed = False
            
            threading.Thread(
                target=self.run_script_thread,
                daemon=True
            ).start()
            
            self.status_label.setText(f"Running external script...")
        except Exception as e:
            self.status_label.setText(f"Error running script: {str(e)}")
            self.script_completed.emit()  
    
    def run_script_thread(self):
        try:
            command = f"sudo python3 {self.external_script}"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return_code = result.returncode
            
            self.script_completed.emit()
        except Exception as e:
            print(f"Error running script: {str(e)}")
            self.script_completed.emit()
    
    def on_script_completed(self):
        self.external_script_running = False
        self.external_script_completed = True
        
        self.capture_timer.start(1000)
        self.status_label.setText("External script completed, start capturing")
    
    def monitor_script_output(self, process):
        pass
    
    def capture_and_send(self):
        if (self.camera_thread and 
            self.camera_thread.isRunning() and 
            self.external_script_completed):
            self.camera_thread.request_capture()
            self.status_label.setText("Capturing image...")
    
    def handle_capture_complete(self, image_data):
        if self.external_script_completed:
            self.status_label.setText("Sending image to server...")
            threading.Thread(
                target=self.send_image_thread,
                args=(image_data,),
                daemon=True
            ).start()
    
    def send_image_thread(self, image_data):
        try:
            filename, response = send_image(image_data, self.server_url)
            self.update_send_status.emit(filename, str(response))
        except Exception as e:
            self.update_send_status.emit("", f"Send error: {str(e)}")
    
    def stop_camera(self):
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
            self.label.clear()
            self.label.setText("Camera stopped")
        
        if self.capture_timer.isActive():
            self.capture_timer.stop()
    
    def update_image(self, qimage):
        pixmap = QtGui.QPixmap.fromImage(qimage)

        scaled = pixmap.scaled(
            self.label.width(), 
            self.label.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.label.setPixmap(scaled)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
    
    def closeEvent(self, event):
        self.stop_camera()
        event.accept()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
    
    def closeEvent(self, event):
        self.ui.closeEvent(event)
        event.accept()

if __name__ == "__main__":

    os.environ["DISPLAY"] = ":0.0"

    app = QtWidgets.QApplication(sys.argv)
    

    main_window = MainWindow()
    main_window.show()
    

    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    sys.exit(app.exec_())