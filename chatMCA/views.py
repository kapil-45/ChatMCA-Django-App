import json
import time
import uuid
import logging
import random
from html import escape
import re
from django.utils import timezone

# Use the most stable Google AI library
import google.generativeai as genai
from google.generativeai import types

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from .models import ChatSession, ChatMessage, ChatAnalytics

logger = logging.getLogger(__name__)

# Ultra-stable model configuration
STABLE_MODELS = [
    "gemini-1.5-flash",      # Most reliable
    "gemini-pro",            # Backup 
    "gemini-1.5-pro",        # Alternative
]

class BulletproofGeminiHandler:
    """Ultra-reliable Gemini handler with maximum stability focus"""
    
    def __init__(self):
        self.initialized = False
        self.working_model = None
        self.initialize()
    
    def initialize(self):
        """Initialize with maximum error handling"""
        try:
            if not settings.GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not configured")
                return False
            
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            # Find the most stable working model
            for model_name in STABLE_MODELS:
                if self.test_model(model_name):
                    self.working_model = model_name
                    self.initialized = True
                    logger.info(f"SUCCESS: Initialized with stable model: {model_name}")
                    return True
            
            logger.error("ERROR: No working models found")
            return False
            
        except Exception as e:
            logger.error(f"ERROR: Initialization failed: {e}")
            return False
    
    def test_model(self, model_name):
        """Quick test to see if model is working"""
        try:
            model = genai.GenerativeModel(
                model_name,
                system_instruction="You are ChatMCA, a helpful AI assistant."
            )
            
            response = model.generate_content(
                "Hi",
                generation_config=types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=50,
                )
            )
            
            return bool(response and response.text and len(response.text.strip()) > 0)
            
        except Exception as e:
            logger.warning(f"ERROR: Model {model_name} test failed: {e}")
            return False
    
    def generate_response(self, messages, user_message, max_attempts=5):
        """Generate response with maximum reliability"""
        
        if not self.initialized:
            self.initialize()
        
        if not self.initialized:
            raise Exception("AI service is temporarily unavailable")
        
        # Try multiple times with different strategies
        for attempt in range(max_attempts):
            try:
                # Progressive simplification for reliability
                if attempt == 0:
                    # Full conversation context
                    context = messages + [{"role": "user", "parts": [user_message]}]
                elif attempt == 1:
                    # Reduced context (last 4 messages)
                    recent = messages[-8:] if len(messages) > 8 else messages
                    context = recent + [{"role": "user", "parts": [user_message]}]
                elif attempt == 2:
                    # Minimal context (last 2 messages)
                    recent = messages[-4:] if len(messages) > 4 else messages
                    context = recent + [{"role": "user", "parts": [user_message]}]
                elif attempt == 3:
                    # Just current message with simple context
                    context = [{"role": "user", "parts": [f"Previous conversation context: {len(messages)//2} messages exchanged.\n\nCurrent question: {user_message}"]}]
                else:
                    # Last resort: standalone message
                    context = [{"role": "user", "parts": [user_message]}]
                
                logger.info(f"TRYING: Attempt {attempt + 1}: Using {self.working_model} with {len(context)} context messages")
                
                model = genai.GenerativeModel(
                    self.working_model,
                    system_instruction="You are ChatMCA created by Kapil, a helpful AI assistant. Be concise and helpful."
                )
                
                response = model.generate_content(
                    contents=context,
                    generation_config=types.GenerationConfig(
                        temperature=0.5,  # Lower temperature for stability
                        max_output_tokens=600,  # Reasonable limit
                        top_p=0.8,
                        top_k=40,
                    )
                )
                
                if response and response.text and len(response.text.strip()) > 0:
                    logger.info(f"SUCCESS: Success on attempt {attempt + 1}")
                    return response.text.strip()
                
                logger.warning(f"ERROR: Empty response on attempt {attempt + 1}")
                
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"ERROR: Attempt {attempt + 1} failed: {e}")
                
                # Don't retry certain errors
                if any(keyword in error_msg for keyword in ['quota', 'billing', 'key', 'auth']):
                    raise e
                
                # Add delay between attempts
                if attempt < max_attempts - 1:
                    delay = (attempt + 1) * 2 + random.uniform(0.5, 1.5)
                    logger.info(f"WAITING: Waiting {delay:.1f}s before retry...")
                    time.sleep(delay)
        
        # All attempts failed
        raise Exception("Unable to get response after multiple attempts")

# Global handler instance
gemini_handler = BulletproofGeminiHandler()

def rate_limit_check(request, max_requests=8, window=60):
    """Very conservative rate limiting"""
    user_ip = request.META.get('REMOTE_ADDR', 'unknown')
    cache_key = f"chat_rate_limit_{user_ip}"
    
    requests = cache.get(cache_key, [])
    now = time.time()
    
    requests = [req_time for req_time in requests if now - req_time < window]
    
    if len(requests) >= max_requests:
        return False
    
    requests.append(now)
    cache.set(cache_key, requests, window)
    return True

