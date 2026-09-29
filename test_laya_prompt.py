import sys
from laya import load

def test_laya():
    agent = load("convaiinnovations/laya")
    
    # 1. The original way (failing)
    q1 = {
        "needs_context": {
            "type": "noul", 
            "instructions": "Does this message require looking up facts, data, or external documents? (Yes for factual queries, No for casual greetings or general chat)"
        }
    }
    
    # 2. The proper Laya way
    q2 = {
        "needs_context": {
            "type": "noul", 
            "instructions": "Does `request` require looking up facts, data, or external documents?",
            "criteria": {
                "false": "casual greetings, conversational chat, or statements that require no context",
                "true": "factual queries or questions that need external documents"
            }
        }
    }

    tests = [
        "hello",
        "how are you",
        "what is the title of pdf 2 which needs context and is available in dataset"
    ]
    
    for t in tests:
        print(f"\n--- Testing: '{t}' ---")
        
        # Method 1
        res1 = agent.predict(t, q1)
        prob1 = res1["answers"]["needs_context"]["noul"]
        
        # Method 2
        res2 = agent.predict({"request": t}, q2)
        prob2 = res2["answers"]["needs_context"]["noul"]
        
        print(f"Method 1 (String + Instructions only): {prob1*100:.2f}%")
        print(f"Method 2 (JSON + Criteria): {prob2*100:.2f}%")

if __name__ == '__main__':
    test_laya()
