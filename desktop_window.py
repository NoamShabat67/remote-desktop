import mpv
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

from chat_window import ReceiverChatWindow
from key_map import key_map


class DesktopWindow(QMainWindow):
    def __init__(self, vid_soc_handler, io_soc_handler, peer_username):
        self.vid_soc_handler = vid_soc_handler
        self.io_soc_handler = io_soc_handler

        self.chat_window = ReceiverChatWindow(self.io_soc_handler, peer_username)

        # set up window
        super().__init__()
        self.setWindowTitle('AeroLink')
        self.resize(1280, 720)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stretch_widget = QWidget()
        layout.addWidget(self.stretch_widget)

        self.chat_window.receive_messages_thread.peer_disconnected_signal.connect(self.close)
        getattr(self.chat_window, 'disconnect_button').clicked.connect(self.button_disconnect)

        # set up mpv player
        self.player = mpv.MPV(wid=str(int(self.stretch_widget.winId())), input_default_bindings=True,
                              input_vo_keyboard=True)
        self.player._set_property('profile', 'low-latency')

        # receive video to mpv
        @self.player.python_stream('vid')
        def receive():
            while True:
                try:
                    data = self.vid_soc_handler.recv_decrypted()
                except ConnectionAbortedError:
                    break
                yield data
        self.player.play('python://vid')

        self.show()

    def button_disconnect(self):
        self.vid_soc_handler.soc.close()
        self.io_soc_handler.soc.close()
        self.chat_window.close()
        self.close()

    # capture keyboard presses
    def keyPressEvent(self, event):
        key = key_map.get(event.key())
        if key is None:
            key = event.text()
            if len(key) > 12:
                print('key too long')
                return
            print(event)
            self.io_soc_handler.send_encrypted(f'key {key}'.encode())
        else:
            self.io_soc_handler.send_encrypted(f'key {key}'.encode())

    # capture mouse presses and convert the cordinates to full screen
    def mousePressEvent(self, event):

        # check if the window is tall or wide to take into accout the black margin
        def convert_coordinates(x, y):

            # check window size
            size = self.size()
            width = size.width()
            height = size.height()

            if width / 16 > height / 9:  # wide screen
                y = y * 1080 / height
                proportional_width = height * 16 / 9
                black_margin = (width - proportional_width) / 2
                x = (x - black_margin) * 1920 / proportional_width
                return round(x), round(y)

            else:  # tall screen
                x = x * 1920 / width
                proportional_height = width * 9 / 16
                black_margin = (height - proportional_height) / 2
                y = (y - black_margin) * 1080 / proportional_height
                return round(x), round(y)

        # send button press data to peer
        btn_lst = [Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton]
        if event.button() in btn_lst:
            btn = btn_lst.index(event.button())
            x_coordinate, y_coordinate = convert_coordinates(event.pos().x(), event.pos().y())
            x_coordinate = str(x_coordinate).rjust(4, '0')
            y_coordinate = str(y_coordinate).rjust(4, '0')
            self.io_soc_handler.send_encrypted(f'btn {btn} {x_coordinate} {y_coordinate}'.encode())
