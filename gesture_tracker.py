"""
Background hand gesture tracking using OpenCV + MediaPipe.
Runs on a separate thread and writes gesture state to a shared dict.
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import threading
import math
import os
import time


class GestureTracker:
    """Captures webcam frames, detects hand landmarks, derives gesture states."""

    # Finger tip and pip landmark indices
    FINGER_TIPS = [4, 8, 12, 16, 20]  # thumb, index, middle, ring, pinky
    FINGER_PIPS = [3, 6, 10, 14, 18]

    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)
    ]

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.overlay_frame = None

        self.cap = self._open_camera()

        # Shared gesture state
        self._state = {
            "index_x": 0.5,
            "index_y": 0.5,
            "hand_x": 0.5,
            "hand_y": 0.5,
            "is_fist": False,
            "is_pinch": False,
            "is_open_palm": False,
            "is_peace": False,
            "is_thumb_up": False,
            "is_thumb_down": False,
            "is_index_only": False,
            "fingers_up": [False] * 5,
            "hand_tilt": 0.0,
            "hand_detected": False,
            "hand_box": None,
            "gesture_label": "NONE",
            "raw_landmarks": None,
            "camera_error": None,
        }

        if self.cap is None:
            self._state["camera_error"] = "Camera not available"

    def _open_camera(self):
        """Open the first available camera, preferring macOS AVFoundation when present."""
        backends = []
        if hasattr(cv2, "CAP_AVFOUNDATION"):
            backends.append(cv2.CAP_AVFOUNDATION)
        backends.append(None)

        for backend in backends:
            for index in (0, 1):
                cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    return cap
                cap.release()
        return None

    def start(self):
        """Start the background tracking thread."""
        if self.cap is None:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the background tracking thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()

    def get_state(self):
        """Thread-safe read of gesture state."""
        with self.lock:
            return dict(self._state)

    def get_overlay(self):
        """Get the latest overlay frame (BGR numpy array or None)."""
        with self.lock:
            return self.overlay_frame.copy() if self.overlay_frame is not None else None

    def _draw_skeleton(self, overlay, landmarks):
        h, w, _ = overlay.shape
        # Connections
        for connection in self.HAND_CONNECTIONS:
            idx1, idx2 = connection
            lm1 = landmarks[idx1]
            lm2 = landmarks[idx2]
            p1 = (int(lm1.x * w), int(lm1.y * h))
            p2 = (int(lm2.x * w), int(lm2.y * h))
            cv2.line(overlay, p1, p2, (200, 200, 200), 2)
        # Dots
        for lm in landmarks:
            p = (int(lm.x * w), int(lm.y * h))
            cv2.circle(overlay, p, 4, (0, 0, 255), -1)

    def _run(self):
        """Main camera loop running on background thread."""
        # Initialize MediaPipe HandLandmarker Tasks API
        model_path = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
        try:
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.5
            )
            detector = vision.HandLandmarker.create_from_options(options)
        except Exception:
            with self.lock:
                self._state["camera_error"] = "Hand model failed to load"
            return

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                with self.lock:
                    self._state["camera_error"] = "Camera frame unavailable"
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)  # Mirror
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = detector.detect(mp_image)

            overlay = frame.copy()
            state = dict(self._state)  # Start from defaults
            state["hand_detected"] = False
            state["camera_error"] = None

            if results.hand_landmarks:
                landmarks = results.hand_landmarks[0]
                
                # Draw skeleton
                self._draw_skeleton(overlay, landmarks)

                state["hand_detected"] = True

                # Index finger position (normalized 0-1)
                idx_tip = landmarks[8]
                state["index_x"] = idx_tip.x
                state["index_y"] = idx_tip.y
                
                mid_base = landmarks[9]
                state["hand_x"] = mid_base.x
                state["hand_y"] = mid_base.y

                # Bounding box for calibration
                x_min = min(lm.x for lm in landmarks)
                x_max = max(lm.x for lm in landmarks)
                y_min = min(lm.y for lm in landmarks)
                y_max = max(lm.y for lm in landmarks)
                state["hand_box"] = (x_min, y_min, x_max, y_max)

                # Which fingers are up
                fingers_up = self._get_fingers_up(landmarks)
                state["fingers_up"] = fingers_up

                # Derived gestures
                num_up = sum(fingers_up)
                state["is_open_palm"] = num_up >= 4
                state["is_fist"] = num_up == 0

                # Classification into UP, DOWN, LEFT, RIGHT, NONE
                label = "NONE"
                # Check if ONLY the index is up (other fingertips near the palm)
                is_index_up = fingers_up[1] and not fingers_up[2] and not fingers_up[3] and not fingers_up[4]
                
                if is_index_up:
                    wrist = landmarks[0]
                    index_tip = landmarks[8]
                    dx = index_tip.x - wrist.x
                    dy = index_tip.y - wrist.y
                    
                    # Determine dominant axis of the index finger relative to the wrist
                    if abs(dx) > abs(dy):
                        if dx < -0.05:
                            label = "LEFT"
                        elif dx > 0.05:
                            label = "RIGHT"
                    else:
                        if dy < -0.05:
                            label = "UP"
                        elif dy > 0.05:
                            label = "DOWN"
                
                state["gesture_label"] = label

                # Hand tilt angle (wrist to middle finger base)
                wrist = landmarks[0]
                mid_base = landmarks[9]
                angle = math.degrees(
                    math.atan2(mid_base.y - wrist.y, mid_base.x - wrist.x)
                )
                state["hand_tilt"] = angle

            # Draw gesture label on overlay
            label = self._gesture_label(state)
            cv2.putText(overlay, label, (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Resize overlay for the game HUD
            overlay_small = cv2.resize(overlay, (240, 180))

            with self.lock:
                self._state = state
                self.overlay_frame = overlay_small

    def _get_fingers_up(self, landmarks):
        """Return list of 5 bools indicating which fingers are raised."""
        fingers = []

        # Thumb: compare x of tip vs ip (landmark 3) — works for right hand
        # Use tip.x < ip.x since image is mirrored
        if landmarks[4].x < landmarks[3].x:
            fingers.append(True)
        else:
            fingers.append(False)

        # Other 4 fingers: tip.y < pip.y means finger is up
        for tip_id, pip_id in zip(self.FINGER_TIPS[1:], self.FINGER_PIPS[1:]):
            fingers.append(landmarks[tip_id].y < landmarks[pip_id].y)

        return fingers

    @staticmethod
    def _gesture_label(state):
        if not state["hand_detected"]:
            return "No Hand"
        if state["is_pinch"]:
            return "PINCH (Jump)"
        if state["is_fist"]:
            return "FIST (Shoot)"
        if state["is_open_palm"]:
            return "PALM (Pause)"
        if state["is_peace"]:
            return "PEACE"
        return "Tracking..."
