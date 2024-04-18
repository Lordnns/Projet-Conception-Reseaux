import json
import socket
import uuid
from copy import deepcopy
import os

# fonction qui valide si l'entré est un JSON
def validate_json(tested_json):
    try:
        json.loads(tested_json)
    except ValueError:
        return False
    return True

# check if the ip address is possible
def validate_ip_address(ip):
    # Check for IPv4 and IPv6 addresses
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, ip)
            return True
        except socket.error:
            continue

    # Check for DNS name
    try:
        socket.gethostbyname(ip)
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
        if valid and validate_ip_address(address_in) and validate_port(port_in):
            return message_json, address_in, port_in
        else:
            return request_to_send, 0, 0


# Fonction qui ouvre un socket client depuis le serveur vers le serveur de référence.
def server_as_client(request_to_send):
    print("")
    validation = True
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data, address, port = get_input_auto(request_to_send)
    try:

        if address == 0:
            validation = False
            return '{' + '"ERROR: INVALID $ ": ' + '"' + data + '"' + '}', validation
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
        return data.decode(), validation
    except Exception:
        validation = False
        message = {
            "server": address,
            "code": "404",
            "rsrc": "",
            "data": "",
            "message": "ressource inconnue"
        }
        message_json = json.dumps(message)
        return message_json, validation
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
def replace_dollar(path_to_reference, my_json, origin_id, origin_ip, origin_port):

    # Utilise le chemin fourni dans path pour reconstruire la commande sous forme de string.
    # Ce string sera exécuter sous forme de code. Pas idéal, mais fonctionne pour le moment.
    # Opère sur le JSON et non son contenu, risque mitigé.
    # Idéalement il faudrait refaire le code pour qu'il change directement en place dans Find_dollar.

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
    if loop_test[-1] == origin_id and loop_test[-2] == origin_ip + ":" + str(origin_port):
        ref_data = {'ERROR:': 'Data is referencing itself'}
        ref_data = json.dumps(ref_data)
        code_string = code_string + "=" + ref_data
        exec(code_string)
        validation = False
        return my_json, validation

    # Envois la référence en requête au client-serveur et ajoute celle-ci
    # à place de la ref
    ref_data, validation = server_as_client(reference)
    ref_data = json.loads(ref_data)
    ref_data.pop('rsrc', None)
    ref_data.pop('message', None)
    if 'code' in ref_data.keys():
        if ref_data['code'] == "404":
            ref_data['data'] = "null"
            validation = False
        else:
            ref_data['code'] = "200"

    # execute le string sous forme de code pout remplacer la référence par son data.
    ref_data = json.dumps(ref_data)
    code_string = code_string + "=" + ref_data
    exec(code_string)
    return my_json, validation


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
def handle_dollar(data_to_handle, origin_id, origin_ip, origin_port):
    validation = True
    data_copy = deepcopy(data_to_handle)  # pour pas modif l'original dans le dic serveur
    reference_path = find_dollar(data_copy)
    while isinstance(reference_path, str):
        data_copy, validation_check = replace_dollar(reference_path, data_copy, origin_id, origin_ip, origin_port)
        if not validation_check:
            validation = False
        reference_path = find_dollar(data_copy)
    return data_copy, validation

# Save dict to json file
def save_dict_to_json(data_dict, folder_path, filename):
    file_path = os.path.join(folder_path, filename)
    with open(file_path, 'w') as json_file:
        json.dump(data_dict, json_file, indent=4)

# Create a folder for local DB if it does not exist 
def init_local_db(server_ip, port):
    folder_name = "{}_{}".format(server_ip, port)
    folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder_name)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

# Return local DB folder path
def get_folder_path(server_ip, port):
    folder_name = "{}_{}".format(server_ip, port)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), folder_name)

# Load the DB into server dict 
def load_data_from_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as json_file:
            return json.load(json_file)
    else:
        return {}






