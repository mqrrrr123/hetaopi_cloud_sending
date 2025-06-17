import cv2
import uuid
from pathlib import Path

def get_camera_uuid_map():

    return {
        '9f7f9c0b-bd09-53db-9a2b-20daffdb4028': '/dev/video0',
        '48b5ddac-a396-5275-b6cb-32edddb4b5bf': '/dev/video1'
    }

def open_camera_by_uuid(target_uuid, api_preference=cv2.CAP_V4L2):

    uuid_map = get_camera_uuid_map()
    
    if target_uuid not in uuid_map:
        available_uuids = "\n".join(uuid_map.keys())
        raise ValueError(f"no  UUID please\n{available_uuids}")
    

    device_path = uuid_map[target_uuid]
    

    if not Path(device_path).exists():
        raise FileNotFoundError(f" {device_path} no cameras")
    
    
    cap = cv2.VideoCapture(device_path, api_preference)
    

    if not cap.isOpened():
        raise RuntimeError(f" {device_path} no get")
    
    return cap


if __name__ == "__main__":

    TARGET_UUID = '9f7f9c0b-bd09-53db-9a2b-20daffdb4028'
    
    try:

        cap = open_camera_by_uuid(TARGET_UUID)
        print(f"success {TARGET_UUID}")
        while True:
            ret, frame = cap.read()
            if not ret:
                print("out...")
                break
                
            cv2.imshow('Camera', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        print(f"fauld: {str(e)}")
        
    finally:
        if 'cap' in locals():
            cap.release()
        cv2.destroyAllWindows()