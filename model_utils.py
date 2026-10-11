import os
import urllib.request
import cv2
import numpy as np

# Model URLs for OpenCV Gender Classifier (Levi & Hassner Caffe Model)
GENDER_PROTOTXT_URL = "https://raw.githubusercontent.com/spmallick/learnopencv/master/AgeGender/gender_deploy.prototxt"
GENDER_CAFFEMODEL_URL = "https://raw.githubusercontent.com/GilLevi/AgeGenderDeepLearning/master/models/gender_net.caffemodel"

# Directory to cache downloaded models
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

GENDER_CLASSES = ['Male', 'Female']
# Mean values for Caffe Gender Net preprocessing (BGR)
MODEL_MEAN_VALUES = (78.4263377603, 87.7689143744, 114.895847746)


def _download_file(url, target_path):
    """Helper to download file with browser User-Agent header."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
        out_file.write(response.read())


def ensure_models_exist():
    """Ensure that gender classification model files exist locally. Downloads if missing."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    prototxt_path = os.path.join(MODELS_DIR, "gender_deploy.prototxt")
    caffemodel_path = os.path.join(MODELS_DIR, "gender_net.caffemodel")

    if not os.path.exists(prototxt_path) or os.path.getsize(prototxt_path) < 1000:
        print(f"Downloading {GENDER_PROTOTXT_URL}...")
        try:
            _download_file(GENDER_PROTOTXT_URL, prototxt_path)
            print("Downloaded prototxt successfully.")
        except Exception as e:
            print(f"Error downloading prototxt: {e}")

    if not os.path.exists(caffemodel_path) or os.path.getsize(caffemodel_path) < 10000000:
        print(f"Downloading {GENDER_CAFFEMODEL_URL}...")
        try:
            _download_file(GENDER_CAFFEMODEL_URL, caffemodel_path)
            print("Downloaded caffemodel successfully.")
        except Exception as e:
            print(f"Error downloading caffemodel: {e}")

    return prototxt_path, caffemodel_path



def _create_dnn_net(prototxt_path, caffemodel_path):
    """Creates OpenCV DNN Net supporting OpenCV 4.x and 5.x API."""
    if hasattr(cv2.dnn, 'readNetFromCaffe'):
        return cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
    elif hasattr(cv2.dnn, 'readNet'):
        return cv2.dnn.readNet(model=caffemodel_path, config=prototxt_path)
    else:
        raise AttributeError("OpenCV DNN module has no net loader function")


def load_gender_net(use_gpu=True):
    """Loads OpenCV DNN Gender classification network with CUDA GPU support if available."""
    prototxt_path, caffemodel_path = ensure_models_exist()
    if os.path.exists(prototxt_path) and os.path.exists(caffemodel_path) and os.path.getsize(caffemodel_path) > 1000000:
        try:
            net = _create_dnn_net(prototxt_path, caffemodel_path)
            cuda_available = False
            if use_gpu and hasattr(cv2, 'cuda'):
                try:
                    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                        cuda_available = True
                except Exception:
                    cuda_available = False
            
            if cuda_available:
                print("⚡ OpenCV DNN: Enabling CUDA GPU backend for Caffe Gender Net.")
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
            else:
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            return net
        except Exception as e:
            print(f"CUDA initialization failed for Caffe gender model, falling back to CPU: {e}")
            try:
                net = _create_dnn_net(prototxt_path, caffemodel_path)
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                return net
            except Exception as e2:
                print(f"Error loading Caffe gender model: {e2}")
                return None
    return None


def get_face_cascade():
    """Loads OpenCV Haar Cascade Frontal Face Detector."""
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    if os.path.exists(cascade_path):
        return cv2.CascadeClassifier(cascade_path)
    return None


def get_profile_cascade():
    """Loads OpenCV Haar Cascade Profile Face Detector for side/facing away views."""
    cascade_path = cv2.data.haarcascades + 'haarcascade_profileface.xml'
    if os.path.exists(cascade_path):
        return cv2.CascadeClassifier(cascade_path)
    return None



def classify_gender(gender_net, face_crop):
    """
    Classifies gender from a cropped face image.
    Returns tuple: (gender_label, confidence_score)
    """
    if gender_net is None or face_crop is None or face_crop.size == 0:
        return ("Unknown", 0.0)

    try:
        # Resize to 227x227 expected by Levi-Hassner Caffe model
        blob = cv2.dnn.blobFromImage(
            face_crop,
            scalefactor=1.0,
            size=(227, 227),
            mean=MODEL_MEAN_VALUES,
            swapRB=False,
            crop=False
        )
        gender_net.setInput(blob)
        preds = gender_net.forward()
        # preds[0] has scores for ['Male', 'Female']
        gender_idx = int(np.argmax(preds[0]))
        confidence = float(preds[0][gender_idx])
        label = GENDER_CLASSES[gender_idx]
        return (label, confidence)
    except Exception as e:
        print(f"Gender classification exception: {e}")
        return ("Unknown", 0.0)