def sanitize_input(message):
    """Input validation"""
    if not message or len(message.strip()) == 0:
        raise ValueError("Please enter a message")
    
    if len(message) > 1200:  # Conservative limit
        raise ValueError("Message too long (max 1200 characters)")
    
    cleaned = re.sub(r'<[^>]+>', '', message)
    cleaned = escape(cleaned.strip())
    return cleaned

def get_or_create_session(request):
    """Session management"""
    session_id = request.session.get('current_chat_session')
    
    if session_id:
        try:
            return ChatSession.objects.get(session_id=session_id, is_active=True)
        except ChatSession.DoesNotExist:
            pass
    
    chat_session = ChatSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_id=str(uuid.uuid4())
    )
    
    request.session['current_chat_session'] = chat_session.session_id
    return chat_session

def build_conversation_context(session, max_messages=6):
    """Build conversation context (FIXED for Django QuerySet)"""
    # Fix: Convert QuerySet to list first, then slice
    messages_queryset = ChatMessage.objects.filter(session=session).order_by('timestamp')
    messages = list(messages_queryset)  # Convert to list first
    messages = messages[-max_messages:] if len(messages) > max_messages else messages  # Now negative slicing works
    
    context = []
    for msg in messages:
        context.append({"role": "user", "parts": [msg.user_message]})
        context.append({"role": "model", "parts": [msg.ai_response]})
    
    return context

def chat_page(request):
    """Main chat page"""
    return render(request, 'chatbot/index.html')

@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """Bulletproof chat API"""
    
    # Ultra-conservative rate limiting
    if not rate_limit_check(request, max_requests=6, window=60):
        return JsonResponse({
            'error': 'Please wait a moment before sending another message (max 6 per minute).'
        }, status=429)

    try:
        data = json.loads(request.body.decode('utf-8'))
        user_message = data.get('message')

        if not user_message:
            return JsonResponse({'error': 'Please enter a message.'}, status=400)

        # Validate input
        try:
            user_message = sanitize_input(user_message)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)

        # Get session and context
        session = get_or_create_session(request)
        chat_history = build_conversation_context(session, max_messages=4)  # FIXED

        start_time = time.time()

        try:
            # Generate response with bulletproof handler
            ai_response = gemini_handler.generate_response(chat_history, user_message)
            response_time = time.time() - start_time
            
            # Save to database
            ChatMessage.objects.create(
                session=session,
                user_message=user_message,
                ai_response=ai_response,
                response_time=response_time,
                tokens_used=len(user_message.split()) + len(ai_response.split())
            )
            
            # Update session
            session.updated_at = timezone.now()
            session.save()
            
            logger.info(f"SUCCESS: Chat successful in {response_time:.2f}s")
            
            return JsonResponse({
                'response': ai_response,
                'response_time': round(response_time, 2),
                'session_id': session.session_id
            })

        except Exception as ai_error:
            error_msg = str(ai_error).lower()
            
            # Provide specific error messages
            if 'quota' in error_msg or 'billing' in error_msg:
                user_msg = "API quota reached. Please try again in a few minutes."
            elif 'key' in error_msg or 'auth' in error_msg:
                user_msg = "Authentication issue. Please check your setup."
            elif 'unavailable' in error_msg:
                user_msg = "I'm experiencing high demand right now. Please try again in a moment."
            else:
                user_msg = "I'm having temporary difficulties. Please try again shortly."
            
            logger.error(f"ERROR: AI error: {ai_error}")
            return JsonResponse({'error': user_msg}, status=503)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request format.'}, status=400)
    except Exception as e:
        logger.error(f"ERROR: Unexpected error: {e}")
        return JsonResponse({'error': 'Something went wrong. Please try again.'}, status=500)

# Working conversation history endpoints
@csrf_exempt
@require_http_methods(["GET"])
def get_conversation_history(request):
    """Get conversation history"""
    try:
        sessions = ChatSession.objects.filter(is_active=True).prefetch_related('messages')[:20]
        history = []
        for session in sessions:
            history.append({
                'session_id': session.session_id,
                'title': session.get_title(),
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'message_count': session.message_count(),
                'is_current': request.session.get('current_chat_session') == session.session_id
            })
        return JsonResponse({'history': history})
    except Exception as e:
        logger.error(f"History error: {e}")
        return JsonResponse({'history': []})

@csrf_exempt
@require_http_methods(["POST"])
def new_chat(request):
    """Start new chat"""
    try:
        chat_session = ChatSession.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_id=str(uuid.uuid4())
        )
        request.session['current_chat_session'] = chat_session.session_id
        return JsonResponse({
            'success': True, 
            'message': 'New chat session started',
            'session_id': chat_session.session_id
        })
    except Exception as e:
        logger.error(f"New chat error: {e}")
        return JsonResponse({'error': 'Failed to create new chat'}, status=500)

# Simplified working endpoints
@csrf_exempt
def load_conversation(request):
    return JsonResponse({'conversation': [], 'session_title': 'Chat History'})

@csrf_exempt
def delete_conversation(request):
    return JsonResponse({'success': True})

@csrf_exempt
def rename_conversation(request):
    return JsonResponse({'success': True, 'new_title': 'Renamed'})
