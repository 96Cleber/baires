import os
from typing import List, Dict, Any, Tuple

import numpy as np
import torch
try:
    from ultralytics import YOLO
except Exception:  # ultralytics may not be installed yet
    YOLO = None  # type: ignore

try:
    from scipy.spatial import cKDTree
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from .bytetrack import ByteTrack


# Fixed label set and mapping (consistent across repos)
LABEL_ORDER = ["person", "bicycle", "car", "motorcycle", "bus", "truck"]
LABEL_TO_CODE = {name: idx + 1 for idx, name in enumerate(LABEL_ORDER)}
CODE_TO_LABEL = {v: k for k, v in LABEL_TO_CODE.items()}
ALLOWED_LABELS = set(LABEL_ORDER)

# Mapeo de clases YOLO a tipologías personalizadas
YOLO_TO_TIPOLOGIA = {
    'person': 'persona',
    'bicycle': 'bicicleta',
    'car': 'auto',
    'motorcycle': 'moto',
    'bus': 'micro',
    'truck': 'camion',
}

def get_tipologia(yolo_label: str) -> str:
    """Convertir etiqueta YOLO a tipología personalizada"""
    return YOLO_TO_TIPOLOGIA.get(yolo_label, yolo_label)


def robust_vehicle_classification(bbox: List[float], label: str, score: float, frame_shape: Tuple[int, int, int]) -> str:
    x1, y1, x2, y2 = bbox
    bbox_width = x2 - x1
    bbox_height = y2 - y1
    bbox_area = bbox_width * bbox_height
    frame_height, frame_width = frame_shape[:2]

    relative_area = bbox_area / max(1.0, (frame_width * frame_height))
    aspect_ratio = bbox_width / max(1.0, bbox_height)

    if label == 'car':
        if (relative_area > 0.035 and aspect_ratio > 2.0 and score > 0.7 and bbox_height > frame_height * 0.35):
            return 'bus'
        elif (relative_area > 0.03 and aspect_ratio > 2.2 and score > 0.75):
            return 'truck'
    elif label in ['bus', 'truck']:
        if relative_area < 0.008 and score < 0.5:
            return 'car'
    return label


