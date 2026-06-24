# Modern Converter Toolkit (Audio)

Un convertidor de audio de alta fidelidad rápido y portátil diseñado en Python con PyQt6 y FFmpeg.

## Características
- **Conversión masiva:** Optimizado especialmente para archivos de audio de alta fidelidad (FLAC).
- **Interfaz moderna:** Soporte nativo para arrastrar y soltar archivos (Drag and Drop).
- **Fluidez absoluta:** Procesamiento en segundo plano mediante hilos (`QThreads`) para evitar que la interfaz se congele.
- **Persistencia:** Conservación y gestión de tus preferencias mediante un archivo `config.ini`.
- **Bilingüe:** Disponible en español e inglés (configurable a través de `config.ini`).
- **Personalizable:** Soporte para dos temas visuales (Modo Oscuro y Modo Claro vía `config.ini`).


## Requisitos del Sistema

Para que el convertidor funcione, el sistema necesita tener acceso a los binarios de **FFmpeg** y **FFprobe**.

### En Linux (Kubuntu / Debian / Ubuntu)
Basta con instalar FFmpeg de forma global desde los repositorios oficiales. El programa lo detectará automáticamente:

`sudo apt update && sudo apt install ffmpeg`

### En Windows

Opción portable: Descarga los binarios oficiales y coloca ffmpeg.exe y ffprobe.exe en la misma carpeta junto al ejecutable.

Opción global (Recomendada): Instálalo mediante Winget desde PowerShell como administrador:

`winget install Gyan.FFmpeg`
