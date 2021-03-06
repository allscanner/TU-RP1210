
#!/bin/env/python
# the cryptography module can be supplied by PGPy 
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric.padding import OAEP
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa as RSA
import cryptography.hazmat.primitives.serialization as serialization
from cryptography.hazmat.primitives.serialization import load_pem_public_key, load_pem_private_key, BestAvailableEncryption
import base64
import os

def make_key_pair(name="TURP1210",passwd=None):
    private_key = RSA.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend())
    if passwd is None:
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption())
    else:
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(bytes(passwd)))
    with open(name+"_PrivateKey.pem",'wb') as fp:
        fp.write(pem)

    public_key = private_key.public_key()
    pem_pub = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo)
    with open(name+"_PublicKey.pem",'wb') as fp:
        fp.write(pem_pub)
    
def load_public_key(keyfile):
    """
    Loads an SSH (PEM) public key from a the path.
    """
    try:
        with open(keyfile, 'rb') as f:
            keystring = f.read()
    except (FileNotFoundError, OSError):
        keystring = keyfile

    return load_pem_public_key(keystring, default_backend())

def load_private_key(keyfile, passwd=None):
    """
    Loads a private PEM key from a file. Can also use a password. 
    """
    try:
        with open(keyfile, 'rb') as f:
            keystring = f.read()
    except (FileNotFoundError, OSError):
        keystring = bytes(keyfile,'ascii')
    return load_pem_private_key(keystring, password=passwd, backend=default_backend())
    
        
def encrypt_bytes(data, keyfile):
    """
    Encrypt data using envelope encryption. 
    """
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data)
    padded_data += padder.finalize()

    iv = os.urandom(16)
    symkey = os.urandom(16)
    pubkey = load_public_key(keyfile)
    if not pubkey:
        print("Public Key Not Found.")
        return 
    cipher = Cipher(algorithms.AES(symkey), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data)
    encryptor.finalize()

    cryptkey = pubkey.encrypt(symkey, 
                    OAEP(mgf=asym_padding.MGF1(algorithm=SHA256()),
                                 algorithm=SHA256(),
                                 label=None))
    safecipher = base64.b64encode(ciphertext)
    safekey = base64.b64encode(cryptkey)
    safeiv = base64.b64encode(iv)
    package = {"key": safekey.decode('ascii'), "iv": safeiv.decode(
        'ascii'), "cipher": safecipher.decode('ascii')}   
    return package

def decrypt_bytes(package, keyfile):
    """
    decrypt data using envelope encryption. 
    """
    #unpack the dictionary
    safekey = package["key"].encode('ascii')
    safeiv = package["iv"].encode('ascii')
    safecipher = package["cipher"].encode('ascii')

    #decode the base64 encoded values
    ciphertext = base64.b64decode(safecipher)
    cryptkey = base64.b64decode(safekey)
    iv = base64.b64decode(safeiv)
    
    privkey = load_private_key(keyfile)
    if not privkey:
        print("Private Key Not Found")
        return 
    symkey = privkey.decrypt(cryptkey, 
                    OAEP(mgf=asym_padding.MGF1(algorithm=SHA256()),
                                 algorithm=SHA256(),
                                 label=None))
    cipher = Cipher(algorithms.AES(symkey), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext)
    decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data)
    data += unpadder.finalize()
    
    return data


if __name__ == '__main__':
    """
    A simple example case
    """
    make_key_pair("Example")
    data = b'This is a test message! Giddie up! \x00' + bytes([x for x in range(256)])
    package = encrypt_bytes(data,"Example_PublicKey.pem")
    print("The following is the data to be encrypted:")
    print(data)
    print("\nThe encrypted package is as follows:")
    print(package)
    new_data = decrypt_bytes(package,"Example_PrivateKey.pem")
    print("\nDecrypting the data gives back the original message:")
    print(new_data)
    print("\nEquality test results: {}".format(data==new_data))
    print("\nYou should keep your private key unique and secret.")