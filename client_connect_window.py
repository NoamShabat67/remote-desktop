from PyQt6.QtWidgets import *
from PyQt6 import uic
from PyQt6.QtCore import *


class ConnectWindow(QMainWindow):
    def __init__(self, soc_handler, io_soc_handler, username):
        self.soc_handler = soc_handler
        self.io_soc_handler = io_soc_handler
        self.username = username

        self.io_switch = True
        self.sender = None
        self.peer_username = None
        self.sender_or_recevier = None

        # set up window
        super().__init__(None)
        self.setWindowTitle('Connect - AeroLink')
        uic.loadUi('connect_window.ui', self)
        self.setFixedSize(800, 600)
        getattr(self, 'name_label').setText(f'Hello {self.username}')
        getattr(self, 'accept_button').hide()
        self.show()

        # connect signals and buttons to functions
        self.server_listen_thread = self.ServerListenThread(self.soc_handler)
        self.server_listen_thread.request_signal.connect(self.show_request)
        self.server_listen_thread.stream_signal.connect(self.start_sender)
        self.server_listen_thread.receive_signal.connect(self.open_desktop_window)
        self.server_listen_thread.no_user_signal.connect(self.error_no_user)
        self.server_listen_thread.occupied_signal.connect(self.error_occupied)
        self.server_listen_thread.start()
        getattr(self, 'connect_button').clicked.connect(self.connect_to_peer)
        getattr(self, 'accept_button').clicked.connect(self.accept_peer)
        getattr(self, 'name_field').returnPressed.connect(self.connect_to_peer)

    def error_occupied(self, name):
        getattr(self, 'accept_button').hide()
        getattr(self, 'error_label').setText(f'{name} is connected to someone else')

    def connect_to_peer(self):
        getattr(self, 'error_label').setText('')
        self.soc_handler.send_encrypted(f'req {getattr(self, "name_field").text()}'.encode())

    def show_request(self, name):
        getattr(self, 'accept_button').setText(f'Accept {name}')
        getattr(self, 'accept_button').show()

    def accept_peer(self):
        _, name = getattr(self, 'accept_button').text().split()
        self.soc_handler.send_encrypted(f'acc {name}'.encode())

    def error_no_user(self, name):
        getattr(self, 'error_label').setText(f'No user online with the name: {name}')

    def start_sender(self, peer_username):
        self.peer_username = peer_username
        self.sender_or_recevier = 'sender'
        self.close()

    def open_desktop_window(self, peer_username):
        self.peer_username = peer_username
        self.sender_or_recevier = 'receiver'
        self.close()

    class ServerListenThread(QThread):
        request_signal = pyqtSignal(str)
        stream_signal = pyqtSignal(str)
        receive_signal = pyqtSignal(str)
        no_user_signal = pyqtSignal(str)
        occupied_signal = pyqtSignal(str)

        def __init__(self, soc_handler):
            super().__init__()
            self.soc_handler = soc_handler

        # listen to the server for requests, accepts etc
        def run(self):
            while True:
                data = self.soc_handler.recv_decrypted().decode()
                if data.startswith('req'):  # request
                    name = data[4:]
                    self.request_signal.emit(name)
                if data.startswith('acc'):  # accept
                    name = data[4:]
                    self.soc_handler.send_encrypted(f'rly {name}'.encode())
                    self.receive_signal.emit(name)
                    break
                if data.startswith('nouser'):  # requested user doesn't exist
                    name = data[7:]
                    self.no_user_signal.emit(name)
                if data.startswith('start'):  # connected, start streaming
                    name = data[6:]
                    self.stream_signal.emit(name)
                if data.startswith('occup'):  # user is already connected to someone else
                    name = data[6:]
                    self.occupied_signal.emit(name)
