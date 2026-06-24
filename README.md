# Modern Converter Toolkit (Audio)

Un convertidor de audio de alta fidelidad rápido y portátil diseñado en Python con PyQt6 y FFmpeg.

## Características
- Conversión masiva de archivos de audio (especialmente optimizado para FLAC).
- Interfaz gráfica moderna con soporte para arrastrar y soltar (Drag and Drop).
- Procesamiento en segundo plano mediante hilos (QThreads) para evitar que la interfaz se congele.
- Conservación y gestión de configuraciones mediante archivo `.ini`.

## Requisitos del Sistema

Para que el convertidor funcione, el sistema necesita tener acceso a los binarios de **FFmpeg** y **FFprobe**.

### En Linux (Kubuntu / Debian / Ubuntu)
Basta con instalar FFmpeg de forma global desde los repositorios oficiales. El programa lo detectará automáticamente:
```bash
sudo apt update && sudo apt install ffmpeg

### En Windows

Opción portable: Descarga los binarios oficiales y coloca ffmpeg.exe y ffprobe.exe en la misma carpeta junto al ejecutable.

Opción global (Recomendada): Instálalo mediante Winget desde PowerShell como administrador:
```bash
winget install Gyan.FFmpeg