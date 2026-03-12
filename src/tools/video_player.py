import cv2
from PyQt5.QtCore import QPointF, QTimer
from shapely.geometry import LineString, box

class CountingLine:
    """
    Línea de conteo.
    
    Atributos
    ---------
    id : str
        Identificador de la línea de conteo.
    start : class
        Clase QPointF de Qt con las coordenadas del punto inicial de la línea de conteo.
    end : class
        Clase QPointF de Qt con las coordenadas del punto final de la línea de conteo.
    selected : bool
        Booleano que indica si se seleccionó un extremo de una línea de conteo.
    """
    def __init__(self, id, access, name, start: QPointF, end: QPointF):
        """
        Parámetros
        ----------
        id : str
            Identificador de la línea de conteo.
        access : str
            Dirección de acceso de la línea de conteo. Valores posibles: 'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW'.
        name : str
            Nombre descriptivo de la línea de conteo.
        start : class
            Clase QPointF de Qt con las coordenadas del punto inicial de la línea de conteo.
        end : class
            Clase QPointF de Qt con las coordenadas del punto final de la línea de conteo.
        """
        self.id = id
        self.access = access
        self.name = name
        self.start = start
        self.end = end
        self.selected = False

    def to_shapely(self):
        """
        TODO

        Retorno
        -------
        TODO
        """
        return LineString([(self.start.x(), self.start.y()), (self.end.x(), self.end.y())])

class BoundingBox:
    """
    Caja de detección.
    
    Atributos
    ---------
    id : int
        Código de la caja de detección.
    road_user_type : int
        Código de la tipología detectada.
    frame_number : int
        Número de fotograma de la detección.
    coordinates : class
        Clase Polygon de Shapely con las coordenadas de la caja de detección.
    """
    def __init__(self, id, road_user_type, frame_number, x1, y1, x2, y2):
        """
        Parámetros
        ----------
        id : int
            Código de la caja de detección.
        road_user_type : int
            Código de la tipología detectada.
        frame_number : int
            Número de fotograma de la detección.
        x1, y1 : float
            Coordenadas (x, y) de la esquina superior izquierda de la caja de detección.
        x2, y2 : float
            Coordenadas (x, y) de la esquina inferior derecha de la caja de detección.
        """
        self.id = id
        self.road_user_type = road_user_type
        self.frame_number = frame_number
        self.coordinates = box(x1, y1, x2, y2)

    def intersects(self, line: LineString):
        """
        TODO

        Retorno
        -------
        TODO
        """
        return self.coordinates.intersects(line)

class VideoPlayer:
    """
    Reproductor de video.

    Atributos
    ---------
    cap : class
        Clase de OpenCV para capturar videos.
    original_size : int, int
        Tupla con las dimensiones originales del video (ancho, alto).
    timer : class
        Clase de Qt para trabajar con temporizadores.
    frame_number: int
        Número de fotograma.
    display_rate : int
        Cantidad de fotogramas a desplazar.
    video_playing : bool
        Booleano que indica si el video está en ejecución.

    Métodos
    -------
    draw_frame(frame_number)
        Leer y dibujar el fotograma número `frame_number`.
    play()
        Iniciar la reproducción del video.
    pause()
        Pausar la reproducción del video.
    """

    def __init__(self, video_path, callback):
        """
        Crear una clase de reproducción de video.

        Parámetros
        ----------
        video_path : str
            Directorio del archivo de video.
        callback : function
            Función para procesar los fotogramas.
        """
        self.cap = cv2.VideoCapture(video_path)
        self.original_size = (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)
        self.frame_number = 0
        self.display_rate = 3  # Saltar frames por defecto para mayor velocidad
        self.video_playing = False
        self.display_callback = callback
        self.video_path = video_path

        # OPT-7: Stride adaptativo - se ajustará dinámicamente desde main_v3.py
        # El display_rate se actualizará según haya o no detecciones
        self.frame_stride = 3

    def _update_frame(self):
        """
        Avanzar `display_rate` fotogramas cada vez que se actualiza el temporizador.
        """
        if self.video_playing:
            # Leer y descartar frames intermedios para evitar errores HEVC
            # Esto es necesario porque HEVC requiere frames de referencia para decodificar
            for _ in range(self.display_rate):
                ret, frame = self.cap.read()
                if not ret:
                    # Fin del video
                    print("[INFO] Procesamiento finalizado.")
                    self.pause()
                    return

            # Procesar el último frame leído
            self.frame_number += self.display_rate
            self.display_callback(frame)

    def draw_frame(self, frame_number):
        """
        Leer y dibujar el fotograma número `frame_number`.

        Parámetros
        ----------
        frame_number : int
            Número de fotograma.
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        if ret:
            self.display_callback(frame)

    def play(self):
        """
        Iniciar la reproducción del video.
        """
        self.video_playing = True
        # Reducir delay de 30ms a 1ms para máxima velocidad de procesamiento
        self.timer.start(1)

    def pause(self):
        """
        Pausar la reproducción del video.
        """
        self.video_playing = False
        self.timer.stop()