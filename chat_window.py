from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6 import uic
import subprocess
import pyautogui


# general chat window that the receiver and sender subclasses inherit from
class ChatWindow(QMainWindow):
    def __init__(self, io_soc_handler, peer_username):
        self.io_soc_handler = io_soc_handler
        self.peer_username = peer_username
        print('peer: ' + peer_username)

        # set up window
        super().__init__()
        self.setWindowTitle('AeroLink')
        uic.loadUi('chat-window.ui', self)
        self.setFixedSize(800, 600)
        getattr(self, 'send_button').clicked.connect(self.send_message)
        getattr(self, 'message_field').returnPressed.connect(self.send_message)

    def add_message(self, message, user=None):
        user = self.peer_username if user is None else user
        print('adding message')
        text = getattr(self, 'chat_text_edit').toPlainText()
        getattr(self, 'chat_text_edit').setText(text + f'\n{user}: {message}')

        sb = getattr(self, 'chat_text_edit').verticalScrollBar()
        sb.setValue(sb.maximum())

    def send_message(self):
        message = getattr(self, 'message_field').text()
        self.io_soc_handler.send_encrypted(f'msg {message}'.encode())
        self.add_message(message, 'you')
        getattr(self, 'message_field').clear()
        print(f'sending message: {message}')


# chat window subclass for receiver
class ReceiverChatWindow(ChatWindow):
    def __init__(self, io_soc_handler, peer_username):
        super().__init__(io_soc_handler, peer_username)
        self.show()

        self.receive_messages_thread = self.ReceiveMessagesThread(self.io_soc_handler)
        self.receive_messages_thread.message_signal.connect(self.add_message)
        self.receive_messages_thread.peer_disconnected_signal.connect(self.close)
        self.receive_messages_thread.start()

    # thread that listens for messages and emit a signal for the messages to be added in the main thread
    class ReceiveMessagesThread(QThread):
        message_signal = pyqtSignal(str)
        peer_disconnected_signal = pyqtSignal()

        def __init__(self, io_soc_handler):
            super().__init__()
            self.io_soc_handler = io_soc_handler

        # listen for messages
        def run(self):
            while True:
                try:
                    data = self.io_soc_handler.recv_decrypted().decode()
                except ConnectionAbortedError:
                    break
                print(data)
                if data.startswith('msg'):
                    message = data[4:]
                    self.message_signal.emit(message)
                if data.startswith('disconnect'):
                    self.peer_disconnected_signal.emit()
                    break


# chat window subclass for sender
class Sender(ChatWindow):
    def __init__(self, vid_soc_handler, io_soc_handler, peer_username):
        super().__init__(io_soc_handler, peer_username)
        self.show()
        self.vid_soc_handler = vid_soc_handler

        self.io_thread = self.ReceiveIoThread(self.io_soc_handler)
        self.io_thread.message_signal.connect(self.add_message)
        self.io_thread.peer_disconnected_signal.connect(self.close_window)
        self.io_thread.start()
        self.ffmpeg_thread = self.StreamFfmpegThread(self.vid_soc_handler)
        self.ffmpeg_thread.start()

        getattr(self, 'disconnect_button').clicked.connect(self.close_window)

    def close_window(self):
        self.ffmpeg_thread.running = False
        self.ffmpeg_thread.ffmpeg_process.terminate()
        self.close()

    # thread that listen to the io socket
    class ReceiveIoThread(QThread):
        message_signal = pyqtSignal(str)
        peer_disconnected_signal = pyqtSignal()

        def __init__(self, io_soc_handler):
            super().__init__()
            self.io_soc_handler = io_soc_handler

        def run(self):
            while True:
                try:
                    data = self.io_soc_handler.recv_decrypted().decode()
                except ConnectionAbortedError:
                    print('a')
                    break
                print(data)

                # emit signal for message to be added in the main thread
                if data.startswith('msg'):
                    message = data[4:]
                    self.message_signal.emit(message)

                if data.startswith('disconnect'):
                    self.peer_disconnected_signal.emit()
                    break

                # simulate mouse and keyboard presses
                continue  # to prevent endless clicks when running localy
                if data.startswith('key'):
                    key = data[4:]
                    pyautogui.press(key)
                if data.startswith('btn'):
                    btn, x, y = [int(s) for s in data.split()[1:]]
                    pyautogui.moveTo(x, y)
                    pyautogui.mouseDown(button=['left', 'middle', 'right'][btn])
                    pyautogui.mouseUp()

    class StreamFfmpegThread(QThread):
        def __init__(self, vid_soc_handler):
            super().__init__()
            self.vid_soc_handler = vid_soc_handler
            self.ffmpeg_process = None
            self.running = True

        # capture the screen with ffmpeg and send it to peer
        def run(self):
            command = [
                'ffmpeg',
                '-f', 'gdigrab',
                '-framerate', '20',
                '-i', 'desktop',
                '-vcodec', 'mpeg4',
                '-q', '12',
                '-f', 'mpegts',
                '-'
            ]
            self.ffmpeg_process = subprocess.Popen(command, stdout=subprocess.PIPE)
            while self.running:
                ffmpeg_data = self.ffmpeg_process.stdout.read(4096)
                try:
                    self.vid_soc_handler.send_encrypted(ffmpeg_data)
                except Exception as e:
                    print(e)
                    break
