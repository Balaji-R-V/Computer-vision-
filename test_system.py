import cv2
import numpy as np
import os
import sys

def create_sample_test_image():
    """Generates a synthetic test image with a mock person shape and background for pipeline testing."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Background gradient
    for y in range(480):
        img[y, :, :] = (int(40 + y * 0.1), int(30 + y * 0.05), int(60 - y * 0.08))
    
    # Draw simple person body representation (head circle + torso)
    cv2.circle(img, (320, 140), 50, (210, 180, 140), -1)  # Head / Face
    cv2.ellipse(img, (320, 320), (90, 140), 0, 0, 180, (180, 100, 50), -1) # Torso
    
    # Text annotation
    cv2.putText(img, "Test Frame - Head & Object Detector", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
    test_path = "sample_test.jpg"
    cv2.imwrite(test_path, img)
    return test_path

if __name__ == "__main__":
    print("Testing detector setup with Virtual Project Boundaries...")
    test_img_path = create_sample_test_image()
    print(f"Created sample test image at {test_img_path}")
    
    try:
        from detector import HeadGenderYOLODetector
        detector = HeadGenderYOLODetector()
        frame = cv2.imread(test_img_path)
        
        # Test 4-Point Custom Polygon Boundaries
        test_project_zones = [
            {'name': 'Project Alpha Area', 'project_code': 'PRJ-A', 'points': [[0.05, 0.1], [0.55, 0.12], [0.58, 0.9], [0.05, 0.9]]},
            {'name': 'Project Beta Zone', 'project_code': 'PRJ-B', 'points': [[0.62, 0.1], [0.95, 0.1], [0.95, 0.9], [0.62, 0.9]]}
        ]
        
        annotated_frame, stats = detector.process_frame(frame, zones=test_project_zones)
        print("\n✅ Success! Processed frame with Virtual Project Segregation Stats:")
        print(f"  - Total People: {stats['person_count']}")
        print(f"  - Male / Female: {stats['male_count']} / {stats['female_count']}")
        print(f"  - Sitting / Standing: {stats['sitting_count']} / {stats['standing_count']}")
        print(f"  - Unassigned Workforce: {stats['unassigned_count']}")
        print("  - Project Breakdown:")
        for zname, zdata in stats['zone_stats'].items():
            print(f"     📁 {zname} ({zdata['project_code']}): {zdata['total']} occupants (Male: {zdata['male']}, Female: {zdata['female']}, Sitting: {zdata['sitting']}, Standing: {zdata['standing']})")
        
        cv2.imwrite("sample_output.jpg", annotated_frame)
        print("\nSaved annotated output to sample_output.jpg")
    except Exception as e:
        print(f"Detector test execution failed: {e}")
        import traceback
        traceback.print_exc()
