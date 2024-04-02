import json
import re
import socket


# fonction qui valide si l'entré est un JSON
def validate_json(jsondata):
    try:
        json.loads(jsondata)
    except ValueError:
        return False
    return True


# Fonction récursive qui parcourt la boucle jusqu'à trouver un $ et renvois un string
# qui contient les clés de références menant à sa location.
def find_dollar(data):
    for value in data:
        if len(value) == 1:
            if value == "$":
                return data
        elif isinstance(data[value], dict):
            answer = find_dollar(data[value])
            if isinstance(answer, str):
                return value + " " + answer
        elif isinstance(data[value], list):
            counter = 0
            for value2 in data[value]:
                answer = find_dollar(value2)
                if isinstance(answer, str):
                    return value + " "+ str(counter) + " " + answer
                counter = counter + 1
        else:
            if data[value][0] == "$":
                return value + " " + data[value]


# Fonction qui valide si un entré string est un nombre
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


# Fonction qui ouvre un socket client depuis le serveur vers le serveur de référence.
def server_as_client(request):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
            data, address, port = get_input_auto(request)
            if address == 0:
                return '{' + '"ERROR: INVALID $ ": ' + '"' + data + '"' + '}'
            server_address = (address, int(port))
            sock.connect(server_address)
            sock.sendall(data.encode())

            expected = 1
            received = 0
            while received < expected:
                data = sock.recv(1024)
                received = received + 1
            return data.decode()
    finally:
        sock.close()


# Fonction qui remplace la référence $ par son contenu.
def replace_dollar(path, my_json, origin_id):

    # Utilise le chemin fourni dans path pour reconstruire la commande sous forme de string.
    # Ce string sera exécuter sous forme de code.
    split_path = path.split(" ")
    counter = 1
    code_string = "my_json"
    for split in split_path:
        if is_number(split):
            code_string = code_string + "[" + split + "]"
        elif counter != len(split_path):
            code_string = code_string + "[" + '"' + split + '"' + "]"
        counter = counter + 1

    # Trouve la référence vers pour la requête
    true_path = split_path[len(split_path)-1]
    true_path = true_path[1:]
    print("TRUE_P ", true_path)

    # vérifie que l'adresse d'envois n'est pas la même que l'adresse
    # de référence pour bloquer l'apparition d'une loop infini
    loop_test = true_path.split("/")
    if loop_test[-1] == origin_id:
        ref_data = {'ERROR:': 'Data is referencing itself'}
        ref_data = json.dumps(ref_data)
        code_string = code_string + "=" + ref_data
        exec(code_string)
        return my_json

    # Envois la référence en requête au client-serveur et ajoute celle-ci
    # à place de la ref
    ref_data = server_as_client(true_path)
    ref_data = json.loads(ref_data)
    ref_data.pop('rsrc', None)
    ref_data.pop('message', None)
    if 'code' in ref_data.keys():
        if ref_data['code'] == "404":
            ref_data['code'] = "404"
            ref_data['data'] = "null"
        else:
            ref_data['code'] = "200"

    # execute le string sous forme de code pout remplacer la référence par son data.
    ref_data = json.dumps(ref_data)
    code_string = code_string + "=" + ref_data
    exec(code_string)
    return my_json


# Fonction qui envois la requête de référence depuis le serveur vers l'autre serveur.
def get_input_auto(entry):
    while True:
        valid = 1
        message = "GET " + entry
        operation, op6, rest = message.partition(" ")
        protocol, op, rest = rest.partition(":")
        if protocol != "rdo" and protocol != "wrdo":
            valid = 0
        buffer1, op1, rest = rest.partition("/")
        buffer2, op2, rest = rest.partition("/")
        address_in, op3, rest = rest.partition(":")
        port_in, op4, rest = rest.partition("/")
        rsrcid, op, data_in = rest.partition(" ")
        if operation == "GET":
            message = '{"protocol": ' + '"' + protocol + '"' + ', "operation": ' + '"' + operation + '"' + ', "rsrcid": ' + '"' + rsrcid +'"' '}'
        if valid == 1:
            return message, address_in, port_in
        else:
            return entry, 0, 0


# Fonction qui passe le message à get pour vérifier si il contient des $ de référencement.
def handle_dollar(dic, data):
    false_flag = dic
    while isinstance(find_dollar(false_flag), str):
        my_path = find_dollar(false_flag)
        dic_copy = false_flag.copy()
        false_flag = replace_dollar(my_path, dic_copy, data)
    false_flag = json.dumps(false_flag)
    return false_flag







