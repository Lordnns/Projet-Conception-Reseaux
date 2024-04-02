import socket
import json
client_add = input('client IP: ')
stop = 0
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def get_input():
    while True:
        valid = 1
        message = input('This is a message from client 3: ')
        if message == "stop":
            return 0, 0, 0
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
            return message, address_in, port_in
        else:
            print("invalid entry")


try:
    current = ""
    while stop == 0:
        data, address, port = get_input()
        if data == 0:
            stop = 1
        else:
            server_address = (address, int(port))
            if address != current:
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(server_address)
            sock.sendall(data.encode())
            timeout = 1  # 1 second timeout

            while True:
                data = sock.recv(1024)
                if data.decode() == "END":
                    break
                print(data.decode())

            current = address
finally:
    sock.close()
