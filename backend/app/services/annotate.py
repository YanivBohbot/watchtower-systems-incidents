"""Evidence drawing shared by uploaded-video analysis and live cameras."""

import cv2

ZONE_COLOR = (0, 200, 255)
BOX_COLOR = (0, 255, 0)


def annotate(frame, zone: dict | None, boxes):
    """Return a copy of the frame with the zone and each normalized (x1, y1, x2, y2) box drawn."""
    out = frame.copy()
    h, w = out.shape[:2]
    if zone:
        cv2.rectangle(
            out, (int(zone["x1"] * w), int(zone["y1"] * h)), (int(zone["x2"] * w), int(zone["y2"] * h)), ZONE_COLOR, 2
        )
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(out, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), BOX_COLOR, 2)
    return out


def encode_jpeg(frame) -> bytes:
    success, encoded = cv2.imencode(".jpg", frame)
    if not success:
        raise ValueError("Could not encode evidence")
    return encoded.tobytes()
