from django.shortcuts import render

def test_chat_template(request):
   return render(request, 'chatting/chat.html')