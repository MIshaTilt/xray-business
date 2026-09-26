import json
import os
import requests
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from engine.llm_logger import log_llm_interaction
from engine.tools import AI_TOOLS_DEFINITIONS, execute_tool_call, get_ai_tools_definitions
from engine.models import ChatMessage, Snapshot, record_llm_usage


def stream_openai_response(messages_list: list, snapshot_id: str = None):
    """
    Generator that proxies streaming response from OpenAI-compatible API to the client.
    Formats data as Server-Sent Events (SSE): 'data: {json}\n\n'.
    Supports Tool Calling (Function Calling) with SQLite deals querying before streaming final answer.
    """
    base_url = os.environ.get('OPENAI_BASE_URL', 'http://144.31.157.209:8317/v1').rstrip('/')
    api_key = os.environ.get('OPENAI_API_KEY', '')
    model_name = os.environ.get('OPENAI_MODEL', 'gemini-3.8-flash-high')

    target_url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    from engine.anonymizer import PIIAnonymizer
    anonymizer = PIIAnonymizer()
    if snapshot_id:
        try:
            from engine.models import Deal
            known_managers = Deal.objects.filter(snapshot_id=snapshot_id).exclude(manager='').values_list('manager', flat=True).distinct()[:150]
            for m in known_managers:
                anonymizer.register_exempt_name(m)

            known_clients = Deal.objects.filter(snapshot_id=snapshot_id).exclude(client='').values_list('client', flat=True).distinct()[:150]
            for c in known_clients:
                anonymizer.register_client(c)
        except Exception:
            pass

    try:
        current_messages = list(messages_list)
        executed_tools_for_saving = []
        initial_final_content = None
        accumulated_prompt_tokens = 0
        accumulated_completion_tokens = 0

        # 1. Step 1: Multi-turn tool resolution loop (supports tool chaining like search -> chart)
        if snapshot_id:
            try:
                tools_for_snapshot = get_ai_tools_definitions(snapshot_id)
                for round_idx in range(4):
                    # Enforce 152-FZ PII masking before sending to external LLM
                    tool_payload = {
                        "model": model_name,
                        "messages": anonymizer.anonymize_messages(current_messages),
                        "tools": tools_for_snapshot,
                        "tool_choice": "auto",
                        "stream": False
                    }
                    resp_tool = requests.post(target_url, headers=headers, json=tool_payload, timeout=25)
                    if resp_tool.status_code != 200:
                        break

                    t_json = resp_tool.json()
                    usage = t_json.get("usage") or {}
                    if usage:
                        accumulated_prompt_tokens += usage.get("prompt_tokens", 0)
                        accumulated_completion_tokens += usage.get("completion_tokens", 0)

                    choice = t_json.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    tool_calls = msg.get("tool_calls", [])

                    if not tool_calls:
                        # Model has concluded tool calls and produced its final textual answer
                        if msg.get("content"):
                            initial_final_content = msg.get("content")
                        break

                    current_messages.append(msg)
                    for tc in tool_calls:
                        func_name = tc.get("function", {}).get("name")
                        raw_args = tc.get("function", {}).get("arguments", "{}")
                        try:
                            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            parsed_args = {}

                        tool_result = execute_tool_call(func_name, parsed_args, snapshot_id)

                        # Emit an event to client about this tool execution
                        tool_event = {
                            "type": "tool_call",
                            "tool_name": func_name,
                            "arguments": parsed_args,
                            "result": tool_result
                        }
                        executed_tools_for_saving.append(tool_event)
                        yield f"data: {json.dumps(tool_event, ensure_ascii=False)}\n\n"

                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "name": func_name,
                            "content": tool_result
                        })
            except Exception as e:
                # Fallback smoothly to standard completion without tools
                print(f"[TOOL CALL ERROR]: {e}")

        # 2. Step 2: Stream final synthesized answer with SSE
        if initial_final_content:
            # We already have the complete synthesized answer from the model!
            # Stream it in chunks so the frontend UI gets the same real-time SSE effect
            chunk_size = 40
            for i in range(0, len(initial_final_content), chunk_size):
                sub_chunk = initial_final_content[i:i+chunk_size]
                chunk_event = {
                    "choices": [{
                        "delta": {"content": sub_chunk}
                    }]
                }
                yield f"data: {json.dumps(chunk_event, ensure_ascii=False)}\n\n"
            full_stream_response = initial_final_content
        else:
            payload = {
                "model": model_name,
                "messages": anonymizer.anonymize_messages(current_messages),
                "stream": True,
                "stream_options": {"include_usage": True}
            }

            collected_chunks = []
            try:
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
                                        # Track token usage from stream chunk
                                        chunk_usage = chunk_json.get("usage")
                                        if chunk_usage:
                                            accumulated_prompt_tokens += chunk_usage.get("prompt_tokens", 0)
                                            accumulated_completion_tokens += chunk_usage.get("completion_tokens", 0)

                                        content = chunk_json['choices'][0]['delta'].get('content', '')
                                        if content:
                                            collected_chunks.append(content)
                                    except Exception:
                                        pass
                                yield f"{decoded}\n\n"
                            else:
                                yield f"data: {decoded}\n\n"

                full_stream_response = "".join(collected_chunks).strip()
            except Exception as stream_err:
                print(f"[STREAM ERROR]: {stream_err}")
                full_stream_response = ""

            # If model emitted tools but no text tokens in stream, provide graceful summary text
            if not full_stream_response and executed_tools_for_saving:
                chart_call = next((tc for tc in executed_tools_for_saving if tc.get("tool_name") == "render_chart"), None)
                if chart_call and chart_call.get("result"):
                    try:
                        c_res = json.loads(chart_call["result"]) if isinstance(chart_call["result"], str) else chart_call["result"]
                        full_stream_response = c_res.get("summary", "График успешно построен и отображен выше.")
                    except Exception:
                        full_stream_response = "График успешно построен и отображен выше."
                else:
                    full_stream_response = "Запрос к базе данных выполнен. Необходимые данные получены."

                chunk_event = {
                    "choices": [{
                        "delta": {"content": full_stream_response}
                    }]
                }
                yield f"data: {json.dumps(chunk_event, ensure_ascii=False)}\n\n"

        log_llm_interaction(
            title="ПОТОКОВЫЙ ЧАТ: УСПЕШНЫЙ ОТВЕТ (RAG/TOOLS)",
            payload_data=payload if 'payload' in locals() else {"model": model_name, "stream": False},
            response_data=full_stream_response,
            extra_info=f"URL: {target_url} | STATUS: 200"
        )

        # 3. Step 3: Persist user prompt & assistant response in Django ORM ChatMessage + Record Token Usage
        if snapshot_id:
            try:
                snap_obj = Snapshot.objects.filter(id=snapshot_id).first()
                if snap_obj and full_stream_response:
                    # Find the last user message from current_messages
                    last_user_msg = next((m for m in reversed(messages_list) if m.get("role") == "user"), None)
                    if last_user_msg:
                        # Avoid duplicate user message if already exists as last user record
                        last_saved_user = ChatMessage.objects.filter(snapshot=snap_obj, role="user").last()
                        if not last_saved_user or last_saved_user.content != last_user_msg.get("content"):
                            ChatMessage.objects.create(
                                snapshot=snap_obj,
                                role="user",
                                content=last_user_msg.get("content", "")
                            )

                    # Save assistant response with tool_calls
                    ChatMessage.objects.create(
                        snapshot=snap_obj,
                        role="assistant",
                        content=full_stream_response,
                        tool_calls=executed_tools_for_saving
                    )

                # Atomically record LLM token usage for snapshot & user
                if accumulated_prompt_tokens > 0 or accumulated_completion_tokens > 0:
                    record_llm_usage(
                        user=snap_obj.user if snap_obj else None,
                        snapshot=snap_obj,
                        operation="chat_consultant",
                        model=model_name,
                        prompt_tokens=accumulated_prompt_tokens,
                        completion_tokens=accumulated_completion_tokens
                    )
            except Exception as e:
                print(f"[CHAT ORM SAVE ERROR]: {e}")

    except Exception as e:
        log_llm_interaction(
            title="ПОТОКОВЫЙ ЧАТ: ИСКЛЮЧЕНИЕ",
            payload_data=payload if 'payload' in locals() else {},
            response_data=str(e)
        )
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


from engine.views_api import get_snapshot_for_request


@csrf_exempt
def chat_stream(request):
    """
    POST or GET endpoint for streaming chat completion with message history, context and tool calling.
    """
    messages_list = []
    snapshot_id = None
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8'))
            snapshot_id = body.get('snapshot_id')
            if snapshot_id:
                snap_dict, snap_obj = get_snapshot_for_request(snapshot_id, request)
                if not snap_obj and not snap_dict:
                    return JsonResponse({'error': 'Снимок не найден или доступ ограничен'}, status=403)
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
        snapshot_id = request.GET.get('snapshot_id')
        messages_list = [
            {"role": "system", "content": "You are a helpful assistant for AI Business X-Ray."},
            {"role": "user", "content": prompt}
        ]

    response = StreamingHttpResponse(
        stream_openai_response(messages_list, snapshot_id=snapshot_id),
        content_type='text/event-stream'
    )
    # Necessary headers for smooth streaming through proxies/browsers
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
