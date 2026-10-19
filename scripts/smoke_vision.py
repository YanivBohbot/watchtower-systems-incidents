"""Optional real YOLO check; requires backend vision dependencies, no LLM key."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='yolov8n.pt')
    args = parser.parse_args()
    import cv2
    import ultralytics
    from app.adapters.vision import YoloDetector
    sample = Path(ultralytics.__file__).parent / 'assets/bus.jpg'
    if not sample.is_file():
        raise SystemExit('Ultralytics sample image is not available in this installation')
    detector = YoloDetector(args.model)
    objects = detector.track(cv2.imread(str(sample)))
    if not objects:
        raise SystemExit('No person tracked in the reference image')
    assert all(0 <= o.x1 <= o.x2 <= 1 and 0 <= o.y1 <= o.y2 <= 1 for o in objects)
    print(f'YOLO/ByteTrack: {len(objects)} tracked people; normalized coordinates valid.')


if __name__ == '__main__':
    main()
