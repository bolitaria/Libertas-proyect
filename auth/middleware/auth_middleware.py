"""
Middleware de autenticación para FastAPI.
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import redis
from ..models.user import AuthUtils, TokenData, UserRole

class JWTBearer(HTTPBearer):
    """Bearer token authentication"""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.redis_client = None
    
    async def __call__(self, request: Request) -> Optional[TokenData]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if credentials:
            if credentials.scheme != "Bearer":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid authentication scheme."
                )
            
            token_data = self.verify_jwt(credentials.credentials)
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid token or expired token."
                )
            
            # Verificar si el token está en la blacklist
            if await self.is_token_revoked(credentials.credentials):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token has been revoked."
                )
            
            return token_data
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authorization code."
            )
    
    def verify_jwt(self, jwtoken: str) -> Optional[TokenData]:
        """Verificar token JWT"""
        try:
            payload = AuthUtils.verify_token(jwtoken)
            if payload:
                return TokenData(
                    username=payload.get("sub"),
                    user_id=payload.get("user_id"),
                    role=payload.get("role")
                )
        except Exception:
            return None
        return None
    
    async def is_token_revoked(self, token: str) -> bool:
        """Verificar si el token está revocado"""
        if not self.redis_client:
            # Conectar a Redis
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
            self.redis_client = redis.from_url(redis_url)
        
        try:
            token_hash = AuthUtils.get_password_hash(token)
            return self.redis_client.sismember('auth:revoked_tokens', token_hash)
        except:
            return False

def require_role(required_role: UserRole):
    """Decorador para requerir rol específico"""
    def role_checker(token_data: TokenData = None):
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Mapear jerarquía de roles
        role_hierarchy = {
            UserRole.VIEWER: 0,
            UserRole.RESEARCHER: 1,
            UserRole.CONTRIBUTOR: 2,
            UserRole.MODERATOR: 3,
            UserRole.ADMIN: 4
        }
        
        user_role_level = role_hierarchy.get(token_data.role, -1)
        required_role_level = role_hierarchy.get(required_role, 0)
        
        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        
        return token_data
    
    return role_checker

# Instancias globales
security = JWTBearer()

# Decoradores predefinidos
require_viewer = require_role(UserRole.VIEWER)
require_researcher = require_role(UserRole.RESEARCHER)
require_contributor = require_role(UserRole.CONTRIBUTOR)
require_moderator = require_role(UserRole.MODERATOR)
require_admin = require_role(UserRole.ADMIN)