"""
Cifrado de extremo a extremo para documentos.
"""
import base64
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives import serialization
import os
import secrets

class E2EEncryption:
    """Cifrado de extremo a extremo"""
    
    def __init__(self, master_key: Optional[str] = None):
        """Inicializar con clave maestra"""
        self.master_key = master_key or os.getenv("ENCRYPTION_MASTER_KEY")
        
        if not self.master_key:
            raise ValueError("ENCRYPTION_MASTER_KEY no configurada")
        
        # Derivar clave de cifrado de archivos
        self.file_key = self.derive_key(self.master_key, b"file_encryption")
    
    @staticmethod
    def generate_master_key() -> str:
        """Generar nueva clave maestra"""
        return base64.b64encode(secrets.token_bytes(32)).decode()
    
    @staticmethod
    def derive_key(master_key: str, salt: bytes, length: int = 32) -> bytes:
        """Derivar clave desde clave maestra"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(master_key.encode())
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Cifrar archivo"""
        # Leer archivo
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        
        # Generar IV aleatorio
        iv = os.urandom(16)
        
        # Configurar cifrado AES
        cipher = Cipher(
            algorithms.AES(self.file_key),
            modes.CBC(iv)
        )
        
        # Añadir padding
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()
        
        # Cifrar
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Guardar archivo cifrado
        if not output_path:
            output_path = file_path + '.enc'
        
        with open(output_path, 'wb') as f:
            f.write(iv + ciphertext)
        
        # Metadatos de cifrado
        metadata = {
            'original_file': file_path,
            'encrypted_file': output_path,
            'algorithm': 'AES-256-CBC',
            'iv': base64.b64encode(iv).decode(),
            'key_derivation': 'PBKDF2-SHA256',
            'original_size': len(plaintext),
            'encrypted_size': len(ciphertext) + len(iv)
        }
        
        # Guardar metadatos
        metadata_file = output_path + '.meta'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata
    
    def decrypt_file(self, encrypted_path: str, output_path: Optional[str] = None) -> bytes:
        """Descifrar archivo"""
        # Leer archivo cifrado
        with open(encrypted_path, 'rb') as f:
            data = f.read()
        
        # Extraer IV y ciphertext
        iv = data[:16]
        ciphertext = data[16:]
        
        # Configurar descifrado AES
        cipher = Cipher(
            algorithms.AES(self.file_key),
            modes.CBC(iv)
        )
        
        # Descifrar
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Quitar padding
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        # Guardar archivo descifrado
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(plaintext)
        
        return plaintext
    
    def encrypt_metadata(self, metadata: Dict[str, Any], public_key_pem: str) -> str:
        """Cifrar metadatos con clave pública"""
        # Cargar clave pública
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode()
        )
        
        # Convertir metadatos a JSON
        metadata_json = json.dumps(metadata)
        
        # Cifrar con RSA-OAEP
        ciphertext = public_key.encrypt(
            metadata_json.encode(),
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return base64.b64encode(ciphertext).decode()
    
    def decrypt_metadata(self, encrypted_metadata: str, private_key_pem: str) -> Dict[str, Any]:
        """Descifrar metadatos con clave privada"""
        # Cargar clave privada
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None
        )
        
        # Decodificar ciphertext
        ciphertext = base64.b64decode(encrypted_metadata)
        
        # Descifrar con RSA-OAEP
        plaintext = private_key.decrypt(
            ciphertext,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return json.loads(plaintext.decode())

class DocumentEncryption:
    """Cifrado específico para documentos"""
    
    def __init__(self, e2e_encryption: E2EEncryption):
        self.e2e = e2e_encryption
    
    def encrypt_document(self, document_path: str, recipients: list) -> Dict[str, Any]:
        """Cifrar documento para múltiples receptores"""
        # Cifrar archivo
        encryption_result = self.e2e.encrypt_file(document_path)
        
        # Metadatos del documento
        document_metadata = {
            'title': os.path.basename(document_path),
            'encryption_info': encryption_result,
            'recipients': recipients,
            'timestamp': os.path.getmtime(document_path)
        }
        
        # Para cada receptor, cifrar metadatos con su clave pública
        encrypted_metadata = {}
        for recipient in recipients:
            if 'public_key' in recipient:
                encrypted_metadata[recipient['id']] = self.e2e.encrypt_metadata(
                    document_metadata,
                    recipient['public_key']
                )
        
        return {
            'encrypted_file': encryption_result['encrypted_file'],
            'encrypted_metadata': encrypted_metadata,
            'document_metadata': document_metadata
        }
    
    def share_document(self, document_path: str, recipient_public_key: str) -> Dict[str, str]:
        """Compartir documento cifrado"""
        # Generar clave de sesión única para este documento
        session_key = secrets.token_bytes(32)
        
        # Cifrar documento con clave de sesión
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(session_key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        
        with open(document_path, 'rb') as f:
            plaintext = f.read()
        
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # Cifrar clave de sesión con clave pública del receptor
        public_key = serialization.load_pem_public_key(
            recipient_public_key.encode()
        )
        
        encrypted_session_key = public_key.encrypt(
            session_key,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Crear paquete de datos
        package = {
            'iv': base64.b64encode(iv).decode(),
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'encrypted_session_key': base64.b64encode(encrypted_session_key).decode(),
            'tag': base64.b64encode(encryptor.tag).decode(),
            'original_filename': os.path.basename(document_path)
        }
        
        return package