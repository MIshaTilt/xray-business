import json
import os
import requests
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


def stream_openai_response(prompt: str):
    """
    Generator that proxies streaming response from OpenAI-compatible API to the client.
    Formats data as Server-Sent Events (SSE): 'data: {json}\n\n'.
    """
    base_url = os.environ.get('OPENAI_BASE_URL', 'http://144.31.157.209:8317/v1').rstrip('/')
    api_key = os.environ.get('OPENAI_API_KEY', '')

    target_url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gemini-3.8-flash-high",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant for AI Business X-Ray."},
            {"role": "user", "content": prompt}
        ],
        "stream": True
    }

    try:
        with requests.post(target_url, headers=headers, json=payload, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                err_text = resp.text
                yield f"data: {json.dumps({'error': f'Upstream error {resp.status_code}: {err_text}'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            for line in resp.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    # OpenAI SSE format outputs lines starting with "data: ..."
                    if decoded.startswith('data:'):
                        yield f"{decoded}\n\n"
                    else:
                        yield f"data: {decoded}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@csrf_exempt
def chat_stream(request):
    """
    POST or GET endpoint for streaming chat completion.
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8'))
            prompt = body.get('prompt', 'Hello world')
        except Exception:
            prompt = request.POST.get('prompt', 'Hello world')
    else:
        prompt = request.GET.get('prompt', 'Hello world')

    response = StreamingHttpResponse(
        stream_openai_response(prompt),
        content_type='text/event-stream'
    )
    # Necessary headers for smooth streaming through proxies/browsers
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
