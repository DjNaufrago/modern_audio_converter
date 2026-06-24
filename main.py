import sys
import os
import configparser
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QListWidget, QComboBox, QPushButton, 
                             QListWidgetItem, QListView, QLineEdit, QFileDialog, QProgressBar, QFrame)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon

# ==============================================================================
# 1. TRABAJADOR BACK-END (Ejecuta FFmpeg en segundo plano)
# ==============================================================================
class ConversorWorker(QObject):
    progreso = pyqtSignal(int)
    archivo_actual = pyqtSignal(str)
    finalizado = pyqtSignal()

    def __init__(self, lista_tareas):
        super().__init__()
        self.lista_tareas = lista_tareas
        self.corriendo = True

    def obtener_duracion(self, ruta_archivo):
        """Usa ffprobe para obtener la duración exacta del audio en segundos"""
        try:
            comando = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', ruta_archivo]
            resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            return float(resultado.stdout.strip())
        except Exception:
            return 0.0

    def iniciar_proceso(self):
        total_tareas = len(self.lista_tareas)
        
        for indice, tarea in enumerate(self.lista_tareas):
            if not self.corriendo:
                break
                
            entrada = tarea["entrada"]
            salida = tarea["salida"]
            argumentos = tarea["argumentos"]
            nombre_breve = os.path.basename(entrada)

            self.archivo_actual.emit(nombre_breve)
            duracion_total = self.obtener_duracion(entrada)
            
            # Lógica inteligente para heredar carátulas en MP3 y formatos que lo soportan
            if salida.lower().endswith('.mp3'):
                # -map 0:a (mapea todo el audio), -map 0:v? (mapea video/caratula si existe)
                # -c:v copy (copia la imagen intacta), -disposition:v attached_pic (la marca como portada)
                argumentos_caratula = ['-map', '0:a', '-map', '0:v?', '-c:v', 'copy', '-disposition:v', 'attached_pic']
                comando = ['ffmpeg', '-y', '-i', entrada] + argumentos_caratula + argumentos + ['-progress', 'pipe:1', salida]
            else:
                # Para el resto de formatos (WAV, FLAC, AAC) mantiene la estructura limpia
                comando = ['ffmpeg', '-y', '-i', entrada] + argumentos + ['-progress', 'pipe:1', salida]

            try:
                proceso = subprocess.Popen(
                    comando,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )

                while proceso.poll() is None:
                    linea = proceso.stdout.readline()
                    if "out_time_us=" in linea:
                        try:
                            us = float(linea.split("=")[1].strip())
                            segundos_procesados = us / 1000000.0
                            
                            if duracion_total > 0:
                                progreso_archivo = (segundos_procesados / duracion_total) * 100
                                progreso_global = int(((indice / total_tareas) * 100) + (progreso_archivo / total_tareas))
                                self.progreso.emit(min(progreso_global, 100))
                        except Exception:
                            pass

                proceso.wait()
            except Exception as e:
                print(f"Error procesando {nombre_breve}: {e}")

        self.progreso.emit(100)
        self.finalizado.emit()

    def detener(self):
        self.corriendo = False


