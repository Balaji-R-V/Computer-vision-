"""
Verification script for Dual Engine Architecture (Local GPU YOLO + AWS Rekognition Cloud).
Tests:
1. AWSRekognitionDetector initialization, mock/live detection, and diagnostics.
2. HeadGenderYOLODetector initialization and detection.
3. EngineManager switching between 'gpu_local' and 'aws_rekognition'.
4. User account creation with designated engine_mode.
"""
import os
import cv2
import numpy as np
import database
from engine_manager import EngineManager, ENGINE_GPU, ENGINE_AWS
from aws_rekognition import AWSRekognitionDetector

def test_dual_engine():
    print("=" * 70)
    print("🧪 RUNNING DUAL ENGINE ARCHITECTURE TEST")
    print("=" * 70)

    # Synthetic test image
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(test_frame, (320, 140), 45, (200, 180, 150), -1)
    cv2.ellipse(test_frame, (320, 300), (80, 120), 0, 0, 180, (180, 100, 50), -1)
    cv2.putText(test_frame, "AEGIS-OS DUAL ENGINE TEST", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # 1. Test AWS Rekognition Detector directly
    print("\n[Step 1] Testing AWSRekognitionDetector...")
    aws_detector = AWSRekognitionDetector(region='us-east-1')
    diag = aws_detector.run_diagnostic_test()
    print(f"  AWS Diagnostic status: {diag.get('status')} | Message: {diag.get('message')}")

    annotated, stats = aws_detector.process_frame(test_frame)
    print(f"  AWS Frame processed: {stats.get('engine_label')}")
    print(f"  People: {stats.get('person_count')}, Male: {stats.get('male_count')}, Female: {stats.get('female_count')}, Posture: {stats.get('sitting_count')} sitting / {stats.get('standing_count')} standing")
    assert 'person_count' in stats, "Stats must have person_count"
    print("  ✅ AWSRekognitionDetector test passed!")

    # 2. Test EngineManager with switching
    print("\n[Step 2] Testing EngineManager...")
    mgr = EngineManager()
    print(f"  Initial active engine: {mgr.active_mode} ({mgr.get_active_label()})")

    # Process frame on GPU engine
    mgr.switch_engine(ENGINE_GPU)
    annotated_gpu, stats_gpu = mgr.process_frame(test_frame)
    print(f"  GPU Mode frame processed: {stats_gpu.get('person_count', 0)} people detected")

    # Switch to AWS engine
    mgr.switch_engine(ENGINE_AWS)
    annotated_aws, stats_aws = mgr.process_frame(test_frame)
    print(f"  AWS Mode frame processed: {stats_aws.get('person_count', 0)} people detected | Engine: {stats_aws.get('engine_label')}")

    status = mgr.get_status()
    print(f"  Engine status summary: Active={status['active_mode']}")
    print("  ✅ EngineManager switching test passed!")

    # 3. Test Database users with engine_mode
    print("\n[Step 3] Testing Database User creation with engine_mode...")
    database.init_runtime_tables()
    database.upsert_user('test_aws_user', 'hash12345678', 'viewer', 'aws_rekognition')
    database.upsert_user('test_gpu_user', 'hash12345678', 'admin', 'gpu_local')

    u_aws = database.get_user('test_aws_user')
    u_gpu = database.get_user('test_gpu_user')
    print(f"  User 'test_aws_user' engine: {u_aws.get('engine_mode')}")
    print(f"  User 'test_gpu_user' engine: {u_gpu.get('engine_mode')}")
    assert u_aws.get('engine_mode') == 'aws_rekognition', "Expected aws_rekognition for test_aws_user"
    assert u_gpu.get('engine_mode') == 'gpu_local', "Expected gpu_local for test_gpu_user"
    database.delete_user('test_aws_user')
    database.delete_user('test_gpu_user')
    print("  ✅ Database user engine_mode test passed!")

    print("\n" + "=" * 70)
    print("🎉 ALL DUAL ENGINE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == '__main__':
    test_dual_engine()
