import json
import socket
import uuid
from copy import deepcopy


# fonction qui valide si l'entré est un JSON
def validate_json(tested_json):
    try:
        json.loads(tested_json)
    except ValueError:
        return False
    return True


# Fonction qui envois la requête de référence depuis le serveur vers l'autre serveur.
def get_input_auto(request_to_send):
    while True:
        valid = 1

        # transforme en commande GET rdo:...
        message = "GET " + request_to_send

        # Sépare les éléments de la request en utilisant les repères.
        operation, op6, rest = message.partition(" ")
        protocol, op, rest = rest.partition(":")
        if protocol != "rdo" and protocol != "wrdo":
            valid = 0
        buffer1, op, rest = rest.partition("/")
        buffer2, op, rest = rest.partition("/")
        address_in, op, rest = rest.partition(":")
        port_in, op, rest = rest.partition("/")
        rsrcid, op, data_in = rest.partition(" ")

        # Construction du JSON à envoyer au serveur.
        message_json = '{"protocol": ' + '"' + protocol + '"' + ', "operation": ' + '"' + operation + '"' + ', "rsrcid": ' + '"' + rsrcid +'"' '}'

        # Si valide retourne le JSON et ses informations d'envois,
        # sinon renvois la request et les code 0 et 0 pour gestion de cas.
        if valid == 1:
            return message_json, address_in, port_in
        else:
            return request_to_send, 0, 0


# Fonction qui ouvre un socket client depuis le serveur vers le serveur de référence.
def server_as_client(request_to_send):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
            data, address, port = get_input_auto(request_to_send)
            if address == 0:
                return '{' + '"ERROR: INVALID $ ": ' + '"' + data + '"' + '}'
            server_address = (address, int(port))
            sock.connect(server_address)
            client_id = str(uuid.uuid4())
            sock.sendall(client_id.encode())
            if sock.recv(1024).decode() == "Received client ID":
                sock.sendall(data.encode())

            expected = 1
            received = 0
            while received < expected:
                data = sock.recv(1024)
                received = received + 1
            return data.decode()
    finally:
        sock.close()


# Fonction qui valide si un entré string est un nombre
def is_number(string_to_test):
    try:
        float(string_to_test)
        return True
    except ValueError:
        return False


# Fonction qui remplace la référence $ par son contenu.
def replace_dollar(path_to_reference, my_json, origin_id):

    # Utilise le chemin fourni dans path pour reconstruire la commande sous forme de string.
    # Ce string sera exécuter sous forme de code.
    split_path = path_to_reference.split(" ")
    counter = 1
    code_string = "my_json"
    for split in split_path:
        if is_number(split):
            code_string = code_string + "[" + split + "]"
        elif counter != len(split_path):
            code_string = code_string + "[" + '"' + split + '"' + "]"
        counter = counter + 1

    # Trouve la référence vers pour la requête
    reference = split_path[len(split_path)-1]  # le dernier élément du path est la référence $...
    reference = reference[1:]  # retire le dollar

    # vérifie que l'adresse d'envois n'est pas la même que l'adresse
    # de référence pour bloquer l'apparition d'une loop infini
    loop_test = reference.split("/")
    if loop_test[-1] == origin_id:
        ref_data = {'ERROR:': 'Data is referencing itself'}
        ref_data = json.dumps(ref_data)
        code_string = code_string + "=" + ref_data
        exec(code_string)
        return my_json

    # Envois la référence en requête au client-serveur et ajoute celle-ci
    # à place de la ref
    ref_data = server_as_client(reference)
    ref_data = json.loads(ref_data)
    ref_data.pop('rsrc', None)
    ref_data.pop('message', None)
    if 'code' in ref_data.keys():
        if ref_data['code'] == "404":
            ref_data['data'] = "null"
        else:
            ref_data['code'] = "200"

    # execute le string sous forme de code pout remplacer la référence par son data.
    ref_data = json.dumps(ref_data)
    code_string = code_string + "=" + ref_data
    exec(code_string)
    return my_json


# Fonction récursive qui parcourt la boucle jusqu'à trouver un $ et renvois un string
# qui contient les clés de références menant à sa location.
def find_dollar(data):
    for Key in data:
        if len(Key) == 1:
            if Key == "$":
                return data


        elif isinstance(data[Key], dict):
            answer = find_dollar(data[Key])
            if isinstance(answer, str):
                return Key + " " + answer

        elif isinstance(data[Key], list):
            counter = 0
            for iterator_value in data[Key]:
                answer = find_dollar(iterator_value)
                if isinstance(answer, str):
                    return Key + " "+ str(counter) + " " + answer
                counter = counter + 1

        else:
            if data[Key][0] == "$":
                return Key + " " + data[Key]


# Fonction qui passe le message à get pour vérifier s'il contient des $ de référencement.
def handle_dollar(data_to_handle, origin_id):
    data_copy = deepcopy(data_to_handle)  # pour pas modif l'original dans le dic serveur
    reference_path = find_dollar(data_copy)
    while isinstance(reference_path, str):
        data_copy = replace_dollar(reference_path, data_copy, origin_id)
        reference_path = find_dollar(data_copy)
    return data_copy







