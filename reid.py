"""
Person re-identification embeddings (OSNet x0.25 trained on MSMT17, ONNX).

Replaces the old colour-histogram descriptor, whose cosine similarity could not separate different
people (different-person scores overlapped same-person scores). OSNet separates them with a wide margin.
The ONNX export has a fixed batch of 16, so crops are padded into one batch per call.
"""
import os

import cv2
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'osnet_x0_25_msmt17.onnx')
MODEL_REPO = 'anriha/osnet_x0_25_msmt17'
BATCH = 16
INPUT_W, INPUT_H = 128, 256
EMBEDDING_DIM = 512
MIN_CROP_H, MIN_CROP_W = 48, 20          # smaller crops are too blurry to identify reliably
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _ensure_model():
    if os.path.exists(MODEL_PATH):
        return True
    try:
        import shutil
        from huggingface_hub import hf_hub_download
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        shutil.copy(hf_hub_download(MODEL_REPO, 'osnet_x0_25_msmt17.onnx'), MODEL_PATH)
        return True
    except Exception as e:
        print(f"⚠️ Could not download ReID model: {e}", flush=True)
        return False


class PersonReID:
    dim = EMBEDDING_DIM

    def __init__(self):
        self.session = None
        if not _ensure_model():
            return
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
            self.input_name = self.session.get_inputs()[0].name
            self.embed([np.zeros((INPUT_H, INPUT_W, 3), np.uint8)])   # warm-up
            print("🧬 Person ReID model loaded (OSNet x0.25 / MSMT17).", flush=True)
        except Exception as e:
            self.session = None
            print(f"⚠️ ReID model unavailable, matching will be disabled: {e}", flush=True)

    @property
    def available(self):
        return self.session is not None

    @staticmethod
    def usable(crop):
        return crop is not None and crop.ndim == 3 and crop.shape[0] >= MIN_CROP_H and crop.shape[1] >= MIN_CROP_W

    @staticmethod
    def _prep(crop):
        c = cv2.resize(crop, (INPUT_W, INPUT_H))
        c = cv2.cvtColor(c, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        return ((c - _MEAN) / _STD).transpose(2, 0, 1)

    def embed(self, crops):
        """Returns one L2-normalised 512-d vector per crop, or None for unusable crops / no model."""
        out = [None] * len(crops)
        if not self.available:
            return out
        idx = [i for i, c in enumerate(crops) if self.usable(c) or (c is not None and c.shape[:2] == (INPUT_H, INPUT_W))]
        for start in range(0, len(idx), BATCH):
            chunk = idx[start:start + BATCH]
            batch = np.zeros((BATCH, 3, INPUT_H, INPUT_W), np.float32)
            for k, i in enumerate(chunk):
                batch[k] = self._prep(crops[i])
            feats = self.session.run(None, {self.input_name: batch})[0][:len(chunk)]
            feats = feats / np.maximum(np.linalg.norm(feats, axis=1, keepdims=True), 1e-9)
            for k, i in enumerate(chunk):
                out[i] = feats[k].astype(np.float32)
        return out
