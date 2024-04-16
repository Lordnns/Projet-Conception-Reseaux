from asyncio.windows_events import NULL
from pickle import FALSE
import select
import sys
import socket
import json
import threading
import time
import os
import uuid

if os.name == 'nt':
    import msvcrt
elif os.name == 'posix':
    import termios
    import tty

# Generate a unique client ID
client_id = str(uuid.uuid4())
print("Client ID: {}".format(client_id))   

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
    
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        # Switch to non-canonical mode
        tty.setcbreak(sys.stdin.fileno())
        
        console_lock.acquire()
        if not prompt_written:
            print('Enter command: ', end='', flush=True)
            prompt_written = True
        console_lock.release()
        
        input_line = ""
        
        while True:
            input_ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if input_ready:
                is_typing = True
                data = os.read(sys.stdin.fileno(), 1024).decode('utf-8')  # Adjust size as needed
                if '\x7f' in data:
                    # Handle backspace
                    input_line = input_line[:-1]
                else:
                    input_line += data.replace('\r', '').replace('\n', '')  # Normalize line endings

                # Check for newline, which indicates submission
                if '\n' in data:
                    print()
                    is_typing = False
                    prompt_written = False
                    # Assuming flush_message_queue() is a function to handle other operations
                    flush_message_queue()  
                    return get_input(input_line)


                # After processing the available input, print the entire input line
                sys.stdout.write('\r\033[K')
                sys.stdout.write('Enter command: ' + input_line)
                sys.stdout.flush()
                
    finally:
        # Restore the terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

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
            
            if char in ('\r', '\n'):  # If it's the Enter key
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

# check if the ip address is possible
def validate_ip_address(ip):
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

# check if the port is in the range of existing port
def validate_port(port):
    try:
        port_num = int(port)
        if 0 < port_num < 65536:
            return True
        else:
            return False
    except ValueError:
        return False

def get_input(message):  
    try:
        valid = True
        
        if message == "stop":
            return 0, 0, 0, None

        operation, _, rest = message.partition(" ")
        if operation not in {"POST", "GET"}:
            valid = False
            raise ValueError("Invalid operation: {}".format(operation))

        protocol, _, rest = rest.partition(":")
        if protocol not in {"rdo", "wrdo"}:
            valid = False
            raise ValueError("Invalid protocol: {}".format(protocol))

        buffer1, _, rest = rest.partition("/")
        buffer2, _, rest = rest.partition("/")
        address_in, _, rest = rest.partition(":")
        port_in, _, rest = rest.partition("/")
        rsrcid, _, data_in = rest.partition(" ")

        if not (validate_ip_address(address_in)):
            valid = False
            raise ValueError("Invalid IP address")
        
        if not (validate_port(port_in)):
            valid = False
            raise ValueError("Invalid port")
        path = []
        current_identity = "{server_address}:{port}/{resource_id}".format(
            server_address= client_add,
            port= NULL,
            resource_id= rsrcid
        )
        path.append(current_identity)
        path_str = str(path)
        path_json = json.dumps(path_str)

        if valid:
            if operation == "POST":
                message = '{"client_address": "' + client_add + '", "protocol": "' + protocol + '", "operation": "' + operation + '", "rsrcid": "' + rsrcid + '", "path": ' + path_json + ', "data": ' + data_in + '}'
            elif operation == "GET":
                message = '{"client_address": "' + client_add + '", "protocol": "' + protocol + '", "operation": "' + operation + '", "rsrcid": "' + rsrcid + '", "path": ' + path_json + '}'

                 
            return message, address_in, port_in, protocol

    except Exception as e:
        print("Error processing input:", e)
        handle_invalid_command()
        return None
    

def handle_server_communication(message, address, port, protocol):
    server_address = (address, int(port))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            global take_new_command
            s.connect(server_address)
            
            s.sendall(client_id.encode())
            accepted = s.recv(1024).decode()
            if accepted == "Received client ID":
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
                                #print_server_response("Connection closed by server.")
                                break
                            if is_typing:
                                message_queue.put(data)
                            else:
                                print_server_response("Update:", data)
                                if message_received == 1:
                                    take_new_command = True;
                        except Exception as e:
                            print_server_response("Error listening for updates: {}".format(e))
                            break
            else:
                print_server_response("Error client id not transfered.")

        except Exception as e:
            print("Error communicating with server: {}".format(e))
        

def handle_invalid_command():
    global prompt_written, take_new_command
    console_lock.acquire()
    print("Invalid command. Please try again.")
    prompt_written = False  # Reset to allow re-prompting
    take_new_command = True
    console_lock.release()
    
    

def rewrite_prompt():
    print("")

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
        
def print_enter_command():
    global prompt_written
    console_lock.acquire()
    try:
        if prompt_written:
            return
    
        print('Enter command: ', end='', flush=True)
        prompt_written = True
        
    finally:
        console_lock.release()
        
def print_queue(*args):
    global prompt_written
    console_lock.acquire()
    try:
        print(*args)
        
    finally:
        console_lock.release()

def flush_message_queue():
    global message_queue
    while not message_queue.empty():
        print_queue("Queued Message:", message_queue.get())
        
def main():
    global stop
    stop = False

    while not stop:
        global take_new_command
        if take_new_command:
            take_new_command = False
            command_info = get_input_non_blocking()
            
            if command_info:
                if command_info[0] == "stop":
                    stop = True
                else:
                    message, address, port, protocol = command_info
                    threading.Thread(target=handle_server_communication, args=(message, address, port, protocol)).start()

if __name__ == "__main__":
    main()
