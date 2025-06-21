import os
import uuid
import re
from pathlib import Path

def get_usb_camera_uuids():
    camera_info = []
    v4l_path = Path('/sys/class/video4linux')
    
    if not v4l_path.exists():
        return []
    
    for v4l_dev in v4l_path.iterdir():
        dev_name = v4l_dev.name
        if not dev_name.startswith('video'):
            continue
        
        dev_node = f"/dev/{dev_name}"
        print(f"Processing: {dev_node}")
        
        try:
            # 
            udev_info = os.popen(f"udevadm info -q property -n {dev_node} 2>/dev/null").read()
            
            # 
            vendor_match = re.search(r'ID_VENDOR_ID=([0-9a-fA-F]+)', udev_info)
            product_match = re.search(r'ID_MODEL_ID=([0-9a-fA-F]+)', udev_info)
            serial_match = re.search(r'ID_SERIAL_SHORT=([\w]+)', udev_info)
            
            vendor_id = vendor_match.group(1).lower() if vendor_match else 'unknown'
            product_id = product_match.group(1).lower() if product_match else 'unknown'
            serial = serial_match.group(1) if serial_match else 'noserial'
            
            # 
            # 
            if serial != 'noserial':
                unique_str = f"{dev_name}:{serial}"
            else:
                unique_str = f"{dev_name}:{vendor_id}_{product_id}"
            
            # 
            namespace = uuid.NAMESPACE_DNS
            dev_uuid = uuid.uuid5(namespace, unique_str)
            
            camera_info.append((dev_node, str(dev_uuid)))
            
        except Exception as e:
            print(f"Error for {dev_node}: {str(e)}")
    
    return camera_info

if __name__ == '__main__':
    print("Detecting USB cameras...")
    cameras = get_usb_camera_uuids()
    
    if not cameras:
        print("No USB cameras found")
    else:
        print("\nDetected USB cameras:")
        for idx, (dev, uid) in enumerate(cameras):
            print(f"  {idx+1}. Device: {dev} => UUID: {uid}")