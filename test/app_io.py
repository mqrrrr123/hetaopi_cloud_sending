#!/usr/bin/env python3
import board
import os
from time import sleep
from digitalio import DigitalInOut, Direction
#led = DigitalInOut(board.PL3)
#led.direction = Direction.OUTPUT

#led.value = 1
#sleep(60)
#led.value = 0

control_path = {
    0: "/sys/class/pwm/pwmchip0",
    1: "/sys/class/pwm/pwmchip16",
    2: "/sys/class/pwm/pwmchip20",
    3: "/sys/class/pwm/pwmchip22",
}

def write_to_file(path: str, value: str) -> None:
    with open(path, "w") as f:
        f.write(value)

def pwm_export(control: int, channel: int) -> None:
    pwm_dir = f"{control_path[control]}/pwm{channel}"
    if os.path.exists(pwm_dir):
        return
    write_to_file(f"{control_path[control]}/export", str(channel))

def pwm_config(control: int, channel: int, period: int, duty_cycle: int) -> None:

    write_to_file(f"{control_path[control]}/pwm{channel}/period", str(period))
    write_to_file(f"{control_path[control]}/pwm{channel}/duty_cycle", str(duty_cycle))
    write_to_file(f"{control_path[control]}/pwm{channel}/polarity", "normal")

def pwm_enable(control: int, channel: int) -> None:

    write_to_file(f"{control_path[control]}/pwm{channel}/enable", "1")

def pwm_disable(control: int, channel: int) -> None:

    write_to_file(f"{control_path[control]}/pwm{channel}/enable", "0")

pwm_export(3, 1)  
pwm_config(3, 1, 10000000, 5000000)  
pwm_enable(3, 1)  
sleep(60)
pwm_disable(3, 1)