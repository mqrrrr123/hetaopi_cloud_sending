import os
import uuid
import re
import sys
from pathlib import Path

TARGET_UUID = "25a955ae-5302-542f-a6c7-7198b08636d1"

def find_target_device(target_uuid):

    v4l_path = Path('/sys/class/video4linux')
    
    if not v4l_path.exists():
        print("f")
        return None
    
    for v4l_dev in sorted(v4l_path.iterdir(), key=lambda x: x.name):
        dev_name = v4l_dev.name
        if not dev_name.startswith('video'):
            continue
        
        dev_node = f"/dev/{dev_name}"
        
        try:
            udev_info = os.popen(f"udevadm info -q property -n {dev_node} 2>/dev/null").read()
            
            vendor_match = re.search(r'ID_VENDOR_ID=([0-9a-fA-F]+)', udev_info)
            product_match = re.search(r'ID_MODEL_ID=([0-9a-fA-F]+)', udev_info)
            serial_match = re.search(r'ID_SERIAL_SHORT=([\w]+)', udev_info)
            
            vendor_id = vendor_match.group(1).lower() if vendor_match else 'unknown'
            product_id = product_match.group(1).lower() if product_match else 'unknown'
            serial = serial_match.group(1) if serial_match else 'noserial'
            
            if serial != 'noserial':
                unique_str = f"{dev_name}:{serial}"
            else:
                unique_str = f"{dev_name}:{vendor_id}_{product_id}"
            
            namespace = uuid.NAMESPACE_DNS
            dev_uuid = str(uuid.uuid5(namespace, unique_str))
            
            if dev_uuid == target_uuid:
                print(f"get: {dev_node}")
                return dev_node
            
        except Exception as e:
            print(f" {dev_node} : {str(e)}")
            continue
    
    return None

def open_and_show_camera(dev_path):
    """"""
    cap = cv2.VideoCapture(dev_path)
    
    if not cap.isOpened():
        print(f": {dev_path}")
        return
    
    print(f" 'q' ")
    while True:
        ret, frame = cap.read()
        if not ret:
            print(f": {dev_path}")
            break
            
        cv2.imshow(f"Camera: {dev_path}", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    
    try:
        import cv2
    except ImportError:
        print("")
        sys.exit(1)
    
    print(f" '{TARGET_UUID}' ...")
    device_path = find_target_device(TARGET_UUID)
    
    if device_path:
        print(f": {device_path}")
        open_and_show_camera(device_path)
    else:
        print("f")