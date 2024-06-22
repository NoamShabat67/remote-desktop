import socket
import threading
import sqlite3

from rsa_handler import RSAHandler

HOST = 'localhost'
PORT = 36252
clients_by_name = {}  # {username: vid_soc, io_soc, peer}
client_list_lock = threading.Lock()
new_io_clinet_event = threading.Event()
connection_event = threading.Event()


def handler(client_soc: socket.socket):

    client_soc_handler = RSAHandler(client_soc)
    client_soc_handler.server_key_swap()

    # recv first message to check if the socket is a new client or an IO socket
    try:
        data = client_soc_handler.recv_decrypted().decode()
    except ConnectionError:
        print('client disconnected')
        return

    if data == 'new':

        main_soc_handler(client_soc_handler)

    # IO socket
    else:
        io_soc_handler(client_soc_handler, data)


def main_soc_handler(client_soc_handler):

    # listen for log in and sign up requests
    while True:
        try:
            data = client_soc_handler.recv_decrypted().decode()
        except ConnectionError:
            print('client disconnected')
            return

        if data.startswith('login'):
            _, username_value, password_value = data.split()

            if username_value in clients_by_name:
                client_soc_handler.send_encrypted(b'already')
            else:
                db_conn = sqlite3.connect('database.db')
                db_cursor = db_conn.cursor()
                db_cursor.execute('SELECT * FROM users WHERE username=? AND password=?',
                                  (username_value, password_value))
                log_in_result = db_cursor.fetchone()
                if log_in_result:
                    db_conn.close()
                    break
                else:
                    client_soc_handler.send_encrypted(b'wrong')

        if data.startswith('signup'):
            _, email_value, username_value, password_value = data.split()

            db_conn = sqlite3.connect('database.db')
            db_cursor = db_conn.cursor()
            try:
                db_cursor.execute('''INSERT INTO users (email, username, password) VALUES (?, ?, ?)''',
                                  (email_value, username_value, password_value))
                db_conn.commit()
                db_conn.close()
                break
            except sqlite3.IntegrityError:
                print('integrity error')
                client_soc_handler.send_encrypted(b'duplicate')
                db_conn.close()

    # add logged in client to clients dict
    client_username = username_value
    with client_list_lock:
        clients_by_name[client_username] = [client_soc_handler, None, None]
    client_soc_handler.send_encrypted(f'connected {client_username}'.encode())

    # wait for the client's IO socket
    while True:
        new_io_clinet_event.wait()
        new_io_clinet_event.clear()
        with client_list_lock:
            if clients_by_name[client_username][1] is not None:
                break

    # listen for requests and accepts
    while True:
        try:
            data = client_soc_handler.recv_decrypted().decode()
        except ConnectionError:
            with client_list_lock:
                clients_by_name.pop(client_username)
            print(f'client {client_username} disconnected')
            return

        print(f'{client_username}: {data}')
        if data.startswith('req'):
            peer_name = data[4:]
            peer_socs = clients_by_name.get(peer_name)
            if peer_socs is None:
                client_soc_handler.send_encrypted(f'nouser {peer_name}'.encode())
                continue
            if peer_socs[2] is not None:
                client_soc_handler.send_encrypted(f'occup {peer_name}'.encode())
                continue
            peer_socs = clients_by_name[peer_name]
            peer_socs[0].send_encrypted(f'req {client_username}'.encode())
        if data.startswith('acc'):
            peer_name = data[4:]
            if clients_by_name[peer_name][2] is not None:
                client_soc_handler.send_encrypted(f'occup {peer_name}'.encode())
                continue
            client_soc_handler.send_encrypted(f'start {peer_name}'.encode())
            with client_list_lock:
                clients_by_name[client_username][2] = peer_name
                clients_by_name[peer_name][2] = client_username
            peer_socs = clients_by_name[peer_name]
            peer_socs[0].send_encrypted(f'acc {client_username}'.encode())
            connection_event.set()
            break
        if data.startswith('rly'):
            peer_name = data[4:]
            peer_socs = clients_by_name[peer_name]
            while True:
                try:
                    data = peer_socs[0].recv_decrypted()
                    print(data)
                except ConnectionError:
                    print(f'client {peer_name} video socket disconnected')
                    clients_by_name.pop(peer_name)
                    break
                try:
                    client_soc_handler.send_encrypted(data)
                except ConnectionError:
                    print(f'client {client_username} video socket disconnected')
                    clients_by_name.pop(client_username)
                    break
            break


def io_soc_handler(client_soc_handler, client_username):

    with client_list_lock:
        clients_by_name[client_username][1] = client_soc_handler
    new_io_clinet_event.set()

    while True:
        connection_event.wait()
        connection_event.clear()
        if clients_by_name[client_username][2] is not None:
            peer_username = clients_by_name[client_username][2]
            peer_io_soc = clients_by_name[peer_username][1]
            break

    while True:
        try:
            data = client_soc_handler.recv_decrypted()
        except ConnectionError:
            print(f'client {client_username} IO socket disconnected')
            if clients_by_name.get(peer_username):
                peer_io_soc.send_encrypted(b'disconnect')
                clients_by_name.pop(peer_username)
            break
        peer_io_soc.send_encrypted(data)


if __name__ == '__main__':
    server_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_soc.bind((HOST, PORT))
    server_soc.listen()

    while True:
        while threading.active_count() > 100:
            pass
        new_client_soc, _ = server_soc.accept()
        print('new socket')
        threading.Thread(target=handler, args=[new_client_soc]).start()
