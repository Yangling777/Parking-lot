"""Webcam-based virtual hardware simulator.

Captures video from a PC webcam and simulates ESP32 camera behavior:
- Press SPACE to capture and send a frame to the Flask backend for plate recognition
- Press Q to quit
- No physical ESP32 hardware required
"""

import cv2
import requests

SERVER_URL = "http://127.0.0.1:5000/api/hardware/upload_image"


def main():
    """Main loop: open webcam, show live preview, capture on SPACE key."""
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Cannot open camera. Check device connection.")
        return

    print("=" * 50)
    print("Smart Parking - Virtual Hardware Terminal")
    print("=" * 50)
    print("Instructions:")
    print("1. Point a license plate (or phone image) at the camera")
    print("2. Press [SPACE] to capture and upload")
    print("3. Press [Q] to quit\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Cannot read frame")
            break

        cv2.putText(frame, "Press SPACE to Scan, Q to Quit", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("ESP32-CAM Simulator", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == 32:  # SPACE key
            print("\nCapturing and sending to backend...")

            success, buffer = cv2.imencode('.jpg', frame)
            if success:
                image_bytes = buffer.tobytes()
                try:
                    files = {'imageFile': ('snapshot.jpg', image_bytes, 'image/jpeg')}
                    response = requests.post(SERVER_URL, files=files)
                    result = response.json()

                    if result.get("code") == 200:
                        print(f"[Recognition Success]")
                        print(f"  Plate: {result.get('plate')}")
                        print(f"  Action: {result.get('action')} ({result.get('msg')})")
                    else:
                        print(f"[Recognition Failed] {result.get('msg')}")

                except requests.exceptions.ConnectionError:
                    print("Cannot connect to server. Ensure Flask backend is running.")

        elif key == ord('q'):
            print("Shutting down virtual hardware terminal...")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
