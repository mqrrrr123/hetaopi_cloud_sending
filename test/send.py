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
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5 import QtCore, QtGui, QtWidgets

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
    filename = generate_filename()  
    files = {'images': (filename, png_binary)}
    response = requests.post(server_url, files=files)
    return filename, response.json()

class CameraThread(QThread):
    image_updated = pyqtSignal(QtGui.QImage)
    
    def __init__(self, uuid, parent=None):
        super().__init__(parent)
        self.target_uuid = uuid
        self.running = True
    
    def run(self):
        try:
            self.cap = open_camera_by_uuid(self.target_uuid)
            while self.running:
                ret, frame = self.cap.read()
                if ret:
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qimage = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                    self.image_updated.emit(qimage)
                
                self.msleep(30)  
                
        except Exception as e:
            print(f"Camera error: {str(e)}")
        finally:
            if hasattr(self, 'cap') and self.cap.isOpened():
                self.cap.release()
    
    def stop(self):
        self.running = False
        self.wait()

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(640, 480)  
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        

        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton.setGeometry(QtCore.QRect(270, 380, 100, 30))
        self.pushButton.setObjectName("pushButton")
        

        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(20, 20, 600, 340))
        self.label.setText("no camera")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("background-color: black; color: white;")
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

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "camera"))
        self.pushButton.setText(_translate("MainWindow", "open"))
        
    def toggle_camera(self):

        if self.camera_thread and self.camera_thread.isRunning():
            self.stop_camera()
            self.pushButton.setText("open")
            self.label.setText("close")
        else:
            self.start_camera()
            self.pushButton.setText("close")
    
    def start_camera(self):

        try:
            self.camera_thread = CameraThread('9f7f9c0b-bd09-53db-9a2b-20daffdb4028')
            self.camera_thread.image_updated.connect(self.update_image)
            self.camera_thread.start()
        except Exception as e:
            self.label.setText(f"error {str(e)}")
    
    def stop_camera(self):

        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
    
    def update_image(self, qimage):

        pixmap = QtGui.QPixmap.fromImage(qimage)

        scaled = pixmap.scaled(
            self.label.width(), 
            self.label.height(),
            QtCore.Qt.KeepAspectRatio
        )
        self.label.setPixmap(scaled)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
    
    def closeEvent(self, event):

        self.stop_camera()
        event.accept()

if __name__ == "__main__":
    os.environ["DISPLAY"] = ":0.0"
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    
    MainWindow.closeEvent = ui.closeEvent

    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec_())