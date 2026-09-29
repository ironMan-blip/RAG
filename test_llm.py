from backend.services.llm_service import get_chat_completion
print("Testing LLM")
try:
    print(get_chat_completion("hello"))
except Exception as e:
    import traceback
    traceback.print_exc()
