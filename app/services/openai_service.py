"""
OpenAI Service — wraps the OpenAI API with budget tracking and usage logging.
"""

import os
import base64
import logging
from datetime import datetime, timedelta

from openai import OpenAI

logger = logging.getLogger(__name__)

# Cost per 1 million tokens (USD) for gpt-4o-mini
COST_TABLE = {
    'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
    'gpt-4o': {'input': 2.50, 'output': 10.00},
}
DEFAULT_MODEL = 'gpt-4o-mini'


class OpenAIService:
    """Singleton wrapper around the OpenAI chat & vision APIs."""

    _instance = None

    def __init__(self):
        self._api_key: str = os.getenv('OPENAI_API_KEY', '')
        self._client: OpenAI | None = None

    # ── lazy client ──────────────────────────────────────────────────────

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError('OPENAI_API_KEY is not set')
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    # ── config helpers (need Flask app context) ──────────────────────────

    def _get_model(self) -> str:
        from app.models import AppConfig
        return AppConfig.get('openai_model', DEFAULT_MODEL)

    def _get_daily_budget(self) -> float:
        from app.models import AppConfig
        try:
            return float(AppConfig.get('openai_daily_budget', '5.0'))
        except (TypeError, ValueError):
            return 5.0

    # ── budget guard ─────────────────────────────────────────────────────

    def _check_budget(self) -> bool:
        """Return True if spending today is still under the daily budget."""
        try:
            from app.models import OpenAIUsageLog

            budget = self._get_daily_budget()
            today_start = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            from app import db

            total_today = (
                db.session.query(db.func.coalesce(db.func.sum(OpenAIUsageLog.cost_estimate), 0))
                .filter(OpenAIUsageLog.created_at >= today_start)
                .scalar()
            )
            if total_today >= budget:
                logger.warning(
                    'Daily OpenAI budget exhausted: $%.4f / $%.2f',
                    total_today,
                    budget,
                )
                return False
            return True
        except Exception as e:
            logger.error('Budget check failed: %s', e)
            return True  # fail-open so the bot is not stuck

    # ── cost calculation ─────────────────────────────────────────────────

    @staticmethod
    def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = COST_TABLE.get(model, COST_TABLE[DEFAULT_MODEL])
        cost = (prompt_tokens * rates['input'] + completion_tokens * rates['output']) / 1_000_000
        return round(cost, 6)

    # ── usage logging ────────────────────────────────────────────────────

    def _log_usage(
        self,
        module: str,
        operation: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        try:
            from app import db
            from app.models import OpenAIUsageLog

            total_tokens = prompt_tokens + completion_tokens
            cost = self._calc_cost(model, prompt_tokens, completion_tokens)

            log = OpenAIUsageLog(
                module=module,
                operation=operation,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_estimate=cost,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error('Failed to log OpenAI usage: %s', e)

    # ── public API ───────────────────────────────────────────────────────

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        module: str,
        model: str | None = None,
    ) -> dict:
        """Send a chat completion request.

        Returns:
            dict with keys: content, prompt_tokens, completion_tokens,
                            total_tokens, cost, model
        """
        if not self._check_budget():
            return {
                'content': None,
                'error': 'Daily budget exceeded',
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'model': model or self._get_model(),
            }

        used_model = model or self._get_model()

        try:
            response = self.client.chat.completions.create(
                model=used_model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message},
                ],
                temperature=0.7,
            )

            choice = response.choices[0]
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens

            self._log_usage(
                module=module,
                operation='chat',
                model=used_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            return {
                'content': choice.message.content,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens,
                'cost': self._calc_cost(used_model, prompt_tokens, completion_tokens),
                'model': used_model,
            }
        except Exception as e:
            logger.error('OpenAI chat error (%s): %s', module, e)
            return {
                'content': None,
                'error': str(e),
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'model': used_model,
            }

    def chat_with_history(
        self,
        system_prompt: str,
        messages: list[dict],
        module: str,
        model: str | None = None,
    ) -> dict:
        """Chat completion with full message history.

        ``messages`` is a list of dicts with 'role' and 'content' keys.
        Returns the same dict format as ``chat()``.
        """
        if not self._check_budget():
            return {
                'content': None,
                'error': 'Daily budget exceeded',
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'model': model or self._get_model(),
            }

        used_model = model or self._get_model()

        try:
            full_messages = [{'role': 'system', 'content': system_prompt}] + messages

            response = self.client.chat.completions.create(
                model=used_model,
                messages=full_messages,
                temperature=0.7,
            )

            choice = response.choices[0]
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens

            self._log_usage(
                module=module,
                operation='chat_with_history',
                model=used_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            return {
                'content': choice.message.content,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens,
                'cost': self._calc_cost(used_model, prompt_tokens, completion_tokens),
                'model': used_model,
            }
        except Exception as e:
            logger.error('OpenAI chat_with_history error (%s): %s', module, e)
            return {
                'content': None,
                'error': str(e),
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'model': used_model,
            }

    def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        module: str,
        model: str | None = None,
    ) -> dict:
        """Send an image to the vision model for analysis.

        Returns the same dict format as ``chat()``.
        """
        if not self._check_budget():
            return {
                'content': None,
                'error': 'Daily budget exceeded',
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'model': model or self._get_model(),
            }

        used_model = model or self._get_model()

        try:
            b64_image = base64.b64encode(image_bytes).decode('utf-8')

            response = self.client.chat.completions.create(
                model=used_model,
                messages=[
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': prompt},
                            {
                                'type': 'image_url',
                                'image_url': {
                                    'url': f'data:image/jpeg;base64,{b64_image}'
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1024,
            )

            choice = response.choices[0]
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens

            self._log_usage(
                module=module,
                operation='analyze_image',
                model=used_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            return {
                'content': choice.message.content,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': prompt_tokens + completion_tokens,
                'cost': self._calc_cost(used_model, prompt_tokens, completion_tokens),
                'model': used_model,
            }
        except Exception as e:
            logger.error('OpenAI image analysis error (%s): %s', module, e)
            return {
                'content': None,
                'error': str(e),
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0.0,
                'model': used_model,
            }

    # ── Audio Transcription (Whisper) ────────────────────────────────────

    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio file using OpenAI Whisper API.
        
        Supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
        """
        try:
            logger.info(f'Transcribing audio: {audio_path}')
            
            with open(audio_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model='whisper-1',
                    file=audio_file,
                    language='en'  # Can be dynamic based on user language preference
                )
            
            text = transcript.text
            logger.info(f'Transcription complete: {text[:100]}...')
            
            # Log Whisper usage (optional - Whisper doesn't use tokens like GPT)
            # Cost: $0.02 per minute of audio
            self._log_usage(
                module='conversation',
                operation='audio_transcription',
                model='whisper-1',
                prompt_tokens=0,
                completion_tokens=0,
            )
            
            return text
            
        except Exception as e:
            logger.error(f'Whisper transcription error: {e}')
            return None

    # ── Singleton accessor ───────────────────────────────────────────────────

def get_openai_service() -> OpenAIService:
    if OpenAIService._instance is None:
        OpenAIService._instance = OpenAIService()
    return OpenAIService._instance
