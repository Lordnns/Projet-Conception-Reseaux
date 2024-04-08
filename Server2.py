import socket
import threading
import json
from Server_util import *
server_add = input('server IP: ')
port = 8080
dic = {}


def handle_client(client_sock):
    print("Accepted Connection".format())
    remember = []
    # Receive and send data
    data = client_sock.recv(1024)
    while data:
        # RECEIVE
        print("Received: {}".format(data.decode('utf-8')))
        if not validate_json(data):
            message = "request not a JSON"
            message = message.encode()
            client_sock.send(b"" + message)
        else:
            data = json.loads(data)

            # POST
            if data["operation"] == "POST":
                if data["rsrcid"] in dic:
                    dic[data["rsrcid"]] = data["data"]
                    message = '{"server": ' + '"' + server_add + '"' + ', "code": ' + '"' + "201" + '"' + ', "rsrc": ' + '"' + data["rsrcid"] + '"' + ', "message": ' + '"' + "ressource modifié" + '"' + '}'
                    json.loads(message)
                    message = message.encode()
                    client_sock.send(b"" + message)
                else:
                    dic[data["rsrcid"]] = data["data"]
                    message = '{"server": ' + '"' + server_add + '"' + ', "code": ' + '"' + "201" + '"' + ', "rsrc": ' + '"' + data["rsrcid"] + '"' + ', "message": ' + '"' + "ressource créée" + '"' + '}'
                    json.loads(message)
                    message = message.encode()
                    client_sock.send(b"" + message)
                if data["rsrcid"] in remember:
                    json_string = handle_dollar(dic[data["rsrcid"]], data["rsrcid"])
                    message = '{"server": ' + '"' + server_add + '"' + ', "code": ' + '"' + "210" + '"' + ', "rsrc": ' + '"' +data["rsrcid"] + '"' + ', "data": ' + json_string + ', "message": ' + '"' + "" + '"' + '}'
                    json.loads(message)
                    message = message.encode()
                    client_sock.send(b"" + message)
                print(dic)

            # GET
            if data["operation"] == "GET":
                if data["rsrcid"] not in dic:
                    message = '{"server": ' + '"' + server_add + '"' + ', "code": ' + '"' + "404" + '"' + ', "rsrc": ' + '"' + data["rsrcid"] + '"' + ', "data": ' + '"' + "" + '"' + ', "message": ' + '"' + "ressource inconnue" + '"' + '}'
                    json.loads(message)
                    message = message.encode()
                    client_sock.send(b"" + message)
                elif data["rsrcid"] in dic and data["protocol"] == "rdo":
                    json_string = handle_dollar(dic[data["rsrcid"]], data["rsrcid"])
                    message = '{"server": '+'"'+ server_add+ '"' +', "code": ' + '"' + "202" + '"' + ', "rsrc": '+'"'+data["rsrcid"]+'"'+', "data": '+json_string+', "message": '+'"'+""+'"'+'}'
                    json.loads(message)
                    message = message.encode()
                    client_sock.send(b"" + message)
                elif data["rsrcid"] in dic and data["protocol"] == "wrdo":
                    json_string = handle_dollar(dic[data["rsrcid"]], data["rsrcid"])
                    message = '{"server": '+'"'+ server_add+ '"' +', "code": ' + '"' + "210" + '"' + ', "rsrc": '+'"'+data["rsrcid"]+'"'+', "data": '+json_string+', "message": '+'"'+""+'"'+'}'
                    json.loads(message)
                    message = message.encode()
                    client_sock.send(b"" + message)
                    remember.append(data["rsrcid"])
                else:
                    message = '{"server": '+'"'+ server_add+ '"' +', "code": ' + '"' + "404" + '"' + ', "rsrc": '+'"'+data["rsrcid"]+'"'+', "data": '+'"'+""+'"'+', "message": '+'"'+"ressource inconnue"+'"'+'}'
                    message = message.encode()
                    client_sock.send(b"" + message)

        # END OF SENDING PHASE
        data = client_sock.recv(1024)
    print("Client disconnected".format())


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((server_add, port))
server_socket.listen(5)
while True:
    client_socket, address = server_socket.accept()
    client_handler = threading.Thread(target=handle_client, args = (client_socket,))
    client_handler.start()







