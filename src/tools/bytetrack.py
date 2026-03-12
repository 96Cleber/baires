from typing import List, Dict, Any
import numpy as np


def iou_xyxy(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    if ax1 >= ax2 or ay1 >= ay2 or bx1 >= bx2 or by1 >= by2:
        return 0.0

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    inter = iw * ih

    if inter <= 0:
        return 0.0

    area_a = max(0.0, (ax2 - ax1)) * max(0.0, (ay2 - ay1))
    area_b = max(0.0, (bx2 - bx1)) * max(0.0, (by2 - by1))
    union = area_a + area_b - inter

    if union <= 0:
        return 0.0

    return inter / union


class ByteTrack:
    def __init__(self, max_age: int = 15, min_hits: int = 3, iou_thresh: float = 0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_thresh = iou_thresh
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.next_track_id = 1
        self.frame_count = 0
        self.current_stride = 1  # Nuevo: frames saltados entre actualizaciones

    def _last_bbox(self, track: Dict[str, Any]):
        if track["detection_history"]:
            return track["detection_history"][-1]["bbox"]
        return None

    def update(self, detections: List[Dict[str, Any]], stride: int = 1):
        """
        Actualizar tracking con las detecciones del frame actual.

        Parámetros
        ----------
        detections : List[Dict[str, Any]]
            Lista de detecciones del frame actual
        stride : int
            Número de frames saltados desde la última actualización (default: 1)
            Usado para ajustar thresholds cuando se procesan frames no consecutivos
        """
        self.frame_count += stride  # Incrementar por frames saltados
        self.current_stride = stride

        track_ids = list(self.tracks.keys())
        last_bboxes = [self._last_bbox(self.tracks[tid]) for tid in track_ids]
        det_bboxes = [d["bbox"] for d in detections]

        unmatched_tracks = set(track_ids)
        unmatched_dets = set(range(len(detections)))
        matches = []

        # Ajustar threshold de IoU basado en stride
        # Cuando stride es alto, los vehículos se mueven más, necesitamos ser más permisivos
        adjusted_iou_thresh = self.iou_thresh * (1.0 - min(0.3, stride * 0.02))

        if track_ids and detections:
            iou_mat = np.zeros((len(track_ids), len(detections)), dtype=np.float32)
            for i, bb_t in enumerate(last_bboxes):
                if bb_t is None:
                    continue
                for j, bb_d in enumerate(det_bboxes):
                    iou_mat[i, j] = iou_xyxy(bb_t, bb_d)

            flat = []
            for i in range(iou_mat.shape[0]):
                for j in range(iou_mat.shape[1]):
                    track_label = self.tracks[track_ids[i]]["detection_history"][-1]["label"]
                    det_label = detections[j]["label"]
                    iou_score = iou_mat[i, j]
                    if track_label == det_label:
                        iou_score *= 1.1
                    flat.append((iou_score, i, j))
            flat.sort(reverse=True, key=lambda x: x[0])

            used_tracks = set()
            used_dets = set()
            for iou_score, i, j in flat:
                if iou_score < adjusted_iou_thresh:
                    break
                tid = track_ids[i]
                if i in used_tracks or j in used_dets:
                    continue
                matches.append((tid, j))
                used_tracks.add(i)
                used_dets.add(j)

            unmatched_tracks -= {track_ids[i] for i in used_tracks}
            unmatched_dets -= used_dets

        for tid, j in matches:
            det = detections[j].copy()
            det["track_id"] = tid
            tr = self.tracks[tid]
            tr["hits"] += 1
            tr["age"] = 0
            tr["detection_history"].append(det)
            # OPT-9: Reducir de 10 a 5 frames para menor uso de memoria
            if len(tr["detection_history"]) > 5:
                tr["detection_history"] = tr["detection_history"][-5:]

        for j in unmatched_dets:
            det = detections[j].copy()
            if det.get('score', 0) > 0.5:
                tid = self.next_track_id
                self.next_track_id += 1
                det["track_id"] = tid
                self.tracks[tid] = {
                    "track_id": tid,
                    "hits": 1,
                    "age": 0,
                    "detection_history": [det],
                }

        for tid in list(unmatched_tracks):
            tr = self.tracks.get(tid)
            if tr is None:
                continue
            # Incrementar age por el número de frames saltados (stride)
            tr["age"] += stride
            # Ajustar max_age efectivo basado en stride para compensar saltos de frames
            adjusted_max_age = self.max_age + (stride - 1) * 3
            if tr["age"] > adjusted_max_age:
                del self.tracks[tid]

        self._cleanup_weak_tracks()
        return self.get_active_tracks()

    def _cleanup_weak_tracks(self):
        to_remove = []
        for tid, track in self.tracks.items():
            if track["hits"] < self.min_hits and track["age"] > 5:
                to_remove.append(tid)
            elif track["hits"] >= self.min_hits and track["age"] > self.max_age // 2:
                to_remove.append(tid)
        for tid in to_remove:
            del self.tracks[tid]

    def get_active_tracks(self):
        return [t for t in self.tracks.values() if t["hits"] >= self.min_hits and t["age"] <= 2]

