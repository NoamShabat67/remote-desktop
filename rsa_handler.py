from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
import hashlib
import os

BUF_SIZE = 1024


class RSAHandler:

    def __init__(self, soc):
        self.soc = soc
        self.aes_params = None

    def __get_cipher(self):
        return AES.new(self.aes_params[0], self.aes_params[1], self.aes_params[2])

    def save_aes_params(self, aes_key):
        key = hashlib.sha256(aes_key).digest()
        mode = AES.MODE_CBC
        iv = '0123456789ABCDEF'.encode()
        self.aes_params = (key, mode, iv)

    def server_key_swap(self):
        with open('private_key.pem') as f:
            private_key = RSA.importKey(f.read())
        public_key = private_key.publickey().export_key()
        self.soc.sendall(public_key)

        encrypted_aes_key = self.soc.recv(1024)
        rsa_cipher = PKCS1_OAEP.new(private_key)
        aes_key = rsa_cipher.decrypt(encrypted_aes_key)

        self.save_aes_params(aes_key)

    def client_key_swap(self):
        public_key = self.soc.recv(1024)
        key = RSA.importKey(public_key)

        aes_key = os.urandom(16)
        rsa_cipher = PKCS1_OAEP.new(key)
        encrypted_aes_key = rsa_cipher.encrypt(aes_key)
        self.soc.sendall(encrypted_aes_key)

        self.save_aes_params(aes_key)

    def recv_decrypted(self):
        data_len = int(self.soc.recv(10).decode())
        read = 0
        data = b''
        while data_len > read:
            if data_len - read > BUF_SIZE:
                data += self.soc.recv(BUF_SIZE)
                read += BUF_SIZE
            else:
                data += self.soc.recv(data_len - read)
                read += data_len - read

        aes_cipher = self.__get_cipher()
        data = aes_cipher.decrypt(data)
        pad_length = int(data[:2])
        data = data[2:-pad_length]

        return data

    def send_encrypted(self, data):
        pad_length = 16 - ((len(data) + 2) % 16)
        data = str(pad_length).zfill(2).encode() + data + pad_length * b'0'
        aes_cipher = self.__get_cipher()
        data = aes_cipher.encrypt(data)

        data_len = len(data)
        self.soc.send(str(data_len).rjust(10, '0').encode())
        sent = 0
        while data_len > sent:
            if data_len - sent >= BUF_SIZE:
                self.soc.send(data[sent:sent + BUF_SIZE])
                sent += BUF_SIZE
            else:
                self.soc.send(data[sent:])
                sent += data_len - sent
