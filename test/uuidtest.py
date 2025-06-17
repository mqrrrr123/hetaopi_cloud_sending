import os
import uuid
from pathlib import Path

def get_usb_camera_uuids():

    camera_info = []
    

    v4l_path = Path('/sys/class/video4linux')
    for v4l_dev in v4l_path.iterdir():
        if not v4l_dev.is_dir() or not v4l_dev.name.startswith('video'):
            continue
        
        try:

            dev_path = v4l_dev / 'device'
            usb_path = dev_path.resolve()
            

            while 'usb' not in str(usb_path) and usb_path != Path('/'):
                usb_path = usb_path.parent.resolve()
            
            if 'usb' not in str(usb_path):
                continue  
            

            vendor_file = usb_path / 'idVendor'
            product_file = usb_path / 'idProduct'
            serial_file = usb_path / 'serial'
            
  
            if not vendor_file.exists():
                parent_usb = usb_path.parent
                vendor_file = parent_usb / 'idVendor'
                product_file = parent_usb / 'idProduct'
                serial_file = parent_usb / 'serial'
            
 
            vendor_id = vendor_file.read_text().strip() if vendor_file.exists() else 'unknown'
            product_id = product_file.read_text().strip() if product_file.exists() else 'unknown'
            serial = serial_file.read_text().strip() if serial_file.exists() else 'no_serial'

            unique_str = f"{vendor_id}:{product_id}:{serial}"
            namespace = uuid.NAMESPACE_OID
            dev_uuid = uuid.uuid5(namespace, unique_str)
            
            camera_info.append( (v4l_dev.name, str(dev_uuid)) )
            
        except Exception as e:
            print(f" {v4l_dev.name} errors: {str(e)}")
            continue
            
    return camera_info

if __name__ == '__main__':
    cameras = get_usb_camera_uuids()
    
    if not cameras:
        print("no camera")
    else:
        print("usb")
        for dev, uid in cameras:
            print(f"  - items: /dev/{dev} => UUID: {uid}")