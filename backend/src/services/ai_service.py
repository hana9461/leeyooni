"""
AI 서비스 통합 - GPT/Claude API
"""
import os
from typing import List, Dict, Any, Optional
import structlog
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from shared.schemas import ChatMessage, OrganismOutput

logger = structlog.get_logger(__name__)


class AIService:
    """AI 서비스 클래스 - GPT와 Claude 통합"""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.anthropic_client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        self.logger = logger.bind(service="ai")
    
    async def analyze_sentiment(self, news_text: str) -> Dict[str, Any]:
        """뉴스 감성 분석 (FearIndex용)"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 금융 뉴스의 감성을 분석하는 전문가입니다.
                        주어진 뉴스를 분석하여 다음 정보를 JSON 형태로 제공해주세요:
                        - sentiment: "positive", "negative", "neutral" 중 하나
                        - confidence: 0.0 ~ 1.0 사이의 신뢰도
                        - key_points: 뉴스의 핵심 포인트 리스트
                        - market_impact: "high", "medium", "low" 중 하나"""
                    },
                    {
                        "role": "user",
                        "content": f"다음 뉴스를 분석해주세요:\n\n{news_text}"
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            # JSON 파싱 시도
            try:
                import json
                result = json.loads(content)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본값 반환
                result = {
                    "sentiment": "neutral",
                    "confidence": 0.5,
                    "key_points": [content],
                    "market_impact": "medium"
                }
            
            self.logger.info("Sentiment analysis completed", 
                           sentiment=result.get("sentiment"),
                           confidence=result.get("confidence"))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to analyze sentiment: {e}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "key_points": ["분석 실패"],
                "market_impact": "low"
            }
    
    async def explain_signal(self, signal_data: OrganismOutput) -> str:
        """신호 설명 생성"""
        try:
            prompt = f"""
            다음은 {signal_data.organism.value} organism의 신호 분석 결과입니다:
            
            종목: {signal_data.symbol}
            신호: {signal_data.signal.value}
            신뢰도: {signal_data.trust:.2f}
            
            분석 요소:
            """
            
            for explain in signal_data.explain:
                prompt += f"- {explain.name}: {explain.value} ({explain.contribution.value})\n"
            
            prompt += """
            
            이 신호에 대해 일반 투자자가 이해하기 쉽게 설명해주세요.
            다음 요소를 포함해주세요:
            1. 신호의 의미와 해석
            2. 신뢰도가 높은/낮은 이유
            3. 투자 시 고려사항
            4. 주의사항
            
            한국어로 답변해주세요.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 금융 투자 분석가입니다. 복잡한 시장 신호를 일반인이 이해할 수 있도록 명확하고 정확하게 설명합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=800
            )
            
            explanation = response.choices[0].message.content
            self.logger.info("Signal explanation generated", 
                           organism=signal_data.organism.value,
                           symbol=signal_data.symbol)
            
            return explanation
            
        except Exception as e:
            self.logger.error(f"Failed to explain signal: {e}")
            return f"{signal_data.organism.value} 신호 분석 중 오류가 발생했습니다. 신호: {signal_data.signal.value}, 신뢰도: {signal_data.trust:.2f}"
    
    async def chat_with_user(self, messages: List[ChatMessage], model: str = "gpt-4") -> str:
        """사용자와 채팅"""
        try:
            # ChatMessage를 OpenAI/Anthropic 형식으로 변환
            formatted_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            if model.startswith("gpt"):
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=formatted_messages,
                    temperature=0.7,
                    max_tokens=1000
                )
                content = response.choices[0].message.content
                
            elif model.startswith("claude"):
                response = await self.anthropic_client.messages.create(
                    model=model,
                    max_tokens=1000,
                    messages=formatted_messages
                )
                content = response.content[0].text
                
            else:
                raise ValueError(f"Unsupported model: {model}")
            
            self.logger.info("Chat response generated", model=model)
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to generate chat response: {e}")
            return "죄송합니다. AI 응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    
    async def generate_market_summary(self, organism_outputs: List[OrganismOutput]) -> str:
        """시장 요약 생성"""
        try:
            prompt = "다음은 UNSLUG City의 최신 신호 분석 결과입니다:\n\n"
            
            for output in organism_outputs:
                prompt += f"""
                {output.organism.value} ({output.symbol}):
                - 신호: {output.signal.value}
                - 신뢰도: {output.trust:.2f}
                - 주요 요인: {', '.join([e.name for e in output.explain[:3]])}
                
                """
            
            prompt += """
            
            이 분석 결과를 바탕으로 현재 시장 상황에 대한 종합적인 요약을 제공해주세요.
            다음을 포함해주세요:
            1. 전체적인 시장 신호의 일관성
            2. 주요 투자 기회와 위험 요소
            3. 단기 전망과 주의사항
            
            투자자에게 실용적인 조언을 제공해주세요.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "당신은 전문 금융 분석가입니다. 다양한 신호를 종합하여 시장 상황을 정확하고 실용적으로 분석합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1000
            )
            
            summary = response.choices[0].message.content
            self.logger.info("Market summary generated")
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate market summary: {e}")
            return "시장 요약 생성 중 오류가 발생했습니다. 개별 신호를 참고해주세요."


# 전역 AI 서비스 인스턴스
ai_service = AIService()
