from backend.services.llm_service import get_chat_completion
print("Testing LLM with attached filename")
try:
    print(get_chat_completion("hello", "test.pdf"))
except Exception as e:
    import traceback
    traceback.print_exc()
