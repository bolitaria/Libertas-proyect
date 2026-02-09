"""
Modelos de usuario y autenticación.
"""
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr
from enum import Enum
import jwt
from passlib.context import CryptContext
import secrets

# Contexto para hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRole(str, Enum):
    """Roles de usuario"""
    VIEWER = "viewer"
    RESEARCHER = "researcher"
    CONTRIBUTOR = "contributor"
    MODERATOR = "moderator"
    ADMIN = "admin"

class UserBase(BaseModel):
    """Base de usuario"""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.VIEWER

class UserCreate(UserBase):
    """Creación de usuario"""
    password: str

class UserInDB(UserBase):
    """Usuario en base de datos"""
    id: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    is_verified: bool = False
    public_key: Optional[str] = None
    
    class Config:
        from_attributes = True

class UserPublic(UserBase):
    """Usuario público (sin datos sensibles)"""
    id: str
    created_at: datetime
    is_active: bool
    is_verified: bool

class Token(BaseModel):
    """Token de autenticación"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None

class TokenData(BaseModel):
    """Datos del token"""
    username: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[UserRole] = None

class AuthConfig:
    """Configuración de autenticación"""
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    @classmethod
    def get_secret_key(cls):
        """Obtener clave secreta desde variables de entorno"""
        import os
        return os.getenv("JWT_SECRET", cls.SECRET_KEY)

class AuthUtils:
    """Utilidades de autenticación"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verificar contraseña"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Obtener hash de contraseña"""
        return pwd_context.hash(password)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generar API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crear token de acceso JWT"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, 
            AuthConfig.get_secret_key(), 
            algorithm=AuthConfig.ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Crear token de refresco"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=AuthConfig.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(
            to_encode,
            AuthConfig.get_secret_key(),
            algorithm=AuthConfig.ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verificar token JWT"""
        try:
            payload = jwt.decode(
                token,
                AuthConfig.get_secret_key(),
                algorithms=[AuthConfig.ALGORITHM]
            )
            return payload
        except jwt.PyJWTError:
            return None
    
    @staticmethod
    def generate_key_pair():
        """Generar par de claves para cifrado E2E"""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        
        # Generar clave privada
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Obtener clave pública
        public_key = private_key.public_key()
        
        # Serializar
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        return {
            'private_key': private_pem.decode(),
            'public_key': public_pem.decode()
        }