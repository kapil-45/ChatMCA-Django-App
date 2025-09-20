# chatMCA/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # The main chat page
    path('', views.chat_page, name='chat_page'),
    # The API endpoint for processing chat messages
    path('chat/', views.chat_api, name='chat_api'),
    path('chat/new/', views.new_chat, name='new_chat'),
    path('api/history/', views.get_conversation_history, name='get_history'),
    path('api/conversation/load/', views.load_conversation, name='load_conversation'),
    path('api/conversation/delete/', views.delete_conversation, name='delete_conversation'),
    path('api/conversation/rename/', views.rename_conversation, name='rename_conversation'),
]

