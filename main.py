#!/usr/bin/env python3
import subprocess as s, time as t, sys, threading as th, os
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QFileDialog
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

try:
 r = s.check_output("xrandr | grep 'current'", shell=True).decode().split("current")[1].split(",")[0].replace(" ","").split("x")
 res = f"{r[0]}x{r[1]}"
except: res = "1920x1080"

p, active = None, False
save_dir = os.path.expanduser("~")

def record_worker(cmd):
    global p
    p = s.Popen(cmd, stdin=s.PIPE, stdout=s.DEVNULL, stderr=s.DEVNULL)
    p.wait()

def choose_dir():
    global save_dir
    d = QFileDialog.getExistingDirectory(w, "Select Output Directory", save_dir)
    if d:
        save_dir = d
        lbl_dir.setText(f"Folder: ...{os.path.basename(save_dir)}")

def toggle():
    global p, active
    f_path = os.path.join(save_dir, f"{t.strftime('%m-%d-%Y')}.mp4")
    if not active:
        selected_res = box.currentText()
        fps_val = fps.currentText()
        crf_map = {"Ultra": "18", "High": "23", "Medium": "28"}
        crf = crf_map.get(quality.currentText(), "23")
        
        cmd = ["ffmpeg", "-y", "-f", "x11grab", "-r", fps_val, "-video_size", selected_res, "-i", ":0.0"]
        if audio.isChecked():
            cmd += ["-f", "pulse", "-i", "default"]
        cmd += ["-c:v", "libx264", "-crf", crf, "-pix_fmt", "yuv420p", f_path]
        
        active = True
        btn.setText("Stop Recording (Active...)")
        for widget in [box, fps, quality, audio, btn_dir]: widget.setEnabled(False)
        
        th.Thread(target=record_worker, args=(cmd,), daemon=True).start()
    else:
        active = False
        if p and p.poll() is None: 
            try:
                p.communicate(b'q\n', timeout=3)
            except:
                p.terminate()
                
        btn.setText("Start Recording")
        for widget in [box, fps, quality, audio, btn_dir]: widget.setEnabled(True)

app = QApplication(sys.argv)
app.setStyle("Fusion") 

w = QWidget()
w.setWindowTitle("OpenRec")
w.setFixedSize(360, 360) # Shrunk height since status label is gone

lay = QVBoxLayout()
lay.setContentsMargins(12, 12, 12, 12)
lay.setSpacing(6)

logo_path = "/usr/share/openrec/assets/logo.png"
if not os.path.exists(logo_path):
    logo_path = "assets/logo.png"

logo = QLabel()
if os.path.exists(logo_path):
    pix = QPixmap(logo_path)
    if not pix.isNull():
        logo.setPixmap(pix.scaledToWidth(100, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)
        lay.addSpacing(6)

lay.addWidget(QLabel("Resolution:"))
box = QComboBox()
resolutions = ["3840x2160", "2560x1440", "1920x1080", "1600x900", "1366x768", "1280x720"]
if res not in resolutions: resolutions.insert(0, res)
box.addItems(resolutions)
box.setCurrentText(res)
lay.addWidget(box)
lay.addSpacing(6)

row1 = QHBoxLayout()
v1 = QVBoxLayout()
v1.addWidget(QLabel("Frame Rate:"))
fps = QComboBox()
fps.addItems(["60", "30"])
v1.addWidget(fps)
row1.addLayout(v1)

v2 = QVBoxLayout()
v2.addWidget(QLabel("Video Quality:"))
quality = QComboBox()
quality.addItems(["High", "Ultra", "Medium"])
v2.addWidget(quality)
row1.addLayout(v2)
lay.addLayout(row1)
lay.addSpacing(6)

row2 = QHBoxLayout()
v3 = QVBoxLayout()
v3.addWidget(QLabel("Output Folder:"))
btn_dir = QPushButton("Browse...")
btn_dir.clicked.connect(choose_dir)
v3.addWidget(btn_dir)
row2.addLayout(v3)

v4 = QVBoxLayout()
v4.addWidget(QLabel("Audio Options:"))
audio = QCheckBox("Enable Sound")
v4.addWidget(audio)
row2.addLayout(v4)
lay.addLayout(row2)
lay.addSpacing(6)

lbl_dir = QLabel(f"Folder: ...{os.path.basename(save_dir)}")
lay.addWidget(lbl_dir)
lay.addSpacing(10)

btn = QPushButton("Start Recording")
btn.setMinimumHeight(32)
btn.clicked.connect(toggle)
lay.addWidget(btn)

w.setLayout(lay)
w.show()
sys.exit(app.exec())
