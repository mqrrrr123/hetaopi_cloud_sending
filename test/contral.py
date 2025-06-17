#!/usr/bin/env python3

import os
import sys
import fcntl


LOCK_FILE = "/tmp/my_script.lock"

def acquire_lock():

    lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
    try:
  
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("waitting for the current finished")
        sys.exit(1)
    return lock_fd

def main():

    lock_fd = acquire_lock()
    try:

        os.system('sudo python3 /home/pi/test/app_io.py')

        os.system('python3 /home/pi/test/camera.py')
    finally:

        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

if __name__ == "__main__":
    main()