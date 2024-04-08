from pickle import FALSE
import select
import sys
import socket
import json
import threading
import time
import os
# Additional imports for Windows
if os.name == 'nt':
    import msvcrt
    
client_add = input('client IP: ')
stop = 0
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
from queue import Queue

message_queue = Queue()
console_lock = threading.Lock()

is_typing = False
prompt_written = False
take_new_command = True

def get_input_non_blocking_unix():
    
    global is_typing, prompt_written
    
    console_lock.acquire()
    if not prompt_written:
        print('Enter command: ', end='', flush=True)
        prompt_written = True
    console_lock.release()
    
    while True:
        input_ready, _, _ = select.select([sys.stdin], [], [], 0.1)
        if input_ready:
            is_typing = True
            message = sys.stdin.readline().strip()
            is_typing = False
            prompt_written = False
            flush_message_queue()
            return get_input(message)

def get_input_non_blocking_windows():
    global is_typing, prompt_written
    
    input_line = ''  # Initialize an empty string to accumulate characters
    
    console_lock.acquire()
    if not prompt_written:
        print('Enter command: ', end='', flush=True)
        prompt_written = True
    console_lock.release()
    
    while True:
        if msvcrt.kbhit():  # Check if a keypress is present
            is_typing = True
            char = msvcrt.getwch()  # Read the character
            
            if char == '\r':  # If it's the Enter key
                print()
                is_typing = False
                prompt_written = False
                flush_message_queue()
                return get_input(input_line)
            elif char == '\x08':  # Handle backspace
                input_line = input_line[:-1]
                sys.stdout.write('\b \b')
            else:
                input_line += char  # Add the character to the input line
                sys.stdout.write(char)  # Echo the character since `getwch()` doesn't
            sys.stdout.flush()
        else:
            time.sleep(0.1)
  
def get_input_non_blocking():
    if os.name == 'posix':
        return get_input_non_blocking_unix()
    elif os.name == 'nt':
        return get_input_non_blocking_windows()

def get_input(message):  
        
        valid = 1
        
        if message == "stop":
            return 0, 0, 0, None
        operation, op6, rest = message.partition(" ")
        if operation != "POST" and operation != "GET":
            valid = 0
        protocol, op, rest = rest.partition(":")
        if protocol != "rdo" and protocol != "wrdo":
            valid = 0
        buffer1, op1, rest = rest.partition("/")
        buffer2, op2, rest = rest.partition("/")
        address_in, op3, rest = rest.partition(":")
        port_in, op4, rest = rest.partition("/")
        rsrcid, op, data_in = rest.partition(" ")
        if operation == "POST":
            message = '{'+'"client_address": ' + '"' + client_add + '"' +',"protocol": ' + '"' + protocol + '"' + ', "operation": ' + '"' + operation + '"' + ', "rsrcid": ' + '"' + rsrcid + '"' + ', "data": ' + data_in + '}'
        if operation == "GET":
            message = '{'+'"client_address": ' + '"' + client_add + '"' +',"protocol": ' + '"' + protocol + '"' + ', "operation": ' + '"' + operation + '"' + ', "rsrcid": ' + '"' + rsrcid +'"' + '}'
        if valid == 1:
            return message, address_in, port_in, protocol

def handle_server_communication(message, address, port, protocol):
    server_address = (address, int(port))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            global take_new_command
            s.connect(server_address)
            s.sendall(message.encode())

            # For "RDO" operations, wait for a single response and then return
            if protocol == "rdo":
                response = s.recv(1024).decode()
                print_server_response("Response:", response)
                take_new_command = True
                
                
            # For "WRDO" operations, spawn a new thread to handle continuous updates
            elif protocol == "wrdo":
                global is_typing, message_queue
                message_received = 0
                while True:
                    try:
                        data = s.recv(1024).decode()
                        message_received += 1
                        if not data:
                            print_server_response("Connection closed by server.")
                            break
                        if is_typing:
                            message_queue.put(data)
                        else:
                            print_server_response("Update:", data)
                            if message_received == 1:
                                take_new_command = True;
                    except Exception as e:
                        print_server_response(f"Error listening for updates: {e}")
                        break

        except Exception as e:
            print(f"Error communicating with server: {e}")

def rewrite_prompt():
    # Move the cursor up one line
    sys.stdout.write('\033[F')
    # Clear the current line
    sys.stdout.write('\033[K')

def print_server_response(*args):
    global prompt_written
    console_lock.acquire()
    try:
        if prompt_written:
            rewrite_prompt()
    
        print(*args)
        print('Enter command: ', end='', flush=True)
        prompt_written = True
        
    finally:
        console_lock.release()

def flush_message_queue():
    global message_queue
    while not message_queue.empty():
        print_server_response("Queued Message:", message_queue.get())
        
def main():
    global stop
    stop = False

    while not stop:
        global take_new_command
        if take_new_command:
            command_info = get_input_non_blocking()
            take_new_command = False
            if command_info:
                if command_info[0] == "stop":
                    stop = True
                else:
                    message, address, port, protocol = command_info
                    threading.Thread(target=handle_server_communication, args=(message, address, port, protocol)).start()

if __name__ == "__main__":
    main()
