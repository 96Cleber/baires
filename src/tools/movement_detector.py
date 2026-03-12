import cv2

class VehicleMovementDetector:
    def __init__(self, min_area = 1500, max_area = 50000, history = 500, var_threshold = 50):
        """
        Inicializar el detector de movimiento de vehículos.
        
        Parámetros
        ----------
        min_area: int
            Área mínima del contorno para ser considerado un vehículo
        max_area: int
            Área máxima del contorno para ser considerado un vehículo
        history: int
            Número de frames para el historial del sustractor de fondo
        var_threshold: int
            Umbral de varianza para el sustractor de fondo
        """
        self.min_area = min_area
        self.max_area = max_area

        # Sustracción de fondo con MOG2
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history = history,
            varThreshold = var_threshold,
            detectShadows = True
        )

        # Kernels para operaciones morfológicas
        self.kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self.kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))