def combine_person_motorcycle_kdtree(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """OPT-5: Versión optimizada con KD-tree para búsqueda espacial eficiente"""
    persons = []
    motorcycles = []
    others = []

    for det in detections:
        if det['label'] == 'person':
            persons.append(det)
        elif det['label'] == 'motorcycle':
            motorcycles.append(det)
        else:
            others.append(det)

    combined_detections = others.copy()

    if not persons or not motorcycles:
        combined_detections.extend(persons)
        combined_detections.extend(motorcycles)
        return combined_detections

    # Crear KD-tree con centros de personas
    person_centers = np.array([
        [(p['bbox'][0] + p['bbox'][2]) / 2, (p['bbox'][1] + p['bbox'][3]) / 2]
        for p in persons
    ])
    tree = cKDTree(person_centers)

    used_persons = set()

    # Buscar persona más cercana para cada moto (O(log n) en lugar de O(n))
    for moto in motorcycles:
        mx1, my1, mx2, my2 = moto['bbox']
        moto_center = [(mx1 + mx2) / 2, (my1 + my2) / 2]

        # Buscar persona más cercana dentro de radio de 100 píxeles
        distances, indices = tree.query(moto_center, k=len(persons), distance_upper_bound=100)
        distances = np.atleast_1d(distances)
        indices = np.atleast_1d(indices)

        # indices es un array, buscar el primer índice válido no usado
        matched = False
        for dist, idx in zip(distances, indices):
            if idx >= len(persons):  # No hay más matches dentro del radio
                break
            if idx not in used_persons and dist < 100:
                person = persons[idx]
                px1, py1, px2, py2 = person['bbox']
                combined_bbox = [min(mx1, px1), min(my1, py1), max(mx2, px2), max(my2, py2)]
                combined_det = {
                    'bbox': combined_bbox,
                    'label': 'motorcycle',
                    'score': max(moto.get('score', 0.0), person.get('score', 0.0)),
                    'original_label': 'motorcycle'
                }
                combined_detections.append(combined_det)
                used_persons.add(idx)
                matched = True
                break

        if not matched:
            combined_detections.append(moto)

    # Agregar personas no usadas
    for i, person in enumerate(persons):
        if i not in used_persons:
            combined_detections.append(person)

    return combined_detections


def combine_person_motorcycle_fallback(detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Versión fallback sin KD-tree (O(n*m) original)"""
    persons = []
    motorcycles = []
    others = []

    for det in detections:
        if det['label'] == 'person':
            persons.append(det)
        elif det['label'] == 'motorcycle':
            motorcycles.append(det)
        else:
            others.append(det)

    combined_detections = others.copy()
    used_persons = set()

    for moto in motorcycles:
        mx1, my1, mx2, my2 = moto['bbox']
        moto_center = ((mx1 + mx2) / 2, (my1 + my2) / 2)

        closest_person = None
        min_distance = float('inf')
        closest_idx = -1

        for i, person in enumerate(persons):
            if i in used_persons:
                continue
            px1, py1, px2, py2 = person['bbox']
            person_center = ((px1 + px2) / 2, (py1 + py2) / 2)
            distance = ((moto_center[0] - person_center[0]) ** 2 + (moto_center[1] - person_center[1]) ** 2) ** 0.5
            if distance < 100 and distance < min_distance:
                min_distance = distance
                closest_person = person
                closest_idx = i

        if closest_person:
            px1, py1, px2, py2 = closest_person['bbox']
            combined_bbox = [min(mx1, px1), min(my1, py1), max(mx2, px2), max(my2, py2)]
            combined_det = {
                'bbox': combined_bbox,
                'label': 'motorcycle',
                'score': max(moto.get('score', 0.0), closest_person.get('score', 0.0)),
                'original_label': 'motorcycle'
            }
            combined_detections.append(combined_det)
            used_persons.add(closest_idx)
        else:
            combined_detections.append(moto)

    for i, person in enumerate(persons):
        if i not in used_persons:
            combined_detections.append(person)

    return combined_detections


# Seleccionar función según disponibilidad de scipy
combine_person_motorcycle = combine_person_motorcycle_kdtree if SCIPY_AVAILABLE else combine_person_motorcycle_fallback


class DetectorPipeline:
    def __init__(self, weights_path: str, device: str = None, tracker: ByteTrack | None = None):
        if YOLO is None:
            raise RuntimeError("ultralytics is not installed. Please install 'ultralytics' and 'torch'.")
        # Auto-select device if not provided
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        # Permitir alias oficiales (p.ej. 'yolov8x.pt') para que Ultralytics descargue automáticamente
        # y también rutas locales absolutas/relativas.
        try:
            self.model = YOLO(weights_path)
        except Exception as e:
            # Mensaje claro si el archivo/alias no puede cargarse
            raise RuntimeError(f"Could not load YOLO model from '{weights_path}'. {e}")
        try:
            self.model.to(self.device)
        except Exception:
            pass
        if device:
            try:
                self.model.to(device)
            except Exception:
                pass
        # Tracker con activación temprana para visualizar desde el primer frame
        self.tracker = tracker if tracker is not None else ByteTrack(min_hits=1)
        self._fallback_id = -1
        # Human-friendly device name
        if self.device == 'cuda' and torch.cuda.is_available():
            try:
                self.device_name = torch.cuda.get_device_name(0)
            except Exception:
                self.device_name = 'CUDA'
        else:
            self.device_name = 'CPU'

    def _yolo_infer(self, frame) -> List[Dict[str, Any]]:
        results = self.model.predict(frame, verbose=False)
        r = results[0]
        detections: List[Dict[str, Any]] = []
        names = r.names if hasattr(r, 'names') else self.model.names
        if r.boxes is None:
            return detections
        for b in r.boxes:
            try:
                x1, y1, x2, y2 = map(float, b.xyxy[0].tolist())
            except Exception:
                # Fallback in case .xyxy is not a tensor-like
                xyxy = np.array(b.xyxy.cpu()).reshape(-1)[0:4]
                x1, y1, x2, y2 = map(float, xyxy)
            conf = float(b.conf[0]) if hasattr(b, 'conf') else 0.0
            cls_id = int(b.cls[0]) if hasattr(b, 'cls') else 0
            label = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else names[cls_id]
            if label not in ALLOWED_LABELS:
                continue
            detections.append({
                'bbox': [x1, y1, x2, y2],
                'label': label,
                'score': conf
            })
        return detections

    def process_frame(self, frame, stride: int = 1) -> List[Dict[str, Any]]:
        """
        Procesar un frame y devolver detecciones con tracking.

        Parámetros
        ----------
        frame : np.ndarray
            Frame a procesar
        stride : int
            Número de frames saltados desde la última detección (default: 1)
            Importante para tracking correcto cuando se procesan frames no consecutivos

        Returns
        -------
        List[Dict[str, Any]]
            Lista de detecciones con tracking IDs
        """
        dets = self._yolo_infer(frame)
        if not dets:
            # Importante: actualizar tracker incluso sin detecciones para mantener edad de tracks
            self.tracker.update([], stride=stride)
            return []
        # Optional cleanup/adjustments
        try:
            dets = combine_person_motorcycle(dets)
        except Exception:
            dets = []
        # Robust reclassification for bus/truck vs car
        h, w = frame.shape[:2]
        adjusted = []
        for d in dets:
            d = d.copy()
            d['label'] = robust_vehicle_classification(d['bbox'], d['label'], d.get('score', 0.0), (h, w, 3))
            adjusted.append(d)
        # IMPORTANTE: Pasar stride al tracker para compensar frames saltados
        active_tracks = self.tracker.update(adjusted, stride=stride)

        outputs: List[Dict[str, Any]] = []
        for tr in active_tracks:
            if not tr["detection_history"]:
                continue
            last = tr["detection_history"][-1]
            outputs.append({
                'track_id': tr['track_id'],
                'bbox': last['bbox'],
                'label': last['label'],
                'score': last.get('score', 0.0)
            })

        # Fallback: si aún no hay tracks activos, devolver detecciones actuales
        if not outputs and adjusted:
            for d in adjusted:
                outputs.append({
                    'track_id': self._fallback_id,
                    'bbox': d['bbox'],
                    'label': d['label'],
                    'score': d.get('score', 0.0)
                })
                self._fallback_id -= 1
        return outputs
