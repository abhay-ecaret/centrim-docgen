import sys
import threading
import itertools
import time

spinner_running = False
spinner_thread = None

def spinner_animation():
    spinner_chars = itertools.cycle(['-', '\\', '|', '/'])
    while spinner_running:
        sys.stdout.write(next(spinner_chars) + '\r')
        sys.stdout.flush()
        time.sleep(0.1)

def start_spinner():
    global spinner_running, spinner_thread
    spinner_running = True
    spinner_thread = threading.Thread(target=spinner_animation)
    spinner_thread.daemon = True
    spinner_thread.start()

def stop_spinner():
    global spinner_running, spinner_thread
    if spinner_running:
        spinner_running = False
        if spinner_thread and spinner_thread.is_alive():
            spinner_thread.join(timeout=0.2)
