import sys
import os
import subprocess
import re
import threading
from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, 
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout, 
    QLabel, 
    QComboBox, 
    QPushButton, 
    QMessageBox,
    QFileDialog
)

class OpenRec(QWidget):
    def __init__(self):
        super().__init__()
        self.recording_process = None
        self.is_paused = False
        self.monitors = self.detect_monitors()
        
        self.segment_files = []
        self.current_segment_file = ""
        
        self.output_dir = os.path.expanduser(os.path.join("~", "Videos", "OpenRec"))
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.encoder_preset = "ultrafast"
        self.output_format = "mp4"
        self.video_speed = "1x"
        
        self.init_ui()

    def detect_monitors(self):
        monitors = {}
        try:
            output = subprocess.check_output(["xrandr"]).decode("utf-8")
            matches = re.findall(r"(\S+) connected (primary )?(\d+x\d+\+\d+\+\d+)", output)
            
            for match in matches:
                name = match[0]
                geometry = match[2]
                is_primary = match[1] != ""
                
                res, x_off, y_off = re.split(r'\+', geometry)
                
                monitors[name] = {
                    "resolution": res,
                    "offset_x": x_off,
                    "offset_y": y_off,
                    "is_primary": is_primary,
                    "display_str": f"{name} ({res})"
                }
        except Exception:
            monitors["Default"] = {"resolution": "1920x1080", "offset_x": "0", "offset_y": "0", "is_primary": True, "display_str": "Default Display"}
        
        return monitors

    def init_ui(self):
        self.setWindowTitle("OpenRec")
        self.setFixedSize(360, 400)
        
        logo_path = os.path.join("assets", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
            self.lbl_logo.setPixmap(scaled_pixmap)
        else:
            self.lbl_logo.setText("<b>OpenRec</b>")
            self.lbl_logo.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.lbl_logo)

        row1 = QHBoxLayout()
        lbl_monitor = QLabel("Monitor:")
        self.combo_monitor = QComboBox()
        monitor_choices = [m["display_str"] for m in self.monitors.values()]
        self.combo_monitor.addItems(monitor_choices)
        
        primary_index = 0
        for idx, m in enumerate(self.monitors.values()):
            if m["is_primary"]:
                primary_index = idx
                break
        self.combo_monitor.setCurrentIndex(primary_index)
        row1.addWidget(lbl_monitor)
        row1.addWidget(self.combo_monitor, 1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_fps = QLabel("Frame Rate:")
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["60", "30", "24", "15"])
        self.combo_fps.setCurrentText("30")
        row2.addWidget(lbl_fps)
        row2.addWidget(self.combo_fps, 1)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        lbl_audio = QLabel("Audio Source:")
        self.combo_audio = QComboBox()
        self.combo_audio.addItems([
            "None",
            "Speakers Only",
            "Microphone Only",
            "Speakers & Microphone"
        ])
        self.combo_audio.setCurrentText("None")
        row3.addWidget(lbl_audio)
        row3.addWidget(self.combo_audio, 1)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        self.btn_more = QPushButton("More Options")
        self.btn_more.clicked.connect(self.open_more_options)
        row4.addWidget(self.btn_more)
        layout.addLayout(row4)

        row5 = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self.start_recording)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(self.stop_recording)

        row5.addWidget(self.btn_start)
        row5.addWidget(self.btn_pause)
        row5.addWidget(self.btn_stop)
        layout.addLayout(row5)

        self.setLayout(layout)

    def build_ffmpeg_command(self, segment_index):
        selected_text = self.combo_monitor.currentText()
        monitor_data = next(m for m in self.monitors.values() if m["display_str"] == selected_text)
        
        res = monitor_data["resolution"]
        fps = self.combo_fps.currentText()
        display = f":0.0+{monitor_data['offset_x']},{monitor_data['offset_y']}"
        audio_choice = self.combo_audio.currentText()
        
        self.current_segment_file = os.path.join(self.output_dir, f"part_{segment_index}.{self.output_format}")
        self.segment_files.append(self.current_segment_file)

        logo_path = os.path.abspath(os.path.join("assets", "logo.png"))
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-video_size", res,
            "-framerate", fps,
            "-i", display
        ]

        if os.path.exists(logo_path):
            cmd.extend(["-i", logo_path])

        if audio_choice == "Speakers Only":
            cmd.extend(["-f", "oss", "-i", "/dev/dsp"])
        elif audio_choice == "Microphone Only":
            cmd.extend(["-f", "alsa", "-i", "hw:0"])
        elif audio_choice == "Speakers & Microphone":
            cmd.extend([
                "-f", "oss", "-i", "/dev/dsp",
                "-f", "alsa", "-i", "hw:0"
            ])

        filter_chains = []
        
        if self.video_speed == "0.5x":
            filter_chains.append("[0:v]setpts=2.0*PTS[vspeed]")
        elif self.video_speed == "1.5x":
            filter_chains.append("[0:v]setpts=0.66*PTS[vspeed]")
        elif self.video_speed == "2x":
            filter_chains.append("[0:v]setpts=0.5*PTS[vspeed]")
        else:
            filter_chains.append("[0:v]null[vspeed]")

        if audio_choice == "Speakers & Microphone":
            if self.video_speed == "0.5x":
                filter_chains.append("amix=inputs=2:duration=first,atempo=0.5[aspeed]")
            elif self.video_speed == "1.5x":
                filter_chains.append("amix=inputs=2:duration=first,atempo=1.5[aspeed]")
            elif self.video_speed == "2x":
                filter_chains.append("amix=inputs=2:duration=first,atempo=2.0[aspeed]")
            else:
                filter_chains.append("amix=inputs=2:duration=first[aspeed]")
        elif audio_choice != "None":
            if self.video_speed == "0.5x":
                filter_chains.append("[2:a]atempo=0.5[aspeed]")
            elif self.video_speed == "1.5x":
                filter_chains.append("[2:a]atempo=1.5[aspeed]")
            elif self.video_speed == "2x":
                filter_chains.append("[2:a]atempo=2.0[aspeed]")
            else:
                filter_chains.append("[2:a]anull[aspeed]")

        if os.path.exists(logo_path):
            filter_chains.append("[1:v]format=rgba,colorchannelmixer=aa=0.5,scale=100:-1[wm]")
            filter_chains.append("[vspeed][wm]overlay=main_w-overlay_w-10:main_h-overlay_h-10")

        if filter_chains:
            cmd.extend(["-filter_complex", ";".join(filter_chains)])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", self.encoder_preset
        ])

        if audio_choice != "None":
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.append("-an")

        cmd.append(self.current_segment_file)
        return cmd

    def start_recording(self):
        self.segment_files = []
        self.is_paused = False
        self.btn_pause.setText("Pause")
        
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.combo_monitor.setEnabled(False)
        self.combo_fps.setEnabled(False)
        self.combo_audio.setEnabled(False)
        self.btn_more.setEnabled(False)

        cmd = self.build_ffmpeg_command(len(self.segment_files))
        self.start_ffmpeg_process(cmd)

    def start_ffmpeg_process(self, cmd):
        self.recording_process = subprocess.Popen(
            cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

    def toggle_pause(self):
        if not self.recording_process:
            return

        if not self.is_paused:
            try:
                self.recording_process.communicate(b'q', timeout=2)
            except Exception:
                self.recording_process.terminate()
            
            self.is_paused = True
            self.btn_pause.setText("Resume")
        else:
            cmd = self.build_ffmpeg_command(len(self.segment_files))
            self.start_ffmpeg_process(cmd)
            
            self.is_paused = False
            self.btn_pause.setText("Pause")

    def stop_recording(self):
        if not self.is_paused and self.recording_process:
            try:
                self.recording_process.communicate(b'q', timeout=2)
            except Exception:
                self.recording_process.terminate()

        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        final_output_file = os.path.join(self.output_dir, f"{timestamp}.{self.output_format}")

        if self.segment_files:
            if len(self.segment_files) > 1:
                list_file_path = os.path.join(self.output_dir, "concat_list.txt")
                with open(list_file_path, "w") as f:
                    for seg in self.segment_files:
                        f.write(f"file '{os.path.abspath(seg)}'\n")
                
                concat_cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file_path,
                    "-c", "copy",
                    final_output_file
                ]
                subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                try:
                    os.remove(list_file_path)
                    for seg in self.segment_files:
                        os.remove(seg)
                except Exception:
                    pass
            else:
                os.rename(self.segment_files[0], final_output_file)

        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.combo_monitor.setEnabled(True)
        self.combo_fps.setEnabled(True)
        self.combo_audio.setEnabled(True)
        self.btn_more.setEnabled(True)
        self.btn_pause.setText("Pause")
        
        QMessageBox.information(self, "OpenRec", f"Recording saved to:\n{final_output_file}")

    def open_more_options(self):
        self.more_window = MoreOptionsWindow(self)
        self.more_window.show()
        self.close()

class MoreOptionsWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("OpenRec - More Options")
        self.setFixedSize(360, 400)
        
        logo_path = os.path.join("assets", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
            self.lbl_logo.setPixmap(scaled_pixmap)
        else:
            self.lbl_logo.setText("<b>OpenRec</b>")
            self.lbl_logo.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.lbl_logo)

        row1 = QHBoxLayout()
        lbl_preset = QLabel("Encoder Preset:")
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"])
        self.combo_preset.setCurrentText(self.main_window.encoder_preset)
        row1.addWidget(lbl_preset)
        row1.addWidget(self.combo_preset, 1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl_format = QLabel("Output Container:")
        self.combo_format = QComboBox()
        self.combo_format.addItems(["mp4", "mkv", "avi"])
        self.combo_format.setCurrentText(self.main_window.output_format)
        row2.addWidget(lbl_format)
        row2.addWidget(self.combo_format, 1)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        lbl_speed = QLabel("Recording Speed:")
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.5x", "1x", "1.5x", "2x"])
        self.combo_speed.setCurrentText(self.main_window.video_speed)
        row3.addWidget(lbl_speed)
        row3.addWidget(self.combo_speed, 1)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        lbl_path = QLabel("Save Location:")
        self.btn_path = QPushButton("Browse...")
        self.btn_path.clicked.connect(self.choose_directory)
        row4.addWidget(lbl_path)
        row4.addWidget(self.btn_path, 1)
        layout.addLayout(row4)

        row5 = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back)
        row5.addWidget(self.btn_back)
        layout.addLayout(row5)

        self.setLayout(layout)

    def choose_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.main_window.output_dir)
        if dir_path:
            self.main_window.output_dir = dir_path

    def go_back(self):
        self.main_window.encoder_preset = self.combo_preset.currentText()
        self.main_window.output_format = self.combo_format.currentText()
        self.main_window.video_speed = self.combo_speed.currentText()
        self.main_window.show()
        self.close()

if __name__ == "__main__":
    if os.system("which ffmpeg > /dev/null 2>&1") != 0:
        print("Error: FFmpeg must be installed to run OpenRec.")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
    window = OpenRec()
    window.show()
    sys.exit(app.exec())