# ==============================================================================
# 2. INTERFAZ FRONT-END (Administra la UI y las interacciones del usuario)
# ==============================================================================
class AudioConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        
        self.opciones_calidad = {
            "FLAC": ["5 (Estándar)", "0 (Compresión Mínima)", "8 (Compresión Máxima)"],
            "MP3": ["CBR 320kbps", "CBR 256kbps", "CBR 224kbps", "VBR V0 (~245 kbps)", "VBR V2 (~190 kbps)"],
            "AAC / M4A": ["CBR 256kbps (Alta Calidad)", "CBR 192kbps", "CBR 128kbps"],
            "WAV": ["16-bit PCM (Calidad CD)", "24-bit PCM (Alta Resolución)"]
        }
        
        self.MAPEO_FFMPEG = {
            "FLAC": {
                "5 (Estándar)": ["-c:a", "flac", "-compression_level", "5"],
                "0 (Compresión Mínima)": ["-c:a", "flac", "-compression_level", "0"],
                "8 (Compresión Máxima)": ["-c:a", "flac", "-compression_level", "8"]
            },
            "MP3": {
                "CBR 320kbps": ["-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3"],
                "CBR 256kbps": ["-c:a", "libmp3lame", "-b:a", "256k", "-id3v2_version", "3"],
                "CBR 224kbps": ["-c:a", "libmp3lame", "-b:a", "224k", "-id3v2_version", "3"],
                "VBR V0 (~245 kbps)": ["-c:a", "libmp3lame", "-q:a", "0", "-id3v2_version", "3"],
                "VBR V2 (~190 kbps)": ["-c:a", "libmp3lame", "-q:a", "2", "-id3v2_version", "3"]
            },
            "AAC / M4A": {
                "CBR 256kbps (Alta Calidad)": ["-c:a", "aac", "-b:a", "256k"],
                "CBR 192kbps": ["-c:a", "aac", "-b:a", "192k"],
                "CBR 128kbps": ["-c:a", "aac", "-b:a", "128k"]
            },
            "WAV": {
                "16-bit PCM (Calidad CD)": ["-c:a", "pcm_s16le"],
                "24-bit PCM (Alta Resolución)": ["-c:a", "pcm_s24le"]
            }
        }

        self.TEXTOS_IDIOMA = {
            "es": {
                "titulo": "Audio Converter Modern",
                "zona_arrastre": "Arrastra tus archivos de audio aquí\n(Los archivos se cargarán en la cola inferior)",
                "cola_conversion": "Cola de conversión:",
                "carpeta_destino": "Carpeta de destino:",
                "btn_buscar": "Buscar...",
                "btn_convertir": "Iniciar Conversión",
                "vacio_alert": "La cola está vacía. No hay nada que convertir.",
                "procesando": "Procesando: ",
                "listo": "¡Conversión Finalizada con Éxito!"
            },
            "en": {
                "titulo": "Modern Audio Converter",
                "zona_arrastre": "Drag your audio files here\n(Files will be loaded into the queue below)",
                "cola_conversion": "Conversion queue:",
                "carpeta_destino": "Destination folder:",
                "btn_buscar": "Browse...",
                "btn_convertir": "Start Conversion",
                "vacio_alert": "The queue is empty. There is nothing to convert.",
                "procesando": "Processing: ",
                "listo": "Conversion Completed Successfully!"
            }
        }

        # Detectar si corre como ejecutable compilado (.exe) o como script (.py)
        if getattr(sys, 'frozen', False):
            carpeta_base = os.path.dirname(sys.executable)
        else:
            carpeta_base = os.path.dirname(os.path.abspath(__file__))

        self.ruta_config = os.path.join(carpeta_base, "config.ini")
        self.cargar_o_crear_config()
        self.init_ui()

    def cargar_o_crear_config(self):
        config = configparser.ConfigParser()
        if not os.path.exists(self.ruta_config):
            config["General"] = {"Idioma": "es", "Tema": "oscuro"}
            config["Conversor"] = {"UltimoFormato": "FLAC", "UltimaCalidad": "5 (Estándar)"}
            with open(self.ruta_config, "w", encoding="utf-8") as f:
                f.write("; Guía de usuario del convertidor\n; idioma: es o en\n; tema: oscuro o claro\n")
                config.write(f)
                
        config.read(self.ruta_config, encoding="utf-8")
        self.idioma_actual = config.get("General", "Idioma", fallback="es").lower()
        self.tema_actual = config.get("General", "Tema", fallback="oscuro").lower()
        self.ultimo_formato = config.get("Conversor", "UltimoFormato", fallback="FLAC")
        self.ultima_calidad = config.get("Conversor", "UltimaCalidad", fallback="5 (Estándar)")
        
        if self.idioma_actual not in self.TEXTOS_IDIOMA:
            self.idioma_actual = "es"
        self.txt = self.TEXTOS_IDIOMA[self.idioma_actual]

    def init_ui(self):
        self.setWindowTitle(self.txt["titulo"])
        self.setFixedSize(600, 540)  
        self.setAcceptDrops(True)

        ruta_script = os.path.dirname(os.path.abspath(__file__))
        # Código inteligente para que la ventana tenga icono siempre
        if hasattr(sys, '_MEIPASS'):
            ruta_icono = os.path.join(sys._MEIPASS, "main.ico") # <-- Solo .ico
        else:
            ruta_icono = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.ico") # <-- Solo .ico

        if os.path.exists(ruta_icono):
            self.setWindowIcon(QIcon(ruta_icono))

        contenedor_principal = QFrame(self)
        contenedor_principal.setObjectName("ContenedorPrincipal")
        contenedor_principal.setFixedSize(600, 540)

        layout_global = QVBoxLayout(contenedor_principal)
        layout_global.setSpacing(14)  
        layout_global.setContentsMargins(20, 18, 20, 20)

        self.zona_arrastre = QLabel(self.txt["zona_arrastre"], self)
        self.zona_arrastre.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zona_arrastre.setFixedHeight(90)
        self.zona_arrastre.setObjectName("ZonaArrastre")
        layout_global.addWidget(self.zona_arrastre)

        layout_cola = QVBoxLayout()
        layout_cola.setSpacing(4) 
        label_cola = QLabel(self.txt["cola_conversion"])
        label_cola.setObjectName("LabelSubtitulo")
        
        self.lista_archivos = QListWidget()
        self.lista_archivos.setFixedHeight(210)  
        self.lista_archivos.keyPressEvent = self.manejar_teclado_lista
        
        layout_cola.addWidget(label_cola)
        layout_cola.addWidget(self.lista_archivos)
        layout_global.addLayout(layout_cola)

        layout_destino = QVBoxLayout()
        layout_destino.setSpacing(4) 
        label_destino = QLabel(self.txt["carpeta_destino"])
        label_destino.setObjectName("LabelSubtitulo")
        
        fila_destino = QHBoxLayout()
        self.txt_destino = QLineEdit()
        self.txt_destino.setReadOnly(True)
        self.txt_destino.setText(self.obtener_carpeta_musica_nativa())
        
        btn_buscar = QPushButton(self.txt["btn_buscar"])
        btn_buscar.setObjectName("BotonSecundario")
        btn_buscar.setFixedWidth(90)
        btn_buscar.clicked.connect(self.seleccionar_carpeta)
        
        fila_destino.addWidget(self.txt_destino)
        fila_destino.addWidget(btn_buscar)
        layout_destino.addWidget(label_destino)
        layout_destino.addLayout(fila_destino)
        layout_global.addLayout(layout_destino)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setRange(0, 100)
        self.barra_progreso.setValue(0)
        self.barra_progreso.setTextVisible(True)
        self.barra_progreso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.barra_progreso.setFixedHeight(18)
        layout_global.addWidget(self.barra_progreso)

        fila_inferior = QHBoxLayout()
        fila_inferior.setSpacing(8)

        self.selector_formato = QComboBox()
        self.selector_formato.setFixedWidth(110) 
        self.selector_formato.addItems(list(self.opciones_calidad.keys()))
        self.selector_formato.setView(QListView(self.selector_formato))

        self.selector_calidad = QComboBox()
        self.selector_calidad.setFixedWidth(210) 
        self.selector_calidad.setView(QListView(self.selector_calidad))
        
        self.selector_formato.currentIndexChanged.connect(self.actualizar_lista_calidades)
        self.actualizar_lista_calidades()

        idx_formato = self.selector_formato.findText(self.ultimo_formato)
        if idx_formato >= 0:
            self.selector_formato.setCurrentIndex(idx_formato)
            self.actualizar_lista_calidades()
            
        idx_calidad = self.selector_calidad.findText(self.ultima_calidad)
        if idx_calidad >= 0:
            self.selector_calidad.setCurrentIndex(idx_calidad)

        self.boton_convertir = QPushButton(self.txt["btn_convertir"])
        self.boton_convertir.setObjectName("BotonConvertir")
        self.boton_convertir.clicked.connect(self.iniciar_conversion)

        fila_inferior.addWidget(self.selector_formato)
        fila_inferior.addWidget(self.selector_calidad)
        fila_inferior.addStretch()
        fila_inferior.addWidget(self.boton_convertir)
        layout_global.addLayout(fila_inferior)

        layout_ventana = QVBoxLayout(self)
        layout_ventana.setContentsMargins(0, 0, 0, 0)
        layout_ventana.addWidget(contenedor_principal)

        if self.tema_actual == "oscuro":
            self.aplicar_barra_oscura_windows()

    def obtener_carpeta_musica_nativa(self):
        """Detecta el sistema operativo y extrae la ruta real de la carpeta Música del usuario"""
        if sys.platform == "win32":
            import winreg
            try:
                clave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                ruta_registro, _ = winreg.QueryValueEx(clave, "My Music")
                winreg.CloseKey(clave)
                ruta_final = os.path.normpath(os.path.expandvars(ruta_registro))
                if os.path.exists(ruta_final):
                    return ruta_final
            except Exception:
                pass
            intento_comun = os.path.normpath(os.path.join(os.path.expanduser("~"), "Music"))
            if os.path.exists(intento_comun):
                return intento_comun
        else:
            try:
                ruta_xdg = subprocess.check_output(['xdg-user-dir', 'MUSIC'], text=True).strip()
                if os.path.exists(ruta_xdg):
                    return os.path.normpath(ruta_xdg)
            except Exception:
                pass
            intento_linux = os.path.normpath(os.path.join(os.path.expanduser("~"), "Music"))
            if os.path.exists(intento_linux):
                return intento_linux
        return os.path.dirname(os.path.abspath(__file__))

    def aplicar_barra_oscura_windows(self):
        if sys.platform == "win32":
            import ctypes
            try:
                hwnd = int(self.winId())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                dark_mode = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode))
            except Exception:
                pass

    def actualizar_lista_calidades(self):
        formato_seleccionado = self.selector_formato.currentText()
        self.selector_calidad.clear()
        if formato_seleccionado in self.opciones_calidad:
            self.selector_calidad.addItems(self.opciones_calidad[formato_seleccionado])

    def seleccionar_carpeta(self):
        carpeta = QFileDialog.getExistingDirectory(self, self.txt["btn_buscar"], self.txt_destino.text())
        if carpeta:
            self.txt_destino.setText(os.path.normpath(carpeta))

    def iniciar_conversion(self):
        cant_archivos = self.lista_archivos.count()
        if cant_archivos == 0:
            return

        formato = self.selector_formato.currentText()
        calidad = self.selector_calidad.currentText()
        carpeta_salida = self.txt_destino.text()

        parametros_ffmpeg = self.MAPEO_FFMPEG[formato][calidad]
        extension_salida = ".m4a" if formato == "AAC / M4A" else f".{formato.lower()}"

        lista_tareas = []
        for i in range(cant_archivos):
            item = self.lista_archivos.item(i)
            ruta_entrada = item.toolTip()
            nombre_base, _ = os.path.splitext(os.path.basename(ruta_entrada))
            ruta_salida = os.path.normpath(os.path.join(carpeta_salida, f"{nombre_base}{extension_salida}"))
            
            lista_tareas.append({
                "entrada": ruta_entrada,
                "salida": ruta_salida,
                "argumentos": parametros_ffmpeg
            })

        self.boton_convertir.setEnabled(False)
        self.selector_formato.setEnabled(False)
        self.selector_calidad.setEnabled(False)
        self.lista_archivos.setEnabled(False)
        self.barra_progreso.setValue(0)

        self.hilo = QThread()
        self.worker = ConversorWorker(lista_tareas)
        self.worker.moveToThread(self.hilo)

        self.hilo.started.connect(self.worker.iniciar_proceso)
        self.worker.progreso.connect(self.barra_progreso.setValue)
        self.worker.archivo_actual.connect(lambda texto: self.zona_arrastre.setText(f"{self.txt['procesando']}\n{texto}"))
        
        self.worker.finalizado.connect(self.finalizar_interfaz)
        self.worker.finalizado.connect(self.hilo.quit)
        self.worker.finalizado.connect(self.worker.deleteLater)
        self.hilo.finished.connect(self.hilo.deleteLater)

        self.hilo.start()

    def finalizar_interfaz(self):
        self.boton_convertir.setEnabled(True)
        self.selector_formato.setEnabled(True)
        self.selector_calidad.setEnabled(True)
        self.lista_archivos.setEnabled(True)
        self.lista_archivos.clear()
        self.zona_arrastre.setText(self.txt["listo"])

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.lista_archivos.isEnabled() and event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.zona_arrastre.setStyleSheet("background-color: #1e293b; border: 2px solid #3b82f6; color: #3b82f6;" if self.tema_actual == "oscuro" else "background-color: #e0f2fe; border: 2px solid #0284c7; color: #0284c7;")

    def dragLeaveEvent(self, event):
        self.zona_arrastre.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.dragLeaveEvent(None)
        if not self.lista_archivos.isEnabled():
            return
        urls = event.mimeData().urls()
        for url in urls:
            ruta_local = url.toLocalFile()
            if os.path.isfile(ruta_local) and ruta_local.lower().endswith(('.mp3', '.flac', '.wav', '.m4a', '.aac')):
                nombre_archivo = os.path.basename(ruta_local)
                items_existentes = [self.lista_archivos.item(i).toolTip() for i in range(self.lista_archivos.count())]
                if ruta_local not in items_existentes:
                    item = QListWidgetItem(nombre_archivo)
                    item.setToolTip(ruta_local)
                    self.lista_archivos.addItem(item)
                    self.zona_arrastre.setText(self.txt["zona_arrastre"])

    def manejar_teclado_lista(self, event):
        if self.lista_archivos.isEnabled() and (event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace):
            for item in self.lista_archivos.selectedItems():
                self.lista_archivos.takeItem(self.lista_archivos.row(item))
        else:
            QListWidget.keyPressEvent(self.lista_archivos, event)

    def closeEvent(self, event):
        """Guarda automáticamente la configuración de los desplegables al cerrar la ventana"""
        config = configparser.ConfigParser()
        config.read(self.ruta_config, encoding="utf-8")
        
        if not config.has_section("General"):
            config["General"] = {"Idioma": self.idioma_actual, "Tema": self.tema_actual}
            
        config["Conversor"] = {
            "UltimoFormato": self.selector_formato.currentText(),
            "UltimaCalidad": self.selector_calidad.currentText()
        }
        
        try:
            with open(self.ruta_config, "w", encoding="utf-8") as f:
                f.write("; Guía de usuario del convertidor\n; idioma: es o en\n; tema: oscuro o claro\n")
                config.write(f)
        except Exception as e:
            print(f"No se pudo guardar la configuración: {e}")
        event.accept()

