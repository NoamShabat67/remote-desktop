from PyQt6.QtWidgets import *
from client_connect_window import ConnectWindow
from log_in_window import LogInWindow
from desktop_window import DesktopWindow
from chat_window import Sender


if __name__ == '__main__':
    app = QApplication([])
    app.setStyleSheet('QMainWindow {background-image: url(pic.jpg)}')
    log_in_window = LogInWindow()
    app.exec()

    if log_in_window.logged_in is True:
        connect_window = ConnectWindow(log_in_window.soc_handler, log_in_window.io_soc_handler, log_in_window.username)
        app.exec()

        if connect_window.sender_or_recevier == 'receiver':
            desktop_window = DesktopWindow(
                connect_window.soc_handler, connect_window.io_soc_handler, connect_window.peer_username
            )
            app.exec()
        if connect_window.sender_or_recevier == 'sender':
            sender = Sender(connect_window.soc_handler, connect_window.io_soc_handler, connect_window.peer_username)
            app.exec()
