#!/bin/bash
# Script para construir el ejecutable de FlowVisionAI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  FlowVisionAI - Construcción de Ejecutable"
echo "============================================"

# Activar entorno virtual
if [ -d "venv" ]; then
    echo "[1/4] Activando entorno virtual..."
    source venv/bin/activate
else
    echo "ERROR: No se encontró el entorno virtual 'venv'"
    exit 1
fi

# Verificar PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "[2/4] Instalando PyInstaller..."
    pip install pyinstaller
else
    echo "[2/4] PyInstaller ya está instalado"
fi

# Limpiar builds anteriores
echo "[3/4] Limpiando builds anteriores..."
rm -rf build/ dist/

# Construir ejecutable
echo "[4/4] Construyendo ejecutable..."
echo "      Esto puede tomar varios minutos..."
pyinstaller flowvisionai.spec --noconfirm

echo ""
echo "============================================"
echo "  Construcción completada!"
echo "============================================"
echo ""
echo "El ejecutable se encuentra en:"
echo "  dist/FlowVisionAI/"
echo ""
echo "Para ejecutar la aplicación:"
echo "  ./dist/FlowVisionAI/FlowVisionAI"
echo ""