# ==============================================================================
# HOJAS DE ESTILO DINÁMICAS
# ==============================================================================
HOJA_ESTILOS_OSCURA = """
    QWidget { background-color: #121212; color: #ffffff; font-family: 'Segoe UI', 'Ubuntu', sans-serif; }
    QFrame#ContenedorPrincipal { border: 1px solid #444444; background-color: #121212; }
    QLabel#LabelSubtitulo { font-weight: 500; color: #b3b3b3; font-size: 12px; }
    QLabel#ZonaArrastre { border: 2px dashed #555555; border-radius: 10px; background-color: #1e1e1e; color: #e0e0e0; font-weight: bold; font-size: 13px; }
    QListWidget { background-color: #1a1a1a; border: 1px solid #444444; border-radius: 8px; color: #ffffff; padding: 5px; }
    QListWidget::item { padding: 6px; border-bottom: 1px solid #292929; }
    QListWidget::item:selected { background-color: #3b82f6; color: #ffffff; }
    QScrollBar:vertical { background-color: #1a1a1a; width: 12px; margin: 0px; border-radius: 4px; }
    QScrollBar::handle:vertical { background-color: #444444; min-height: 20px; border-radius: 4px; }
    QScrollBar::handle:vertical:hover { background-color: #555555; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; height: 0px; }
    QLineEdit { background-color: #1a1a1a; border: 1px solid #444444; border-radius: 6px; padding: 6px; color: #cccccc; }
    QPushButton#BotonSecundario { background-color: #2d2d2d; color: #ffffff; border: 1px solid #444444; border-radius: 6px; padding: 6px; }
    QPushButton#BotonSecundario:hover { background-color: #3d3d3d; }
    QComboBox { background-color: #1e1e1e; color: #ffffff; border: 1px solid #444444; border-radius: 6px; padding: 6px 30px 6px 12px; }
    QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 25px; border-left-width: 0px; }
    QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid #ffffff; width: 0; height: 0; }
    QListView { background-color: #1e1e1e; color: #ffffff; border: 1px solid #444444; selection-background-color: #3b82f6; selection-color: #ffffff; }
    QProgressBar { border: 1px solid #444444; border-radius: 4px; background-color: #1a1a1a; color: #ffffff; font-weight: bold; font-size: 11px; }
    QProgressBar::chunk { background-color: #15803d; border-radius: 3px; }
    QPushButton#BotonConvertir { background-color: #15803d; color: #ffffff; font-weight: bold; border: 1px solid #16a34a; border-radius: 6px; padding: 8px 20px; }
    QPushButton#BotonConvertir:hover { background-color: #166534; border-color: #15803d; }
    QPushButton#BotonConvertir:pressed { background-color: #14532d; }
"""

