"""
WebSocket 연결 관리자
"""
import structlog
from typing import Dict, Set, Any
from fastapi import WebSocket
import json

logger = structlog.get_logger(__name__)


class SocketManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[int, Set[str]] = {}  # user_id -> connection_ids
        self.connection_users: Dict[str, int] = {}  # connection_id -> user_id
        self.subscribed_symbols: Dict[str, Set[str]] = {}  # symbol -> connection_ids
        self.symbol_subscribers: Dict[str, Set[str]] = {}  # connection_id -> symbols
        self.city_state_subscribers: Set[str] = set()
        
        self.logger = logger.bind(service="websocket")
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: int = None):
        """WebSocket 연결 수립"""
        await websocket.accept()
        
        self.active_connections[connection_id] = websocket
        
        if user_id:
            self.connection_users[connection_id] = user_id
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        self.logger.info("WebSocket connected", 
                        connection_id=connection_id, 
                        user_id=user_id,
                        total_connections=len(self.active_connections))
    
    def disconnect(self, connection_id: str):
        """WebSocket 연결 해제"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        # 사용자 연결 정리
        if connection_id in self.connection_users:
            user_id = self.connection_users[connection_id]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            del self.connection_users[connection_id]
        
        # 심볼 구독 정리
        if connection_id in self.symbol_subscribers:
            symbols = self.symbol_subscribers[connection_id].copy()
            for symbol in symbols:
                self.unsubscribe_from_symbol(connection_id, symbol)
            del self.symbol_subscribers[connection_id]
        
        # 도시 상태 구독 정리
        self.city_state_subscribers.discard(connection_id)
        
        self.logger.info("WebSocket disconnected", 
                        connection_id=connection_id,
                        total_connections=len(self.active_connections))
    
    async def send_personal_message(self, message: dict, connection_id: str):
        """개인 메시지 전송"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(json.dumps(message))
                return True
            except Exception as e:
                self.logger.error(f"Failed to send personal message: {e}")
                self.disconnect(connection_id)
                return False
        return False
    
    async def send_to_user(self, message: dict, user_id: int):
        """특정 사용자에게 메시지 전송"""
        if user_id in self.user_connections:
            sent_count = 0
            for connection_id in self.user_connections[user_id].copy():
                if await self.send_personal_message(message, connection_id):
                    sent_count += 1
            return sent_count
        return 0
    
    async def broadcast_signal(self, signal_data: dict, symbol: str = None):
        """신호 브로드캐스트"""
        message = {
            "type": "new_signal",
            "data": signal_data,
            "timestamp": signal_data.get("ts")
        }
        
        sent_count = 0
        
        if symbol and symbol in self.subscribed_symbols:
            # 특정 심볼 구독자에게만 전송
            for connection_id in self.subscribed_symbols[symbol].copy():
                if await self.send_personal_message(message, connection_id):
                    sent_count += 1
        else:
            # 모든 연결에 브로드캐스트
            for connection_id in list(self.active_connections.keys()):
                if await self.send_personal_message(message, connection_id):
                    sent_count += 1
        
        self.logger.info("Signal broadcasted", 
                        symbol=symbol,
                        sent_count=sent_count,
                        total_subscribers=len(self.subscribed_symbols.get(symbol, [])))
    
    async def broadcast_city_state(self, city_state: dict):
        """도시 상태 브로드캐스트"""
        message = {
            "type": "city_state_update",
            "data": city_state,
            "timestamp": city_state.get("timestamp")
        }
        
        sent_count = 0
        for connection_id in self.city_state_subscribers.copy():
            if await self.send_personal_message(message, connection_id):
                sent_count += 1
        
        self.logger.info("City state broadcasted", 
                        sent_count=sent_count,
                        total_subscribers=len(self.city_state_subscribers))
    
    def subscribe_to_symbol(self, connection_id: str, symbol: str):
        """심볼 구독"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols[symbol] = set()
        
        self.subscribed_symbols[symbol].add(connection_id)
        
        if connection_id not in self.symbol_subscribers:
            self.symbol_subscribers[connection_id] = set()
        self.symbol_subscribers[connection_id].add(symbol)
        
        self.logger.info("Subscribed to symbol", 
                        connection_id=connection_id, 
                        symbol=symbol)
    
    def unsubscribe_from_symbol(self, connection_id: str, symbol: str):
        """심볼 구독 해제"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols[symbol].discard(connection_id)
            if not self.subscribed_symbols[symbol]:
                del self.subscribed_symbols[symbol]
        
        if connection_id in self.symbol_subscribers:
            self.symbol_subscribers[connection_id].discard(symbol)
        
        self.logger.info("Unsubscribed from symbol", 
                        connection_id=connection_id, 
                        symbol=symbol)
    
    def subscribe_to_city_state(self, connection_id: str):
        """도시 상태 구독"""
        self.city_state_subscribers.add(connection_id)
        self.logger.info("Subscribed to city state", connection_id=connection_id)
    
    def unsubscribe_from_city_state(self, connection_id: str):
        """도시 상태 구독 해제"""
        self.city_state_subscribers.discard(connection_id)
        self.logger.info("Unsubscribed from city state", connection_id=connection_id)
    
    def get_stats(self) -> dict:
        """연결 통계"""
        return {
            "total_connections": len(self.active_connections),
            "total_users": len(self.user_connections),
            "subscribed_symbols": len(self.subscribed_symbols),
            "city_state_subscribers": len(self.city_state_subscribers),
            "active_symbols": list(self.subscribed_symbols.keys())
        }


# 전역 소켓 매니저 인스턴스
socket_manager = SocketManager()
