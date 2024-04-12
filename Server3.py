import socket
import threading
import json
from Server_util import *
server_add = input('server IP: ')
port = input("Port: ")
port = int(port)
dic = {}
subscriptions = {}
client_handlers = {}
dic_lock = threading.Lock()
client_handler_lock = threading.Lock()
subscription_lock = threading.Lock()

class ClientHandler(threading.Thread):
    def __init__(self, client_sock, client_address):
        super().__init__()
        self.client_sock = client_sock
        self.client_address = client_address
        self.subscribed_resources = []
        self.send_update_trigger = False
        self.update_message_instance = {}
        self.client_id = ""
        self.resource_to_subscribe_to = None
        self.subscription_update_requested = False

    def run(self):
        print("Accepted connection from {}".format(self.client_address))
        try:
            self.client_id = self.client_sock.recv(1024).decode()
            print("Received client ID: {} from {}".format(self.client_id, self.client_address))
            self.send_response("Received client ID")
            
            data = self.client_sock.recv(1024).decode('utf-8')
            if data:
                self.process_request(data)
            # After processing the initial request, the thread will exit if not subscribed to "wrdo"

        except Exception as e:
            print("Error with client {}: {}".format(self.client_address, e))
        finally:
            self.unsubscribe_all()  # Clean up subscriptions
            self.client_sock.close()
            print("Connection closed for {}".format(self.client_address))

    def process_request(self, data):
        
        print("Received: {}".format(data))
        
        if not validate_json(data):
            self.send_response("request not a JSON")
            return
        data = json.loads(data)
        
        if data["operation"] == "POST":
            self.handle_post(data)
            
        elif data["operation"] == "GET":
            self.handle_get(data)

    def handle_post(self, data): # we do not handle post with $ and we need to 
        with dic_lock:
            dic_copy = dic.copy()
            dic_original = dic.copy()
            
        data_copy2 = deepcopy(data)
        data_copy2, validate = handle_dollar(data_copy2["data"], data_copy2["rsrcid"], server_add, port)
        
        if not validate:
            data_copy2_json = json.dumps(data_copy2)
            self.send_response("Invalid references in data" + data_copy2_json)
            return
            
        if data["rsrcid"] in dic_copy:
            dic_copy[data["rsrcid"]] = data["data"]
            message_status = "Resource Modified"
            code = "211"
        else:
            dic_copy[data["rsrcid"]] = data["data"]
            message_status = "Resource Created"
            code = "201"
        
        with dic_lock:       
            dic[data["rsrcid"]] = data["data"]
            
        message = {
            "server": server_add,
            "code": code,
            "rsrc": data["rsrcid"],
            "message": message_status
        }
        message_json = json.dumps(message)
        
        self.send_response(message_json)
        
        json_string, validate = handle_dollar(dic_copy[data["rsrcid"]], data["rsrcid"], server_add, port)
        update_message = {
            "server": server_add,
            "code": "210",
            "rsrc": data["rsrcid"],
            "data": json_string,
            "message": message_status
        }
        update_message_json = json.dumps(update_message)
        notify_subscribers(data["rsrcid"], update_message_json)

    def handle_get(self, data):
        print("data: ", data)
        with dic_lock:
            dic_copy = dic.copy()
            
        resource_exists = data["rsrcid"] in dic_copy
        if resource_exists:
            json_string, validate = handle_dollar(dic_copy[data["rsrcid"]], data["rsrcid"], server_add, port)
            message = {
                "server": server_add,
                "code": "202" if data["protocol"] == "rdo" else "210",
                "rsrc": data["rsrcid"],
                "data": json_string,
                "message": ""
            }
        else:
             message = {
                "server": server_add,
                "code": "404",
                "rsrc": data["rsrcid"],
                "data": "",
                "message": "ressource inconnue"
             }
        message_json = json.dumps(message)
        
        with dic_lock:    
            if (data["rsrcid"] in dic and dic_copy[data["rsrcid"]] == dic[data["rsrcid"]]) or data["rsrcid"] not in dic:
                data_has_changed = False
            else:
                data_has_changed = True
                
        if data_has_changed:
            self.handle_get(data)
        else:            
            self.send_response(message_json)

            if resource_exists and data["protocol"] == "wrdo":
                self.subscribe_to_resource(data["rsrcid"]) # Missing we dont handle if we already looking at resource
    
    def subscribe_to_resource(self, resource_id):
        with client_handler_lock:
            existing_handler = client_handlers.get(self.client_id)
            call_wait = False
            
            if existing_handler:
                existing_handler.resource_to_subscribe_to = resource_id
                existing_handler.subscription_update_requested = True
            else:

                client_handlers[self.client_id] = self
                with subscription_lock:
                    if resource_id not in subscriptions:
                        subscriptions[resource_id] = []
                    if self not in subscriptions[resource_id]:
                        subscriptions[resource_id].append(self)

                self.subscribed_resources.append(resource_id)
                call_wait = True
                print("Client {} subscribed to {}".format(self.client_id, resource_id))
        
        if call_wait:
            self.wait_for_updates()
    
    def add_subscriptions(self, resource_id):
        with subscription_lock:
            if resource_id not in subscriptions:
                subscriptions[resource_id] = []
            if self not in subscriptions[resource_id]:
                subscriptions[resource_id].append(self)        
    
    def wait_for_updates(self):
        try:
            while True:
                if self.send_update_trigger:
                    self.send_update(self.update_message_instance)
                    self.send_update_trigger = False
                    
                if self.subscription_update_requested:
                    if self.resource_to_subscribe_to not in self.subscribed_resources:
                        self.subscribed_resources.append(self.resource_to_subscribe_to)
                        self.subscription_update_requested = False
                        self.add_subscriptions(self.resource_to_subscribe_to)
                               
        except Exception as e:
            print("Error while waiting for updates: {}".format(e))
        finally:
            self.unsubscribe_all()

    def unsubscribe_all(self):
        for resource_id in self.subscribed_resources:
            if resource_id in subscriptions:
                subscriptions[resource_id].remove(self)

    def send_update(self, update_message):
        self.send_response(update_message)

    def send_response(self, message):
        try:
            self.client_sock.sendall(message.encode())
        except Exception as e:
            print("Error sending response to {}: {}".format(self.client_address, e))
    
def notify_subscribers(resource_id, update_message):
    if resource_id in subscriptions:
        for client_handler in subscriptions[resource_id]:
            client_handler.update_message_instance = update_message
            client_handler.send_update_trigger = True
        
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((server_add, port))
server_socket.listen(5)

while True:
    client_socket, address = server_socket.accept()
    client_handler = ClientHandler(client_socket, address)
    client_handler.start()