HOJA_ESTILOS_CLARA = """
    QWidget { background-color: #f3f4f6; color: #1f2937; font-family: 'Segoe UI', 'Ubuntu', sans-serif; }
    QFrame#ContenedorPrincipal { border: 1px solid #d1d5db; background-color: #f3f4f6; }
    QLabel#LabelSubtitulo { font-weight: 500; color: #4b5563; font-size: 12px; }
    QLabel#ZonaArrastre { border: 2px dashed #9ca3af; border-radius: 10px; background-color: #ffffff; color: #374151; font-weight: bold; font-size: 13px; }
    QListWidget { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 8px; color: #1f2937; padding: 5px; }
    QListWidget::item { padding: 6px; border-bottom: 1px solid #f3f4f6; }
    QListWidget::item:selected { background-color: #0284c7; color: #ffffff; }
    QScrollBar:vertical { background-color: #f3f4f6; width: 12px; margin: 0px; border-radius: 4px; }
    QScrollBar::handle:vertical { background-color: #d1d5db; min-height: 20px; border-radius: 4px; }
    QScrollBar::handle:vertical:hover { background-color: #9ca3af; }
    QLineEdit { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 6px; color: #1f2937; }
    QPushButton#BotonSecundario { background-color: #e5e7eb; color: #1f2937; border: 1px solid #c4c6cc; border-radius: 6px; padding: 6px; }
    QPushButton#BotonSecundario:hover { background-color: #d1d5db; }
    QComboBox { background-color: #ffffff; color: #1f2937; border: 1px solid #d1d5db; border-radius: 6px; padding: 6px 30px 6px 12px; }
    QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 25px; border-left-width: 0px; }
    QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid #1f2937; width: 0; height: 0; }
    QListView { background-color: #ffffff; color: #1f2937; border: 1px solid #d1d5db; selection-background-color: #0284c7; selection-color: #ffffff; }
    QProgressBar { border: 1px solid #d1d5db; border-radius: 4px; background-color: #ffffff; color: #1f2937; font-weight: bold; font-size: 11px; }
    QProgressBar::chunk { background-color: #16a34a; border-radius: 3px; }
    QPushButton#BotonConvertir { background-color: #16a34a; color: #ffffff; font-weight: bold; border: 1px solid #15803d; border-radius: 6px; padding: 8px 20px; }
    QPushButton#BotonConvertir:hover { background-color: #15803d; }
"""

if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("modern_converter.audio_app.1.0")

    app = QApplication(sys.argv)
    ventana = AudioConverterApp()
    
    if ventana.tema_actual == "claro":
        app.setStyleSheet(HOJA_ESTILOS_CLARA)
    else:
        app.setStyleSheet(HOJA_ESTILOS_OSCURA)
        
    ventana.show()
    sys.exit(app.exec())