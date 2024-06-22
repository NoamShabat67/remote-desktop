from PyQt6.QtWidgets import *
from PyQt6 import uic
from PyQt6.QtCore import *
import socket

from rsa_handler import RSAHandler

HOST = 'localhost'
PORT = 36252
# HOST = '0.tcp.eu.ngrok.io'
# PORT = 18284


class LogInWindow(QMainWindow):
    def __init__(self):
        self.io_soc = None
        self.io_soc_handler = None
        self.username = None
        self.logged_in = False

        # set up window
        super().__init__()
        self.setWindowTitle('Log in - AeroLink')
        uic.loadUi('log-in-window.ui', self)
        self.setFixedSize(800, 600)

        self.hide_widgets()
        self.show()

        # set up the server listen thread
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc_handler = RSAHandler(self.soc)
        self.server_listen_thread = self.ServerListenThread(self.soc_handler)
        self.server_listen_thread.connected_signal.connect(self.show_widgets)
        self.server_listen_thread.duplicate_signal.connect(self.error_duplicate_user)
        self.server_listen_thread.wrong_signal.connect(self.error_wrong_user)
        self.server_listen_thread.already_connected_signal.connect(self.error_already_connected)
        self.server_listen_thread.logged_in_signal.connect(self.connect_io_soc_and_close)
        self.server_listen_thread.start()

        # connect signals and buttons to functions
        getattr(self, 'log_in_button').clicked.connect(self.log_in)
        getattr(self, 'sign_up_button').clicked.connect(self.sign_up)
        for field in ['log_in_username_field', 'log_in_password_field']:
            getattr(self, field).returnPressed.connect(self.log_in)
        for field in ['sign_up_email_field', 'sign_up_username_field', 'sign_up_password_field']:
            getattr(self, field).returnPressed.connect(self.sign_up)

    class ServerListenThread(QThread):
        connected_signal = pyqtSignal()
        duplicate_signal = pyqtSignal()
        wrong_signal = pyqtSignal()
        already_connected_signal = pyqtSignal()
        logged_in_signal = pyqtSignal(str)

        def __init__(self, soc_handler):
            super().__init__()
            self.soc_handler = soc_handler

        def run(self):

            # connect to server
            while True:
                try:
                    self.soc_handler.soc.connect((HOST, PORT))
                    self.soc_handler.client_key_swap()
                    self.soc_handler.send_encrypted(b'new')
                except ConnectionError:
                    continue
                break
            self.connected_signal.emit()

            # listen to log in and sign up responses
            while True:
                data = self.soc_handler.recv_decrypted().decode()
                print(data)
                if data == 'duplicate':
                    self.duplicate_signal.emit()
                if data == 'wrong':
                    self.wrong_signal.emit()
                if data == 'already':
                    self.already_connected_signal.emit()
                if data.startswith('connected'):
                    name = data[10:]
                    self.logged_in_signal.emit(name)
                    break

    def show_widgets(self):
        for widget in getattr(self, 'centralwidget').findChildren(QWidget):
            widget.show()
        getattr(self, 'connecting_to_server_label').hide()

    def hide_widgets(self):
        for widget in getattr(self, 'centralwidget').findChildren(QWidget):
            widget.hide()
        getattr(self, 'connecting_to_server_label').show()

    # send log in request to server
    def log_in(self):
        username_value = getattr(self, 'log_in_username_field').text()
        password_value = getattr(self, 'log_in_password_field').text()

        if len(username_value) > 20 or len(password_value) > 20 or len(username_value) < 4 or len(password_value) < 6\
                or ' ' in username_value or ' ' in password_value:
            getattr(self, 'log_in_error_label').setText('Incorrect username or password')
            return

        self.soc_handler.send_encrypted(f'login {username_value} {password_value}'.encode())

    def error_duplicate_user(self):
        getattr(self, 'sign_up_error_label').setText('User with this email or password already exsists')

    def error_wrong_user(self):
        getattr(self, 'log_in_error_label').setText('Incorrect username or password')

    def error_already_connected(self):
        getattr(self, 'log_in_error_label').setText('You are already connected on another computer')

    # send sign up request to server
    def sign_up(self):
        email_value = getattr(self, 'sign_up_email_field').text()
        username_value = getattr(self, 'sign_up_username_field').text()
        password_value = getattr(self, 'sign_up_password_field').text()

        sign_up_error_label = getattr(self, 'sign_up_error_label')
        if '@' not in email_value or len(email_value) < 3 or ' ' in email_value:
            sign_up_error_label.setText('Invalid email')
        elif ' ' in username_value or ' ' in password_value:
            sign_up_error_label.setText("Username and password can't have spaces in them")
        elif len(username_value) < 4:
            sign_up_error_label.setText('Username must be 4 characters or more')
        elif len(password_value) < 6:
            sign_up_error_label.setText('Password must be 6 characters or more')
        elif len(username_value) > 20:
            sign_up_error_label.setText('Username must be 20 characters or less')
        elif len(password_value) > 20:
            sign_up_error_label.setText('Password must be 20 characters or less')
        elif len(email_value) > 50:
            sign_up_error_label.setText('email must be 50 characters or less')
        else:
            self.soc_handler.send_encrypted(f'signup {email_value} {username_value} {password_value}'.encode())

    def connect_io_soc_and_close(self, name):

        # connect IO socket
        self.io_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.io_soc.connect((HOST, PORT))

        self.io_soc_handler = RSAHandler(self.io_soc)
        self.io_soc_handler.client_key_swap()

        self.io_soc_handler.send_encrypted(name.encode())

        self.username = name
        self.logged_in = True
        self.close()
