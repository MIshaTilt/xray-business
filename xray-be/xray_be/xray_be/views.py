import json
import os
import requests
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from engine.llm_logger import log_llm_interaction


def stream_openai_response(messages_list: list):
    """
    Generator that proxies streaming response from OpenAI-compatible API to the client.
    Formats data as Server-Sent Events (SSE): 'data: {json}\n\n'.
    Accepts full messages list with system prompt and history.
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
        "messages": messages_list,
        "stream": True
    }

    try:
        collected_chunks = []
        with requests.post(target_url, headers=headers, json=payload, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                err_text = resp.text
                log_llm_interaction(
                    title="ПОТОКОВЫЙ ЧАТ: ОШИБКА",
                    payload_data=payload,
                    response_data=err_text,
                    extra_info=f"STATUS: {resp.status_code}"
                )
                yield f"data: {json.dumps({'error': f'Upstream error {resp.status_code}: {err_text}'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            for line in resp.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data:'):
                        raw_data = decoded[5:].strip()
                        if raw_data != '[DONE]':
                            try:
                                chunk_json = json.loads(raw_data)
                                content = chunk_json['choices'][0]['delta'].get('content', '')
                                if content:
                                    collected_chunks.append(content)
                            except Exception:
                                pass
                        yield f"{decoded}\n\n"
                    else:
                        yield f"data: {decoded}\n\n"

        full_stream_response = "".join(collected_chunks)
        log_llm_interaction(
            title="ПОТОКОВЫЙ ЧАТ: УСПЕШНЫЙ ОТВЕТ",
            payload_data=payload,
            response_data=full_stream_response,
            extra_info=f"URL: {target_url} | STATUS: 200"
        )

    except Exception as e:
        log_llm_interaction(
            title="ПОТОКОВЫЙ ЧАТ: ИСКЛЮЧЕНИЕ",
            payload_data=payload if 'payload' in locals() else {},
            response_data=str(e)
        )
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@csrf_exempt
def chat_stream(request):
    """
    POST or GET endpoint for streaming chat completion with message history and context.
    """
    messages_list = []
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8'))
            if 'messages' in body and isinstance(body['messages'], list):
                messages_list = body['messages']
            else:
                prompt = body.get('prompt', 'Hello world')
                messages_list = [
                    {"role": "system", "content": "You are a helpful assistant for AI Business X-Ray."},
                    {"role": "user", "content": prompt}
                ]
        except Exception:
            prompt = request.POST.get('prompt', 'Hello world')
            messages_list = [
                {"role": "system", "content": "You are a helpful assistant for AI Business X-Ray."},
                {"role": "user", "content": prompt}
            ]
    else:
        prompt = request.GET.get('prompt', 'Hello world')
        messages_list = [
            {"role": "system", "content": "You are a helpful assistant for AI Business X-Ray."},
            {"role": "user", "content": prompt}
        ]

    response = StreamingHttpResponse(
        stream_openai_response(messages_list),
        content_type='text/event-stream'
    )
    # Necessary headers for smooth streaming through proxies/browsers
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
