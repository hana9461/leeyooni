"""
WebSocket 라우터
"""
import json
import uuid
from typing import Optional
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.websocket.socket_manager import socket_manager
from src.api.auth import get_current_user
from src.db.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """토큰에서 사용자 정보 추출"""
    if not credentials:
        return None
    
    try:
        from jose import jwt
        from src.config import settings
        
        payload = jwt.decode(
            credentials.credentials, 
            settings.jwt_secret, 
            algorithms=[settings.jwt_algorithm]
        )
        user_id: int = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id and token_type == "access":
            return user_id
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
    
    return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """WebSocket 엔드포인트"""
    connection_id = str(uuid.uuid4())
    user_id = None
    
    try:
        # 토큰에서 사용자 ID 추출
        if token:
            try:
                from jose import jwt
                from src.config import settings
                
                payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
                user_id = payload.get("sub")
            except Exception as e:
                logger.error(f"Token validation failed: {e}")
        
        # WebSocket 연결 수립
        await socket_manager.connect(websocket, connection_id, user_id)
        
        logger.info("WebSocket connection established", 
                   connection_id=connection_id, 
                   user_id=user_id)
        
        # 메시지 처리 루프
        while True:
            try:
                # 클라이언트로부터 메시지 수신
                data = await websocket.receive_text()
                message = json.loads(data)
                
                await handle_websocket_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected", connection_id=connection_id)
                break
            except json.JSONDecodeError:
                await socket_manager.send_personal_message({
                    "type": "error",
                    "message": "Invalid JSON format"
                }, connection_id)
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")
                await socket_manager.send_personal_message({
                    "type": "error",
                    "message": "Internal server error"
                }, connection_id)
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        socket_manager.disconnect(connection_id)


async def handle_websocket_message(connection_id: str, message: dict):
    """WebSocket 메시지 처리"""
    try:
        message_type = message.get("type")
        data = message.get("data", {})
        
        if message_type == "subscribe_symbol":
            symbol = data.get("symbol")
            if symbol:
                socket_manager.subscribe_to_symbol(connection_id, symbol.upper())
                await socket_manager.send_personal_message({
                    "type": "subscription_confirmed",
                    "data": {"symbol": symbol.upper()}
                }, connection_id)
        
        elif message_type == "unsubscribe_symbol":
            symbol = data.get("symbol")
            if symbol:
                socket_manager.unsubscribe_from_symbol(connection_id, symbol.upper())
                await socket_manager.send_personal_message({
                    "type": "unsubscription_confirmed",
                    "data": {"symbol": symbol.upper()}
                }, connection_id)
        
        elif message_type == "subscribe_city_state":
            socket_manager.subscribe_to_city_state(connection_id)
            await socket_manager.send_personal_message({
                "type": "city_state_subscription_confirmed",
                "data": {}
            }, connection_id)
        
        elif message_type == "unsubscribe_city_state":
            socket_manager.unsubscribe_from_city_state(connection_id)
            await socket_manager.send_personal_message({
                "type": "city_state_unsubscription_confirmed",
                "data": {}
            }, connection_id)
        
        elif message_type == "ping":
            await socket_manager.send_personal_message({
                "type": "pong",
                "data": {"timestamp": data.get("timestamp")}
            }, connection_id)
        
        else:
            await socket_manager.send_personal_message({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }, connection_id)
    
    except Exception as e:
        logger.error(f"Message handling failed: {e}")
        await socket_manager.send_personal_message({
            "type": "error",
            "message": "Message processing failed"
        }, connection_id)


@router.get("/ws/stats")
async def get_websocket_stats():
    """WebSocket 통계 조회 (관리자용)"""
    return socket_manager.get_stats()
