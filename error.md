(venv) cleber@96Cleber:~/Descargas/mejoras-versiones/flowvisionai_base/templates/flowvisionai$ python src/main_lite.py 
Warning: Ignoring XDG_SESSION_TYPE=wayland on Gnome. Use QT_QPA_PLATFORM=wayland to run on Wayland anyway.
Traceback (most recent call last):
  File "/home/cleber/Descargas/mejoras-versiones/flowvisionai_base/templates/flowvisionai/src/main_lite.py", line 512, in open_classifier
    dialog = ClassificationGalleryDialog(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/cleber/Descargas/mejoras-versiones/flowvisionai_base/templates/flowvisionai/src/ui/classification_gallery_dialog.py", line 411, in __init__
    self.preload_all_images()  # Precargar todas las imágenes al inicio
    ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/cleber/Descargas/mejoras-versiones/flowvisionai_base/templates/flowvisionai/src/ui/classification_gallery_dialog.py", line 1342, in preload_all_images
    QApplication.processEvents()
    ^^^^^^^^^^^^
NameError: name 'QApplication' is not defined
Abortado (`core' generado)